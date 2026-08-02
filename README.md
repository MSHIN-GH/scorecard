# Client Health Scorecard

A code-based pipeline that scores client accounts on churn/downsell risk, combining deterministic structured metrics with LLM-extracted signals from unstructured notes. Built as a follow-up exploration after a conversation about quantifying client health — synthetic data throughout, no real client data used.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python3 scripts/generate_synthetic_data.py   # writes data/*.csv (already committed, safe to re-run)
python3 run.py                                # runs the full pipeline, writes output/results.json
streamlit run app.py                          # launches the viewer at localhost:8501
```

A pre-generated `output/results.json` is already committed, so `streamlit run app.py` works immediately without needing an API key or running the pipeline first. Live at **[case-study-scorecard.streamlit.app](https://case-study-scorecard.streamlit.app)**.

The viewer reads that cached snapshot rather than making live LLM calls per viewer — landing view is a portfolio table filterable by risk level and recommended action, with a dropdown to drill into any account's full scorecard. This stands in for what a scheduled daily batch job + shared dashboard would look like in production — see the note in `src/scoring/serialize.py` for why a flat JSON snapshot is a demo-scale stand-in for a database table.

## Architecture

```
data/*.csv (CRM, usage, tickets, billing, notes)
        │
        ▼
structured feature extraction (code, no LLM)      ─┐  independent, no cross-talk
        │                                           │  (fan-out)
unstructured signal extraction (LLM, per item)     ─┘
        │
        ▼
deterministic composite score  (code — the number is never LLM-decided)
        │
        ▼
reasoning/synthesis layer (LLM — reasons across an account's full evidence,
        │                        produces narrative + action_recommendation)
        ▼
output assembly → results.json snapshot → Streamlit viewer reads the snapshot
```

- **Structured extraction** (`src/scoring/features.py`) — usage trend, ticket velocity/severity, renewal proximity, payment delinquency, engagement recency, contract trend, contact turnover. Pure functions, no LLM.
- **Unstructured extraction** (`src/scoring/extraction.py`) — one structured-output call per **account**, classifying every one of that account's tickets/notes in a single batched request, on `claude-haiku-4-5`. Still extraction, not reasoning: the model is explicitly instructed to classify each item on its own content, not let one item's tone influence another's — batching by account avoids paying the ~700-token fixed schema overhead once per document instead of once per account, without changing what's actually being decided. A narrow classification task doesn't need Sonnet-tier reasoning, so it runs on the cheaper, faster model; Sonnet is reserved for the step that actually reasons across combined evidence.
- **Deterministic score** (`src/scoring/formula.py`) — a weighted formula combining all of the above into a 0–100 risk score, band, and top drivers. Fully explainable and reproducible: same inputs always produce the same score. See `docs/methodology.md` for the full weighting rationale.
- **Reasoning/synthesis layer** (`src/scoring/synthesis.py`, `claude-sonnet-4-5`) — the one point in the pipeline where the LLM sees an account's combined evidence together, and judges whether it reinforces or contradicts the computed score. Outputs a structured schema (narrative + `action_recommendation` enum: `NO_ACTION` / `CSM_CHECK_IN` / `EXEC_ESCALATION`) — the enum is what would make this machine-actionable for a downstream workflow (a Salesforce task, a Slack alert). It's a recommendation surfaced for CSM review, not an autonomous trigger — no auto-execution logic exists in this codebase.

This is a fan-out/fan-in pipeline, not a multi-agent system — the LLM touches exactly two narrow, bounded points (extraction, synthesis), and nothing talks to anything else in between. Accounts are independent of one another and are fanned out across a thread pool (`src/scoring/pipeline.py::run_pipeline`, `MAX_CONCURRENT_ACCOUNTS = 8`) — the same design principle applied one level up from the per-account extraction batching.

## Micro-benchmark

Measured on the full 8-account synthetic dataset (16 LLM calls: 8 batched extraction + 8 synthesis), priced per-call by the model that actually served it (Haiku vs. Sonnet, not a single flat rate):

| Metric | Value |
|---|---|
| Avg. LLM cost per account | ~$0.010 |
| Test-portfolio (8 accounts) wall time | ~15s |
| Test-portfolio (8 accounts) total cost | ~$0.08 |

This is down from an earlier version of this pipeline (one call per document, everything on Sonnet) that cost ~$0.016/account and took ~26s for the same 8 accounts — batching extraction per-account plus moving it to Haiku cut cost by ~35% and wall time by ~45%, with no measurable quality loss (spot-checked against the same proof-point accounts below).

Cost scales linearly with account count; wall time scales with account count divided by concurrency. Solovis's actual client-account count wasn't directly available — the round-1 case study estimated it from public headcount data as ~20 CSMs × a 20–25 account book each, i.e. **~400–500 accounts**, not the ~150–160 figure that was Solovis's total *employee* headcount. Extrapolating from the measured throughput above at the same concurrency cap: a full run at that scale would take roughly **12–16 minutes for ~$4–5** — well within a nightly batch window, with the concurrency cap raisable in production, bounded by whatever Anthropic rate-limit tier applies.

## Project structure

```
data/                   synthetic CSVs (CRM, usage, tickets, billing, notes)
scripts/
  generate_synthetic_data.py   regenerates data/*.csv deterministically
docs/
  methodology.md         full scoring methodology and weight rationale
src/
  scoring/
    features.py           structured feature extraction (no LLM)
    extraction.py          unstructured signal extraction (LLM, narrow scope)
    formula.py              deterministic composite score
    synthesis.py             reasoning/synthesis layer (LLM)
    pipeline.py               orchestrates the above
    serialize.py               reads/writes the cached results.json snapshot
  render/
    html_report.py            secondary output format (static HTML), not the primary deliverable
templates/
  report.html.jinja      template for the above
tests/
  test_formula.py        unit tests for the deterministic scoring formula
output/
  results.json           cached snapshot the Streamlit viewer reads (committed)
  report.html            static HTML rendering of the same data (committed, secondary)
run.py                   single entry point: run the pipeline, write results.json (+ report.html)
app.py                   the viewer — streamlit run app.py
```

## Known limitations

- **No ground truth.** Weights in `formula.py` are a reasoned starting hypothesis tied to a downsell-mitigation framing, not fitted against real historical churn outcomes — there's no ground truth available for a synthetic dataset. A production version would calibrate weights against realized churn/downsell history (e.g. logistic regression on outcomes).
- **The reasoning layer's narrative isn't deterministic.** Running the pipeline twice can produce different wording, and occasionally a different `action_recommendation` on borderline accounts (observed directly: on one run an already-healthy account got `CSM_CHECK_IN` instead of `NO_ACTION`). The high-confidence cases (the clearest red account, the clearest contradiction case) were stable across repeated runs; only borderline accounts drifted between adjacent recommendations. Verification should check for this kind of stability, not exact text match.
- **This is a risk score, not a full health score.** Every component measures downside (usage decline, tickets, non-payment, churn signal). Expansion/upsell/advocacy signals are out of scope here — an intentional boundary, not an oversight. A natural v2 direction.
- **Band thresholds are calibrated against this 8-account sample**, not a large population — see the comment in `formula.py::band()` and `docs/methodology.md` for why an even three-way split doesn't work given the weight distribution.

## Testing

```bash
pytest tests/ -v
```

Covers the deterministic scoring formula only (weights sum to 1, monotonicity, reproducibility, band boundaries). The LLM-touching steps (extraction, synthesis) are exercised via the real end-to-end run rather than mocked — see `run.py` output for cost/timing evidence from an actual run.
