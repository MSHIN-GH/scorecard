# Client Health Scorecard

A code-based pipeline that scores client accounts on churn/downsell risk, combining deterministic structured metrics with LLM-extracted signals from unstructured notes. Built as a follow-up exploration after a conversation about quantifying client health — synthetic data throughout, no real client data used.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python3 scripts/generate_synthetic_data.py   # writes data/*.csv (already committed, safe to re-run)
python3 run.py                                # runs the full pipeline, writes output/report.html + output/results.json
```

Open `output/report.html` — no server needed, it's a self-contained static file. A pre-generated copy is already committed so the report is viewable without running anything.

### Interactive viewer (optional)

```bash
streamlit run app.py
```

Opens at `localhost:8501`. Reads the cached `output/results.json` snapshot rather than making live LLM calls — landing view is a portfolio table filterable by band and recommended action, with a dropdown to drill into any account's full scorecard and underlying evidence. This is local-only (no public URL); it stands in for what a scheduled daily batch job + shared dashboard would look like in production — see the note in `src/scoring/serialize.py` for why a flat JSON snapshot is a demo-scale stand-in for a database table.

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
output assembly → static HTML report + results.json snapshot → optional Streamlit viewer reads the snapshot
```

- **Structured extraction** (`src/scoring/features.py`) — usage trend, ticket velocity/severity, renewal proximity, payment delinquency, engagement recency, contract trend, contact turnover. Pure functions, no LLM.
- **Unstructured extraction** (`src/scoring/extraction.py`) — one narrow, structured-output classification call per ticket/note, run independently and in parallel (`ThreadPoolExecutor`). Extraction, not reasoning: each call sees one input in isolation.
- **Deterministic score** (`src/scoring/formula.py`) — a weighted formula combining all of the above into a 0–100 risk score, band, and top drivers. Fully explainable and reproducible: same inputs always produce the same score. See `docs/methodology.md` for the full weighting rationale.
- **Reasoning/synthesis layer** (`src/scoring/synthesis.py`) — the one point in the pipeline where the LLM sees an account's combined evidence together, and judges whether it reinforces or contradicts the computed score. Outputs a structured schema (narrative + `action_recommendation` enum: `NO_ACTION` / `CSM_CHECK_IN` / `EXEC_ESCALATION`) — the enum is what would make this machine-actionable for a downstream workflow (a Salesforce task, a Slack alert). It's a recommendation surfaced for CSM review, not an autonomous trigger — no auto-execution logic exists in this codebase.

This is a fan-out/fan-in pipeline, not a multi-agent system — the LLM touches exactly two narrow, bounded points (extraction, synthesis), and nothing talks to anything else in between.

## Micro-benchmark

Measured on the full 8-account synthetic dataset (24 LLM calls: 16 extraction + 8 synthesis):

| Metric | Value |
|---|---|
| Avg. LLM cost per account | ~$0.015 |
| Avg. wall time per account | ~12s |
| Total cost, full portfolio run | ~$0.12 |

Cost scales linearly with account count; at Solovis's estimated ~150-160 accounts, a full portfolio run would cost roughly $2–3 in API spend. Wall time could be parallelized further across accounts (currently parallel *within* an account's extraction calls, sequential *across* accounts) if a production version needed to run faster than the ~12s/account rate shown here.

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
    html_report.py            renders results to static HTML
templates/
  report.html.jinja      HTML report template
tests/
  test_formula.py        unit tests for the deterministic scoring formula
output/
  report.html            pre-generated sample output (committed)
  results.json           cached snapshot used by the Streamlit viewer (committed)
run.py                   single entry point: run pipeline + render report + write snapshot
app.py                   optional interactive viewer (streamlit run app.py)
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
