"""Streamlit viewer for a cached scoring run (output/results.json).

Reads a shared snapshot rather than triggering live LLM calls per viewer —
this stands in for a scheduled daily batch job in production (see
src/scoring/serialize.py). Landing view is a filterable portfolio table;
selecting an account drills into its full scorecard.
"""
import json
import os

import streamlit as st

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "output", "results.json")

BAND_COLOR = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
ACTION_LABEL = {
    "NO_ACTION": "No action",
    "CSM_CHECK_IN": "CSM check-in",
    "EXEC_ESCALATION": "Exec escalation",
}

st.set_page_config(page_title="Client Health Scorecard", layout="wide")


@st.cache_data
def load_snapshot(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


if not os.path.exists(RESULTS_PATH):
    st.error(
        f"No results snapshot found at `{RESULTS_PATH}`.\n\n"
        "Run `python run.py` first to score the portfolio and generate one."
    )
    st.stop()

data = load_snapshot(RESULTS_PATH)
rollup = data["rollup"]
accounts = data["accounts"]

st.title("Client Health Scorecard")
st.caption("Synthetic portfolio snapshot — same data every viewer sees until the next scheduled run.")

# --- Portfolio summary ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Accounts", rollup["total_accounts"])
col2.metric("Avg health score", rollup["avg_health_score"])
col3.metric("Red", rollup["band_counts"]["red"])
col4.metric("Yellow", rollup["band_counts"]["yellow"])
col5.metric("Green", rollup["band_counts"]["green"])

if rollup["exec_escalation_accounts"]:
    st.warning("**Exec escalation:** " + ", ".join(rollup["exec_escalation_accounts"]))

st.divider()

# --- Filterable summary table ---
st.subheader("Portfolio")

filter_col1, filter_col2 = st.columns(2)
band_filter = filter_col1.multiselect(
    "Filter by band", options=["red", "yellow", "green"], default=["red", "yellow", "green"],
)
action_filter = filter_col2.multiselect(
    "Filter by recommended action",
    options=list(ACTION_LABEL.keys()),
    default=list(ACTION_LABEL.keys()),
    format_func=lambda v: ACTION_LABEL[v],
)

filtered = [
    a for a in accounts
    if a["band"] in band_filter and a["action_recommendation"] in action_filter
]
filtered.sort(key=lambda a: a["risk_score"], reverse=True)

table_rows = [
    {
        "": BAND_COLOR[a["band"]],
        "Account": a["account_name"],
        "Health score": a["health_score"],
        "Band": a["band"],
        "Recommended action": ACTION_LABEL[a["action_recommendation"]],
        "Renewal in (days)": a["structured"]["days_to_renewal"],
    }
    for a in filtered
]
st.dataframe(table_rows, use_container_width=True, hide_index=True)
st.caption(f"Showing {len(filtered)} of {len(accounts)} accounts.")

st.divider()

# --- Account detail ---
st.subheader("Account detail")

if not filtered:
    st.info("No accounts match the current filters.")
    st.stop()

account_names = [a["account_name"] for a in filtered]
selected_name = st.selectbox("Select an account", account_names)
account = next(a for a in filtered if a["account_name"] == selected_name)

detail_col1, detail_col2 = st.columns([2, 1])

with detail_col1:
    st.markdown(f"### {account['account_name']}")
    st.caption(
        f"{account['plan_tier']} · {account['primary_contact_name']} · "
        f"renewal in {account['structured']['days_to_renewal']} days"
    )
    st.markdown(f"**{BAND_COLOR[account['band']]} {account['band'].upper()} — "
                f"{ACTION_LABEL[account['action_recommendation']]}**")
    st.write(account["narrative"])

    st.markdown("**Top drivers**")
    for name, pts in account["top_drivers"]:
        st.write(f"- {name.replace('_', ' ')}: {pts:.1f} pts")

with detail_col2:
    st.metric("Health score", account["health_score"])
    st.metric("Risk score", account["risk_score"])

if account["extracted_items"]:
    with st.expander("Evidence (tickets & notes reviewed)"):
        for item in account["extracted_items"]:
            st.markdown(
                f"**[{item['source_type']}]** tone={item['risk_tone']}, theme={item['theme']}\n\n"
                f"> {item['text']}"
            )

st.divider()
st.caption("Internal CSM/leadership prep aid — not client-facing. Recommendations are surfaced for human review, not auto-executed.")
