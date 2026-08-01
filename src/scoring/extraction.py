"""Step 3: unstructured signal extraction.

One narrow, structured-output LLM call per ticket/note, independent of all
others (no cross-talk). This is extraction, not reasoning — each call sees
exactly one input in isolation and classifies it.
"""
from enum import Enum

from pydantic import BaseModel, Field

from .llm_client import get_client, timed_call, MODEL


class RiskTone(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class Theme(str, Enum):
    competitor_mention = "competitor_mention"
    champion_unfamiliar = "champion_unfamiliar"
    blocking_issue = "blocking_issue"
    positive_expansion_signal = "positive_expansion_signal"
    none = "none"


class TextClassification(BaseModel):
    risk_tone: RiskTone
    theme: Theme = Field(description="The single most relevant theme, or 'none'")
    risk_flag: bool = Field(description="True if this item alone should raise concern")


_TOOL_SCHEMA = {
    "name": "classify_text",
    "description": "Classify a single support ticket or CSM note for client-health risk signal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "risk_tone": {"type": "string", "enum": [t.value for t in RiskTone]},
            "theme": {"type": "string", "enum": [t.value for t in Theme]},
            "risk_flag": {"type": "boolean"},
        },
        "required": ["risk_tone", "theme", "risk_flag"],
    },
}


def classify_text(text: str, source_type: str) -> TextClassification:
    """source_type is 'ticket' or 'note' — included only as context, not branching logic."""
    client = get_client()

    def do_call():
        return client.messages.create(
            model=MODEL,
            max_tokens=256,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "classify_text"},
            messages=[{
                "role": "user",
                "content": (
                    f"Classify this {source_type} text for client-health risk signal. "
                    f"Text:\n\n{text}"
                ),
            }],
        )

    response = timed_call(f"extraction:{source_type}", do_call)
    tool_input = next(b.input for b in response.content if b.type == "tool_use")
    return TextClassification(**tool_input)
