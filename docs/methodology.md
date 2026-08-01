# Scoring methodology

## Composite risk score

Each account gets a **risk score (0–100, higher = riskier)**, built from 7 weighted components. The health score shown in the report is `100 − risk_score` (higher = healthier), banded:

| Band | Risk score | Meaning |
|---|---|---|
| Green | 0–14 | Healthy |
| Yellow | 15–44 | Watch |
| Red | 45–100 | At risk |

Thresholds are calibrated against the 8-account synthetic sample, not an even three-way split — with 7 components at max weight 0.20, an even split would mean no single risk factor could ever cross into yellow, and severe compounding risk (e.g. usage collapse + open high-severity tickets, modeled on the round-1 escalation example) wouldn't reliably reach red either.

## Components and weights

| Component | Weight | Signal | Source |
|---|---|---|---|
| Usage trend | 0.20 | % decline in active usage over trailing 30 days vs. prior 30 | Usage (structured) |
| Support ticket risk | 0.20 | Open ticket count + severity mix, weighted toward unresolved/high-severity | Tickets (structured) |
| Renewal proximity | 0.15 | Days to renewal, scaled up as the date approaches | CRM/contract (structured) |
| Payment delinquency | 0.15 | Invoice overdue days / amount overdue | Billing (structured) |
| Engagement recency | 0.10 | Days since last CSM touchpoint/meeting | CRM (structured) |
| Contract trend | 0.10 | % contraction at last renewal (expansion reduces risk) | Billing/CRM (structured) |
| Champion turnover | 0.10 | Primary contact changed recently, or note-derived signal that the new contact is unfamiliar with the platform | CRM (structured) + notes (LLM-extracted) |

Weights sum to 1.0. Each component is scored 0–100 independently via a documented threshold function (see `src/scoring/formula.py`), then combined as a weighted sum. **No LLM call participates in this number** — it is deterministic and reproducible from the same inputs every time.

## Where the LLM contributes

- **Extraction** (per note/ticket, independent, narrow-scope): classifies risk tone, theme (e.g., competitor mention, champion unfamiliarity), producing structured flags that feed the champion-turnover and ticket-risk components above.
- **Reasoning/synthesis** (per account, after the score is computed): reviews the account's full computed evidence together and produces a qualitative escalation judgment (`NO_ACTION` / `CSM_CHECK_IN` / `EXEC_ESCALATION`) + narrative. This sits alongside the score — it does not change the number.

## Known limitation

Weights above are a reasoned starting hypothesis tied to Solovis's stated downsell-mitigation KPI, not fitted against historical churn outcomes (no ground truth exists for a synthetic dataset). A production version would calibrate weights against realized churn/downsell history.
