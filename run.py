#!/usr/bin/env python3
"""Single entry point: run the full pipeline and render the static HTML report.

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

# Approximate Claude Sonnet 4.5 pricing, USD per million tokens.
PRICE_PER_M_INPUT = 3.0
PRICE_PER_M_OUTPUT = 15.0


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
    total_in = sum(c["input_tokens"] for c in log)
    total_out = sum(c["output_tokens"] for c in log)
    cost = (total_in / 1_000_000 * PRICE_PER_M_INPUT) + (total_out / 1_000_000 * PRICE_PER_M_OUTPUT)

    print(f"Scored {len(results)} accounts in {elapsed:.1f}s ({len(log)} LLM calls).")
    print(f"Est. cost: ${cost:.4f} (${cost / len(results):.4f} / account)")
    print(f"Report written to {os.path.abspath(OUTPUT_PATH)}")
    print(f"Results snapshot written to {os.path.abspath(RESULTS_JSON_PATH)}")


if __name__ == "__main__":
    main()
