"""Step 5: reasoning/synthesis layer.

Takes an account's full assembled evidence together — computed score,
component drivers, and extracted note/ticket signals — and reasons about
whether they reinforce or contradict each other. This is the one point in
the pipeline where the LLM sees combined evidence rather than a single
isolated input, and it produces a recommendation, not the score itself.
"""
from enum import Enum

from pydantic import BaseModel, Field

from .llm_client import get_client, timed_call, MODEL


class ActionRecommendation(str, Enum):
    no_action = "NO_ACTION"
    csm_check_in = "CSM_CHECK_IN"
    exec_escalation = "EXEC_ESCALATION"


class SynthesisResult(BaseModel):
    narrative: str = Field(description="1-3 sentence explanation a CSM could read cold")
    action_recommendation: ActionRecommendation


_TOOL_SCHEMA = {
    "name": "synthesize_account_risk",
    "description": "Reason across an account's combined structured and extracted evidence to produce an escalation recommendation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative": {"type": "string"},
            "action_recommendation": {"type": "string", "enum": [a.value for a in ActionRecommendation]},
        },
        "required": ["narrative", "action_recommendation"],
    },
}


def synthesize(account_name: str, risk_score: float, band: str, top_drivers: list[tuple[str, float]],
                evidence_summary: str) -> SynthesisResult:
    client = get_client()
    drivers_text = ", ".join(f"{name} ({weight:.1f} pts)" for name, weight in top_drivers)

    prompt = (
        f"Account: {account_name}\n"
        f"Computed risk score: {risk_score:.1f}/100 (band: {band})\n"
        f"Top score drivers: {drivers_text}\n\n"
        f"Additional evidence (from tickets and CSM notes, already classified):\n{evidence_summary}\n\n"
        "Consider whether this evidence reinforces or contradicts the computed score. "
        "A high score with corroborating negative signals warrants escalation. "
        "A concerning metric explained by context in the notes (e.g., a temporary, "
        "explained dip alongside clearly positive signals) may not. "
        "Do not just restate the number — reason about whether the full picture supports it. "
        "You are not deciding the final numeric score, only the recommended next action."
    )

    def do_call():
        return client.messages.create(
            model=MODEL,
            max_tokens=512,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "synthesize_account_risk"},
            messages=[{"role": "user", "content": prompt}],
        )

    response = timed_call("synthesis", do_call)
    tool_input = next(b.input for b in response.content if b.type == "tool_use")
    return SynthesisResult(**tool_input)
