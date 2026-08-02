"""Streamlit viewer for a cached scoring run (output/results.json).

Reads a shared snapshot rather than triggering live LLM calls per viewer —
this stands in for a scheduled daily batch job in production (see
src/scoring/serialize.py). Landing view is an executive KPI strip + a
filterable watchlist table; selecting an account drills into its full
scorecard. Styled as an internal tool, not a marketing page.
"""

import html
import json
import os

import streamlit as st

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "output", "results.json")

# Status palette — fixed roles, never themed. Icon + label always pairs with
# color; on the light surface these hexes are sub-3:1 as text, so they're
# used as dots/accents against primary-ink text, never as text color alone.
STATUS = {
    "red": {"hex": "#d03b3b", "tint": "#fbe9e9", "label": "At Risk"},
    "yellow": {"hex": "#fab219", "tint": "#fef6e3", "label": "Monitor"},
    "green": {"hex": "#0ca30c", "tint": "#e8f7e8", "label": "Low Risk"},
}
ACTION_LABEL = {
    "NO_ACTION": "No action",
    "CSM_CHECK_IN": "CSM check-in",
    "EXEC_ESCALATION": "Exec escalation",
}
ACTION_BAND = {  # which status color an action badge borrows
    "NO_ACTION": "green",
    "CSM_CHECK_IN": "yellow",
    "EXEC_ESCALATION": "red",
}

st.set_page_config(
    page_title="Client Health Scorecard",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        /* Solovis's own site uses Brandon Grotesque (a licensed Adobe/Typekit font
           we can't legally hotlink here). Inter — used across most fintech/
           financial dashboards (Stripe, trading platforms) — was chosen over
           a closer geometric match because it reads as more precise and
           data-serious, which fits this tool's register better. */

        :root {
            --ink-primary: #0b0b0b;
            --ink-secondary: #3d5568;
            --ink-muted: #6b8296;
            --surface: #ffffff;
            --surface-tint: #eaf6fb;
            --page: #eef1f4;
            --border: rgba(6,73,117,0.14);
            --accent: #0075A9;
            --accent-cyan: #00BFDF;
            --brand-navy: #064975;
            --on-page-text: var(--brand-navy);
            --on-page-muted: var(--ink-muted);
        }
        /* Apply the brand font broadly, but never to icon glyphs — Streamlit
           renders several icons (expander arrows, etc.) as ligature text in
           an icon font, and overriding font-family on those turns the glyph
           back into literal text. */
        html, body, .stApp,
        .stApp p, .stApp span, .stApp div, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        .stApp label, .stApp button, .stApp input, .stApp li, .stApp td, .stApp th {
            font-family: 'Inter', sans-serif;
        }
        .stApp [data-testid*="Icon" i], .stApp [class*="icon" i], .stApp svg, .stApp svg * {
            font-family: initial !important;
        }
        .stApp { background: var(--page) !important; }
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding-top: 0 !important; max-width: 1180px;}

        .st-key-watchlist, .st-key-watchlist > div {
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            padding: 6px 14px 14px 14px !important;
        }
        .st-key-watchlist label, .st-key-watchlist p { color: var(--ink-primary) !important; }

        .ch-header {
            background: var(--brand-navy);
            color: #ffffff;
            padding: 20px 28px;
            border-radius: 10px;
            margin: 18px 0 24px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .ch-header .eyebrow {
            font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
            color: #9aa3b2; margin-bottom: 3px;
        }
        .ch-header h1 {
            font-size: 30px; margin: 0; font-weight: 700; color: #ffffff;
        }
        .ch-status {
            font-size: 12px; color: #9aa3b2; display: flex; align-items: center; gap: 6px;
        }
        .ch-status .dot {
            width: 8px; height: 8px; border-radius: 50%; background: #0ca30c; display: inline-block;
        }

        .kpi-row {display: flex; gap: 12px; margin-bottom: 22px; flex-wrap: wrap;}
        .kpi-card {
            flex: 1; min-width: 150px; background: var(--surface);
            border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px;
        }
        .kpi-card .label {
            font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em;
            color: var(--ink-muted); margin-bottom: 6px;
        }
        .kpi-card .value {
            font-size: 28px; font-weight: 600; color: var(--ink-primary);
            font-variant-numeric: tabular-nums; line-height: 1;
        }
        .kpi-card.status-red .value { color: #d03b3b; }
        .kpi-card .sub { font-size: 12px; color: var(--ink-secondary); margin-top: 4px; }

        .badge {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
            color: var(--ink-primary);
        }
        .badge .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

        .section-title {
            font-size: 24px; font-weight: 700; color: var(--on-page-text);
            text-align: center; margin: 8px 0 16px 0;
        }
        .section-caption { font-size: 13px; color: var(--on-page-muted); margin-top: -8px; margin-bottom: 16px; }

        table.ch-table {
            width: 100%; border-collapse: collapse; font-size: 13px;
            background: var(--surface); border-radius: 8px; overflow: hidden;
        }
        table.ch-table th {
            text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
            color: var(--ink-muted); font-weight: 600; padding: 8px 12px; border-bottom: 1px solid var(--border);
        }
        table.ch-table td {
            padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--ink-primary);
        }
        table.ch-table tr:hover td { background: var(--surface-tint); }
        table.ch-table .num { font-variant-numeric: tabular-nums; text-align: right; }
        table.ch-table .acct-name { font-weight: 600; }

        .detail-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 20px 24px; margin-bottom: 16px;
        }
        .detail-card .meta { color: var(--ink-secondary); font-size: 13px; margin-bottom: 10px; }
        .detail-card .narrative { font-size: 14px; line-height: 1.55; color: var(--ink-primary); margin-top: 12px; }
        .footnote { font-size: 12px; color: var(--on-page-muted); margin-top: 24px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(band: str) -> str:
    s = STATUS[band]
    return (
        f'<span class="badge" style="background:{s["tint"]}">'
        f'<span class="dot" style="background:{s["hex"]}"></span>{s["label"]}</span>'
    )


def action_badge(action: str) -> str:
    band = ACTION_BAND[action]
    s = STATUS[band]
    return (
        f'<span class="badge" style="background:{s["tint"]}">'
        f'<span class="dot" style="background:{s["hex"]}"></span>{ACTION_LABEL[action]}</span>'
    )


@st.cache_data
def load_snapshot(path: str, mtime: float) -> dict:
    """mtime busts the cache whenever the file actually changes — cache_data
    keyed on path alone would keep serving a stale snapshot after a deploy
    that updates the file without a full app restart. (Streamlit excludes
    underscore-prefixed args from the cache key, so this must NOT be
    underscore-prefixed — it needs to participate in the key.)"""
    with open(path) as f:
        return json.load(f)


inject_css()

if not os.path.exists(RESULTS_PATH):
    st.error(
        f"No results snapshot found at `{RESULTS_PATH}`.\n\n"
        "Run `python run.py` first to score the portfolio and generate one."
    )
    st.stop()

data = load_snapshot(RESULTS_PATH, os.path.getmtime(RESULTS_PATH))
rollup = data["rollup"]
accounts = data["accounts"]

# --- Header ---
st.markdown(
    """
    <div class="ch-header">
        <div>
            <div class="eyebrow">Client Success</div>
            <h1>Client Health Scorecard</h1>
        </div>
        <div class="ch-status"><span class="dot"></span>Snapshot current · v1.0</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Executive KPI strip ---
n_escalations = len(rollup["exec_escalation_accounts"])
kpi_html = f"""
<div class="kpi-row">
    <div class="kpi-card">
        <div class="label">Portfolio</div>
        <div class="value">{rollup["total_accounts"]}</div>
        <div class="sub">accounts</div>
    </div>
    <div class="kpi-card">
        <div class="label">Avg health score</div>
        <div class="value">{rollup["avg_health_score"]}</div>
        <div class="sub">out of 100</div>
    </div>
    <div class="kpi-card">
        <div class="label">At Risk</div>
        <div class="value" style="color:{STATUS["red"]["hex"]}">{rollup["band_counts"]["red"]}</div>
        <div class="sub">accounts</div>
    </div>
    <div class="kpi-card">
        <div class="label">Monitor</div>
        <div class="value" style="color:#b8860b">{rollup["band_counts"]["yellow"]}</div>
        <div class="sub">accounts</div>
    </div>
    <div class="kpi-card">
        <div class="label">Low Risk</div>
        <div class="value" style="color:{STATUS["green"]["hex"]}">{rollup["band_counts"]["green"]}</div>
        <div class="sub">accounts</div>
    </div>
    <div class="kpi-card{" status-red" if n_escalations else ""}">
        <div class="label">Exec escalation</div>
        <div class="value">{n_escalations}</div>
        <div class="sub">{html.escape(", ".join(rollup["exec_escalation_accounts"])) if n_escalations else "none"}</div>
    </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)

# --- Filterable watchlist ---
st.markdown(
    '<div class="section-title">Portfolio Watchlist</div>', unsafe_allow_html=True
)

watchlist = st.container(border=True, key="watchlist")
with watchlist:
    filter_col1, filter_col2 = st.columns(2)
    band_filter = filter_col1.multiselect(
        "Filter by risk level",
        options=["red", "yellow", "green"],
        default=["red", "yellow", "green"],
        format_func=lambda v: STATUS[v]["label"],
    )
    action_filter = filter_col2.multiselect(
        "Filter by recommended action",
        options=list(ACTION_LABEL.keys()),
        default=list(ACTION_LABEL.keys()),
        format_func=lambda v: ACTION_LABEL[v],
    )

    filtered = [
        a
        for a in accounts
        if a["band"] in band_filter and a["action_recommendation"] in action_filter
    ]
    filtered.sort(key=lambda a: a["risk_score"], reverse=True)

    rows_html = "".join(
        f"""<tr>
            <td>{status_badge(a["band"])}</td>
            <td class="acct-name">{html.escape(a["account_name"])}</td>
            <td class="num">{a["health_score"]}</td>
            <td>{action_badge(a["action_recommendation"])}</td>
            <td class="num">{a["structured"]["days_to_renewal"]}</td>
        </tr>"""
        for a in filtered
    )
    table_html = f"""
    <table class="ch-table">
        <thead><tr>
            <th>Risk Level</th><th>Account</th><th style="text-align:right">Health</th>
            <th>Recommended action</th><th style="text-align:right">Renewal (days)</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-caption">Showing {len(filtered)} of {len(accounts)} accounts, sorted by risk.</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- Account detail ---
st.markdown('<div class="section-title">Account Detail</div>', unsafe_allow_html=True)

if not filtered:
    st.info("No accounts match the current filters.")
    st.stop()

account_names = [a["account_name"] for a in filtered]
selected_name = st.selectbox(
    "Select an account", account_names, label_visibility="collapsed"
)
account = next(a for a in filtered if a["account_name"] == selected_name)

detail_col1, detail_col2 = st.columns([2.2, 1])

with detail_col1:
    st.markdown(
        f"""
        <div class="detail-card">
            <h3 style="margin:0 0 4px 0;">{html.escape(account["account_name"])}</h3>
            <div class="meta">{html.escape(account["plan_tier"])} · {html.escape(account["primary_contact_name"])} ·
                renewal in {account["structured"]["days_to_renewal"]} days</div>
            <div>{status_badge(account["band"])} {action_badge(account["action_recommendation"])}</div>
            <div class="narrative">{html.escape(account["narrative"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    breakdown_html = "".join(
        f"<li>{row['name'].replace('_', ' ').capitalize()} — {row['actual']:.1f} / {row['max']:.0f}</li>"
        for row in account["score_breakdown"]
    )
    st.markdown(
        f'<div class="detail-card"><b>Risk Factors</b><ul style="margin:8px 0 0 0; padding-left:20px;">'
        f"{breakdown_html}</ul></div>",
        unsafe_allow_html=True,
    )

with detail_col2:
    st.markdown(
        f"""
        <div class="kpi-card" style="margin-bottom:12px;">
            <div class="label">Health score</div>
            <div class="value">{account["health_score"]}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Risk score</div>
            <div class="value">{account["risk_score"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="footnote">For internal CSM and leadership use only — not client-facing. '
    "All recommendations require human review before action is taken.</div>",
    unsafe_allow_html=True,
)
