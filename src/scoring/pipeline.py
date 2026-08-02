"""Orchestrates the full pipeline: structured features -> LLM extraction
(one batched call per account) -> deterministic score -> LLM reasoning layer
-> assembled per-account result + portfolio rollup.

Fan-out/fan-in shape: accounts are independent of one another and are fanned
out across a thread pool; this module is the only aggregator.
"""
import csv
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import formula
from .extraction import classify_texts_batch, Theme
from .features import DATA_DIR, load_all_structured_features, StructuredFeatures
from .synthesis import synthesize, SynthesisResult


def _read_csv(name: str) -> list[dict]:
    path = os.path.join(DATA_DIR, name)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class ExtractedItem:
    source_type: str
    source_id: str
    text: str
    risk_tone: str
    theme: str
    risk_flag: bool


@dataclass
class AccountResult:
    account_id: str
    account_name: str
    plan_tier: str
    primary_contact_name: str
    structured: StructuredFeatures
    extracted_items: list[ExtractedItem]
    component_scores: dict
    risk_score: float
    health_score: float
    band: str
    top_drivers: list[tuple[str, float]]
    score_breakdown: list[dict]
    narrative: str
    action_recommendation: str


def _extract_account_signals(account_id: str, tickets: list[dict], notes: list[dict]) -> list[ExtractedItem]:
    """One batched call classifies every ticket/note for this account at once
    — see extraction.classify_texts_batch for why this is still extraction,
    not reasoning, despite batching the request."""
    account_tickets = [t for t in tickets if t["account_id"] == account_id]
    account_notes = [n for n in notes if n["account_id"] == account_id]

    jobs = [("ticket", t["ticket_id"], t["body_text"]) for t in account_tickets]
    jobs += [("note", f"{n['date']}-note", n["note_text"]) for n in account_notes]

    if not jobs:
        return []

    batch_items = [(source_id, source_type, text) for source_type, source_id, text in jobs]
    classifications = classify_texts_batch(batch_items)

    results = []
    for source_type, source_id, text in jobs:
        result = classifications[source_id]
        results.append(ExtractedItem(
            source_type=source_type,
            source_id=source_id,
            text=text,
            risk_tone=result.risk_tone.value,
            theme=result.theme.value,
            risk_flag=result.risk_flag,
        ))
    return results


def _score_breakdown(comp_scores: dict) -> list[dict]:
    """Full per-component accounting: weighted points earned vs. the max
    possible for that component (raw score * weight, and weight * 100)."""
    rows = [
        {
            "name": name,
            "actual": round(raw * formula.WEIGHTS[name], 1),
            "max": round(formula.WEIGHTS[name] * 100, 1),
        }
        for name, raw in comp_scores.items()
    ]
    return sorted(rows, key=lambda r: r["actual"], reverse=True)


def _evidence_summary(items: list[ExtractedItem]) -> str:
    if not items:
        return "No support tickets or CSM notes on file for this period."
    lines = []
    for item in items:
        excerpt = item.text if len(item.text) <= 200 else item.text[:200] + "..."
        lines.append(f"- [{item.source_type}] tone={item.risk_tone}, theme={item.theme}: \"{excerpt}\"")
    return "\n".join(lines)


MAX_CONCURRENT_ACCOUNTS = 8  # caps concurrent Anthropic calls across accounts; raise if rate limits allow


def _score_account(structured: StructuredFeatures, tickets: list[dict], notes: list[dict]) -> AccountResult:
    """Scores a single account end-to-end. Accounts are fully independent of
    one another, so run_pipeline fans these out across a thread pool rather
    than processing accounts one at a time."""
    extracted_items = _extract_account_signals(structured.account_id, tickets, notes)

    champion_unfamiliar_flag = any(
        item.theme == Theme.champion_unfamiliar.value for item in extracted_items
    )

    account_features = formula.AccountFeatures(
        account_id=structured.account_id,
        usage_trend_pct=structured.usage_trend_pct,
        open_tickets=structured.open_tickets,
        high_severity_open_tickets=structured.high_severity_open_tickets,
        days_to_renewal=structured.days_to_renewal,
        invoice_overdue_days=structured.invoice_overdue_days,
        days_since_last_meeting=structured.days_since_last_meeting,
        contract_trend_pct=structured.contract_trend_pct,
        champion_turnover_flag=structured.champion_turnover_flag,
        champion_unfamiliar_flag=champion_unfamiliar_flag,
    )

    comp_scores = formula.component_scores(account_features)
    risk_score = formula.composite_risk_score(account_features)
    acc_band = formula.band(risk_score)
    drivers = formula.top_drivers(account_features)

    synthesis: SynthesisResult = synthesize(
        account_name=structured.account_name,
        risk_score=risk_score,
        band=acc_band,
        top_drivers=drivers,
        evidence_summary=_evidence_summary(extracted_items),
    )

    return AccountResult(
        account_id=structured.account_id,
        account_name=structured.account_name,
        plan_tier=structured.plan_tier,
        primary_contact_name=structured.primary_contact_name,
        structured=structured,
        extracted_items=extracted_items,
        component_scores=comp_scores,
        risk_score=round(risk_score, 1),
        health_score=round(100 - risk_score, 1),
        band=acc_band,
        top_drivers=drivers,
        score_breakdown=_score_breakdown(comp_scores),
        narrative=synthesis.narrative,
        action_recommendation=synthesis.action_recommendation.value,
    )


def run_pipeline() -> list[AccountResult]:
    structured_list = load_all_structured_features()
    tickets = _read_csv("tickets.csv")
    notes = _read_csv("notes.csv")

    with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_ACCOUNTS, len(structured_list))) as pool:
        return list(pool.map(lambda s: _score_account(s, tickets, notes), structured_list))


def portfolio_rollup(results: list[AccountResult]) -> dict:
    total = len(results)
    band_counts = {"red": 0, "yellow": 0, "green": 0}
    for r in results:
        band_counts[r.band] += 1
    avg_health = sum(r.health_score for r in results) / total if total else 0
    escalations = [r for r in results if r.action_recommendation == "EXEC_ESCALATION"]
    return {
        "total_accounts": total,
        "band_counts": band_counts,
        "avg_health_score": round(avg_health, 1),
        "exec_escalation_accounts": [r.account_name for r in escalations],
    }
