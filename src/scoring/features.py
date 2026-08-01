"""Structured feature extraction. Pure code, no LLM calls.

Reads the flat-file data sources and computes deterministic per-account
metrics. Each function operates on one domain independently (CRM, usage,
billing) — no cross-talk between them, matching the fan-out/fan-in shape
described in docs/methodology.md.
"""
import csv
import os
from dataclasses import dataclass
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
REPORT_DATE = date(2026, 8, 1)


def _read_csv(name: str) -> list[dict]:
    path = os.path.join(DATA_DIR, name)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


@dataclass
class StructuredFeatures:
    account_id: str
    account_name: str
    plan_tier: str
    primary_contact_name: str
    usage_trend_pct: float
    open_tickets: int
    high_severity_open_tickets: int
    days_to_renewal: int
    invoice_overdue_days: int
    days_since_last_meeting: int
    contract_trend_pct: float
    champion_turnover_flag: bool


def compute_usage_trend(rows: list[dict], account_id: str) -> float:
    """% change: avg of most recent 4 weeks vs. avg of the prior 4 weeks."""
    weekly = sorted(
        (int(r["week_index"]), int(r["active_users"])) for r in rows if r["account_id"] == account_id
    )
    values = [v for _, v in weekly]
    if len(values) < 8:
        raise ValueError(f"expected 8 weeks of usage data for {account_id}, got {len(values)}")
    prior_avg = sum(values[:4]) / 4
    recent_avg = sum(values[4:]) / 4
    if prior_avg == 0:
        return 0.0
    return round((recent_avg - prior_avg) / prior_avg * 100, 1)


def compute_ticket_features(rows: list[dict], account_id: str) -> tuple[int, int]:
    account_tickets = [r for r in rows if r["account_id"] == account_id]
    open_tickets = [t for t in account_tickets if t["status"] == "open"]
    high_severity_open = [t for t in open_tickets if t["severity"] == "high"]
    return len(open_tickets), len(high_severity_open)


def load_all_structured_features() -> list[StructuredFeatures]:
    crm_rows = _read_csv("crm.csv")
    usage_rows = _read_csv("usage.csv")
    billing_rows = _read_csv("billing.csv")
    ticket_rows = _read_csv("tickets.csv")

    billing_by_account = {r["account_id"]: r for r in billing_rows}

    results = []
    for crm in crm_rows:
        account_id = crm["account_id"]
        billing = billing_by_account[account_id]

        usage_trend_pct = compute_usage_trend(usage_rows, account_id)
        open_tickets, high_severity_open = compute_ticket_features(ticket_rows, account_id)

        days_to_renewal = (_parse_date(crm["renewal_date"]) - REPORT_DATE).days
        days_since_last_meeting = (REPORT_DATE - _parse_date(crm["last_meeting_date"])).days
        champion_turnover_flag = bool(crm["contact_changed_date"].strip())

        results.append(StructuredFeatures(
            account_id=account_id,
            account_name=crm["account_name"],
            plan_tier=crm["plan_tier"],
            primary_contact_name=crm["primary_contact_name"],
            usage_trend_pct=usage_trend_pct,
            open_tickets=open_tickets,
            high_severity_open_tickets=high_severity_open,
            days_to_renewal=days_to_renewal,
            invoice_overdue_days=int(billing["invoice_overdue_days"]),
            days_since_last_meeting=days_since_last_meeting,
            contract_trend_pct=float(billing["contract_trend_pct"]),
            champion_turnover_flag=champion_turnover_flag,
        ))
    return results
