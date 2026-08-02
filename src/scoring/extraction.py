"""Step 3: unstructured signal extraction.

One structured-output call per account, classifying every one of that
account's tickets/notes together in a single request. This is still
extraction, not reasoning: each item is classified independently within the
batch (the model is instructed not to let one item's content influence
another's classification), it just avoids paying the ~700-token fixed
schema/prompt overhead once per document instead of once per account. Runs
on Haiku — a narrow classification task doesn't need Sonnet-tier reasoning,
which is reserved for the synthesis step that actually reasons across
combined evidence.
"""
from enum import Enum

from pydantic import BaseModel, Field

from .llm_client import get_client, timed_call, EXTRACTION_MODEL


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


_BATCH_TOOL_SCHEMA = {
    "name": "classify_texts",
    "description": (
        "Classify each provided support ticket or CSM note independently for "
        "client-health risk signal. Return exactly one classification per item, "
        "matched by id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Echo the item's id exactly."},
                        "risk_tone": {"type": "string", "enum": [t.value for t in RiskTone]},
                        "theme": {"type": "string", "enum": [t.value for t in Theme]},
                        "risk_flag": {"type": "boolean"},
                    },
                    "required": ["id", "risk_tone", "theme", "risk_flag"],
                },
            },
        },
        "required": ["classifications"],
    },
}


def classify_texts_batch(items: list[tuple[str, str, str]]) -> dict[str, TextClassification]:
    """items: list of (id, source_type, text). Returns {id: TextClassification}.

    One call for the whole batch, but each item is classified on its own
    merits — the prompt explicitly instructs the model not to let one item's
    tone or content influence another's classification.
    """
    if not items:
        return {}

    client = get_client()

    item_lines = "\n\n".join(
        f'Item id="{item_id}" ({source_type}):\n{text}'
        for item_id, source_type, text in items
    )
    prompt = (
        "Classify each of the following items independently for client-health risk "
        "signal. Each item is a separate support ticket or CSM note — evaluate each "
        "on its own content only; do not let one item's tone or theme influence "
        "another's classification. Return one classification per item, with the id "
        "field matching exactly.\n\n" + item_lines
    )

    def do_call():
        return client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=256 * len(items),
            tools=[_BATCH_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "classify_texts"},
            messages=[{"role": "user", "content": prompt}],
        )

    response = timed_call(f"extraction:batch:{len(items)}", do_call)
    tool_input = next(b.input for b in response.content if b.type == "tool_use")

    results = {}
    for entry in tool_input["classifications"]:
        results[entry["id"]] = TextClassification(
            risk_tone=entry["risk_tone"],
            theme=entry["theme"],
            risk_flag=entry["risk_flag"],
        )
    return results
