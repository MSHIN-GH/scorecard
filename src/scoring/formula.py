"""Deterministic scoring formula. No LLM calls in this module.

See docs/methodology.md for the rationale behind weights and thresholds.
"""
from dataclasses import dataclass


WEIGHTS = {
    "usage_trend": 0.20,
    "ticket_risk": 0.20,
    "renewal_proximity": 0.15,
    "payment_delinquency": 0.15,
    "engagement_recency": 0.10,
    "contract_trend": 0.10,
    "champion_turnover": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


@dataclass
class AccountFeatures:
    """Structured inputs, already extracted (steps 2 + 3 of the pipeline)."""

    account_id: str
    usage_trend_pct: float  # negative = decline, e.g. -40.0
    open_tickets: int
    high_severity_open_tickets: int
    days_to_renewal: int
    invoice_overdue_days: int
    days_since_last_meeting: int
    contract_trend_pct: float  # negative = contraction
    champion_turnover_flag: bool
    champion_unfamiliar_flag: bool  # from LLM note extraction


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def score_usage_trend(f: AccountFeatures) -> float:
    if f.usage_trend_pct >= 0:
        return 0.0
    return _clamp(abs(f.usage_trend_pct) * 2.0)


def score_ticket_risk(f: AccountFeatures) -> float:
    base = f.open_tickets * 12
    severity_bump = f.high_severity_open_tickets * 20
    return _clamp(base + severity_bump)


def score_renewal_proximity(f: AccountFeatures) -> float:
    if f.days_to_renewal > 180:
        return 0.0
    if f.days_to_renewal <= 0:
        return 100.0
    return _clamp(100.0 * (1 - f.days_to_renewal / 180))


def score_payment_delinquency(f: AccountFeatures) -> float:
    return _clamp(f.invoice_overdue_days * 2.5)


def score_engagement_recency(f: AccountFeatures) -> float:
    if f.days_since_last_meeting <= 30:
        return 0.0
    return _clamp((f.days_since_last_meeting - 30) * 1.5)


def score_contract_trend(f: AccountFeatures) -> float:
    if f.contract_trend_pct >= 0:
        return 0.0
    return _clamp(abs(f.contract_trend_pct) * 3.0)


def score_champion_turnover(f: AccountFeatures) -> float:
    score = 0.0
    if f.champion_turnover_flag:
        score += 60.0
    if f.champion_unfamiliar_flag:
        score += 40.0
    return _clamp(score)


COMPONENT_SCORERS = {
    "usage_trend": score_usage_trend,
    "ticket_risk": score_ticket_risk,
    "renewal_proximity": score_renewal_proximity,
    "payment_delinquency": score_payment_delinquency,
    "engagement_recency": score_engagement_recency,
    "contract_trend": score_contract_trend,
    "champion_turnover": score_champion_turnover,
}


def component_scores(f: AccountFeatures) -> dict:
    return {name: fn(f) for name, fn in COMPONENT_SCORERS.items()}


def composite_risk_score(f: AccountFeatures) -> float:
    scores = component_scores(f)
    return sum(scores[name] * WEIGHTS[name] for name in WEIGHTS)


def band(risk_score: float) -> str:
    """Thresholds calibrated against the 8-account synthetic sample so that
    compounding real risk (e.g. usage collapse + open high-severity tickets)
    lands in red, and a single moderate factor lands in yellow rather than
    being swallowed by an arbitrary midpoint cutoff. See docs/methodology.md.
    """
    if risk_score >= 45:
        return "red"
    if risk_score >= 15:
        return "yellow"
    return "green"


def top_drivers(f: AccountFeatures, n: int = 3) -> list[tuple[str, float]]:
    scores = component_scores(f)
    weighted = {name: scores[name] * WEIGHTS[name] for name in WEIGHTS}
    return sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)[:n]
