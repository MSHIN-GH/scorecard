"""Thin wrapper around the Anthropic client, shared by extraction and synthesis."""
import os
import time

import anthropic

MODEL = "claude-sonnet-4-5"

_client = None
_call_log: list[dict] = []


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call_log() -> list[dict]:
    return _call_log


def record_call(label: str, input_tokens: int, output_tokens: int, latency_s: float) -> None:
    _call_log.append({
        "label": label,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_s": latency_s,
    })


def timed_call(label: str, fn):
    start = time.monotonic()
    response = fn()
    latency = time.monotonic() - start
    record_call(label, response.usage.input_tokens, response.usage.output_tokens, latency)
    return response
