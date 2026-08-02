#!/usr/bin/env python3
"""Single entry point: run the full pipeline and write the results snapshot
that app.py (the Streamlit viewer) reads.

Usage:
    python run.py

Requires ANTHROPIC_API_KEY to be set (see .env.example).
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from scoring.pipeline import run_pipeline, portfolio_rollup  # noqa: E402
from scoring.llm_client import call_log  # noqa: E402
from scoring.serialize import save_results  # noqa: E402
from render.html_report import render_html  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "report.html")
RESULTS_JSON_PATH = os.path.join(OUTPUT_DIR, "results.json")

# USD per million tokens, by model family. Priced per-call from the actual
# model that served each request (response.model), not a single flat rate —
# extraction runs on Haiku, synthesis on Sonnet, and they price differently.
PRICING_PER_M = {
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
}


def _price_for_model(model: str) -> tuple[float, float]:
    for key, prices in PRICING_PER_M.items():
        if key in model:
            return prices
    return PRICING_PER_M["sonnet"]  # conservative fallback


def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if value and key not in os.environ:
                os.environ[key] = value


def main():
    _load_dotenv()

    start = time.monotonic()
    results = run_pipeline()
    elapsed = time.monotonic() - start

    rollup = portfolio_rollup(results)
    render_html(results, rollup, OUTPUT_PATH)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_results(results, rollup, RESULTS_JSON_PATH)

    log = call_log()
    cost = 0.0
    for c in log:
        price_in, price_out = _price_for_model(c["model"])
        cost += c["input_tokens"] / 1_000_000 * price_in
        cost += c["output_tokens"] / 1_000_000 * price_out

    print(f"Scored {len(results)} accounts in {elapsed:.1f}s ({len(log)} LLM calls).")
    print(f"Est. cost: ${cost:.4f} (${cost / len(results):.4f} / account)")
    print(f"Report written to {os.path.abspath(OUTPUT_PATH)}")
    print(f"Results snapshot written to {os.path.abspath(RESULTS_JSON_PATH)}")


if __name__ == "__main__":
    main()
