"""Serializes pipeline output to/from JSON.

This stands in for what would be a scheduled batch job writing to a shared
database/object store in production: the pipeline runs once (e.g. daily),
and all downstream viewers (the Streamlit app, or any other consumer) read
the same snapshot rather than triggering new LLM calls per viewer. A flat
JSON file is a reasonable proxy for that at demo scale; at real scale
(thousands of accounts, concurrent viewers, day-over-day trend) this would
be a database table instead, so the app can query/filter at scale and keep
history rather than only ever seeing the latest snapshot.
"""
import json
from dataclasses import asdict

from .pipeline import AccountResult


def results_to_dict(results: list[AccountResult], rollup: dict) -> dict:
    return {
        "rollup": rollup,
        "accounts": [asdict(r) for r in results],
    }


def save_results(results: list[AccountResult], rollup: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(results_to_dict(results, rollup), f, indent=2)


def load_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
