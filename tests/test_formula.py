import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scoring.formula import AccountFeatures, composite_risk_score, band, top_drivers, WEIGHTS


def make_features(**overrides) -> AccountFeatures:
    defaults = dict(
        account_id="TEST-001",
        usage_trend_pct=0.0,
        open_tickets=0,
        high_severity_open_tickets=0,
        days_to_renewal=365,
        invoice_overdue_days=0,
        days_since_last_meeting=0,
        contract_trend_pct=0.0,
        champion_turnover_flag=False,
        champion_unfamiliar_flag=False,
    )
    defaults.update(overrides)
    return AccountFeatures(**defaults)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_all_healthy_account_scores_near_zero():
    f = make_features()
    score = composite_risk_score(f)
    assert score == 0.0
    assert band(score) == "green"


def test_severe_usage_decline_drives_score_up():
    healthy = composite_risk_score(make_features())
    declining = composite_risk_score(make_features(usage_trend_pct=-50))
    assert declining > healthy
    assert band(declining) in ("yellow", "red")


def test_renewal_at_zero_days_maxes_that_component():
    f = make_features(days_to_renewal=0)
    score = composite_risk_score(f)
    assert score == 100 * WEIGHTS["renewal_proximity"]


def test_renewal_far_out_contributes_nothing():
    f = make_features(days_to_renewal=365)
    score = composite_risk_score(f)
    assert score == 0.0


def test_compounding_risk_factors_produce_red_band():
    f = make_features(
        usage_trend_pct=-45,
        open_tickets=3,
        high_severity_open_tickets=2,
        days_to_renewal=30,
        days_since_last_meeting=60,
    )
    score = composite_risk_score(f)
    assert band(score) == "red"


def test_champion_turnover_alone_is_moderate_not_critical():
    f = make_features(champion_turnover_flag=True, champion_unfamiliar_flag=True)
    score = composite_risk_score(f)
    assert score == 100 * WEIGHTS["champion_turnover"]
    assert band(score) != "red"


def test_top_drivers_returns_highest_weighted_components_first():
    f = make_features(usage_trend_pct=-50, open_tickets=5, high_severity_open_tickets=2)
    drivers = top_drivers(f, n=2)
    assert len(drivers) == 2
    assert drivers[0][1] >= drivers[1][1]
    driver_names = {name for name, _ in drivers}
    assert "usage_trend" in driver_names or "ticket_risk" in driver_names


def test_score_is_reproducible_across_runs():
    f = make_features(usage_trend_pct=-30, open_tickets=2, invoice_overdue_days=40)
    assert composite_risk_score(f) == composite_risk_score(f)
