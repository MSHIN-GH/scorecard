"""Generates synthetic data/*.csv files. Deterministic — same output every run.

Eight accounts span the risk spectrum, including one deliberately contradictory
case (Highline Capital) where a raw metric looks bad but context says otherwise,
to give the LLM reasoning layer something real to reconcile.
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

ACCOUNTS = [
    {
        "account_id": "ACC-001",
        "account_name": "Ironwood Financial",
        "plan_tier": "Enterprise",
        "primary_contact_name": "David Ruiz",
        "contact_changed_date": "",
        "renewal_date": "2027-05-15",
        "last_meeting_date": "2026-07-22",
        "usage_weekly": [98, 101, 103, 100, 108, 112, 109, 115],
        "contract_trend_pct": 5.0,
        "invoice_overdue_days": 0,
        "tickets": [
            {"ticket_id": "T-1001", "opened_date": "2026-06-10", "status": "closed", "severity": "low",
             "body_text": "Question about exporting a custom report to PDF. Resolved same day."},
        ],
        "notes": [
            {"date": "2026-07-22", "author": "CSM", "note_text": "Team is happy with the reporting module. Asked about adding the risk-analytics add-on next quarter."},
        ],
    },
    {
        "account_id": "ACC-002",
        "account_name": "Meridian Advisors",
        "plan_tier": "Enterprise",
        "primary_contact_name": "Karen Ellis",
        "contact_changed_date": "",
        "renewal_date": "2026-09-10",
        "last_meeting_date": "2026-06-12",
        "usage_weekly": [205, 198, 210, 187, 130, 118, 105, 97],
        "contract_trend_pct": 0.0,
        "invoice_overdue_days": 0,
        "tickets": [
            {"ticket_id": "T-2001", "opened_date": "2026-07-05", "status": "open", "severity": "high",
             "body_text": "Users unable to log in via SSO since Tuesday. Blocking daily reporting workflow. No update in 4 days."},
            {"ticket_id": "T-2002", "opened_date": "2026-07-18", "status": "open", "severity": "high",
             "body_text": "Second team also reporting SSO login failures. Escalating internally, growing frustrated."},
            {"ticket_id": "T-2003", "opened_date": "2026-07-20", "status": "open", "severity": "medium",
             "body_text": "Dashboard load times much slower than usual this week."},
        ],
        "notes": [
            {"date": "2026-06-12", "author": "CSM", "note_text": "Standard check-in, no concerns raised at the time."},
        ],
    },
    {
        "account_id": "ACC-003",
        "account_name": "Beacon Hill Partners",
        "plan_tier": "Growth",
        "primary_contact_name": "Sarah Kim",
        "contact_changed_date": "2026-07-10",
        "renewal_date": "2026-12-28",
        "last_meeting_date": "2026-07-24",
        "usage_weekly": [148, 152, 145, 150, 140, 143, 138, 141],
        "contract_trend_pct": 0.0,
        "invoice_overdue_days": 0,
        "tickets": [
            {"ticket_id": "T-3001", "opened_date": "2026-07-15", "status": "open", "severity": "medium",
             "body_text": "New admin asking how to pull the quarterly allocation report — previous admin used to run this manually."},
        ],
        "notes": [
            {"date": "2026-07-24", "author": "CSM", "note_text": "New admin Sarah Kim is still ramping up. Asked several basic navigation questions and seems unfamiliar with the reporting workflows the prior contact had set up."},
        ],
    },
    {
        "account_id": "ACC-004",
        "account_name": "Windward Asset Management",
        "plan_tier": "Enterprise",
        "primary_contact_name": "Tom Bradley",
        "contact_changed_date": "",
        "renewal_date": "2027-02-01",
        "last_meeting_date": "2026-07-08",
        "usage_weekly": [120, 118, 122, 119, 121, 117, 120, 118],
        "contract_trend_pct": 0.0,
        "invoice_overdue_days": 50,
        "tickets": [],
        "notes": [
            {"date": "2026-07-08", "author": "CSM", "note_text": "Discussed renewal terms, no product concerns raised. They mentioned invoice processing delays on their end due to an internal AP backlog, expect it resolved this month."},
        ],
    },
    {
        "account_id": "ACC-005",
        "account_name": "Cascade Investment Group",
        "plan_tier": "Growth",
        "primary_contact_name": "Linda Park",
        "contact_changed_date": "",
        "renewal_date": "2026-11-05",
        "last_meeting_date": "2026-05-20",
        "usage_weekly": [92, 88, 90, 85, 80, 76, 74, 75],
        "contract_trend_pct": -15.0,
        "invoice_overdue_days": 0,
        "tickets": [
            {"ticket_id": "T-5001", "opened_date": "2026-07-01", "status": "open", "severity": "low",
             "body_text": "Minor formatting issue in exported CSV, low priority."},
        ],
        "notes": [
            {"date": "2026-05-20", "author": "CSM", "note_text": "Have not been able to connect with Linda in over two months despite three outreach attempts."},
        ],
    },
    {
        "account_id": "ACC-006",
        "account_name": "Highline Capital",
        "plan_tier": "Enterprise",
        "primary_contact_name": "James Okafor",
        "contact_changed_date": "",
        "renewal_date": "2027-04-18",
        "last_meeting_date": "2026-07-20",
        "usage_weekly": [310, 295, 305, 290, 245, 230, 220, 215],
        "contract_trend_pct": 20.0,
        "invoice_overdue_days": 0,
        "tickets": [],
        "notes": [
            {"date": "2026-07-20", "author": "CSM", "note_text": "Client is evaluating rolling the platform out to two additional teams next quarter. The recent usage dip is attributed to a temporary staffing gap on their analytics team, expected to resolve by next month. No concerns raised."},
        ],
    },
    {
        "account_id": "ACC-007",
        "account_name": "Stonegate Partners",
        "plan_tier": "Enterprise",
        "primary_contact_name": "Priya Nair",
        "contact_changed_date": "2026-06-25",
        "renewal_date": "2026-09-28",
        "last_meeting_date": "2026-06-02",
        "usage_weekly": [180, 175, 190, 165, 140, 130, 122, 126],
        "contract_trend_pct": 0.0,
        "invoice_overdue_days": 0,
        "tickets": [
            {"ticket_id": "T-7001", "opened_date": "2026-06-30", "status": "open", "severity": "high",
             "body_text": "Reporting engine crashing on large portfolios, unresolved for over two weeks. Team is frustrated and has started evaluating alternative platforms, including a named competitor, due to slow issue resolution."},
            {"ticket_id": "T-7002", "opened_date": "2026-07-15", "status": "open", "severity": "medium",
             "body_text": "Follow-up requesting status update, no response yet from support."},
        ],
        "notes": [],
    },
    {
        "account_id": "ACC-008",
        "account_name": "Fairview Wealth Partners",
        "plan_tier": "Growth",
        "primary_contact_name": "Mark Alston",
        "contact_changed_date": "",
        "renewal_date": "2026-11-30",
        "last_meeting_date": "2026-06-27",
        "usage_weekly": [140, 137, 142, 138, 130, 128, 126, 124],
        "contract_trend_pct": 0.0,
        "invoice_overdue_days": 10,
        "tickets": [
            {"ticket_id": "T-8001", "opened_date": "2026-07-12", "status": "open", "severity": "medium",
             "body_text": "Requesting clarification on how allocation drift is calculated in the monthly report."},
        ],
        "notes": [
            {"date": "2026-06-27", "author": "CSM", "note_text": "Routine check-in. Generally positive, no major issues flagged."},
        ],
    },
]

REPORT_DATE = "2026-08-01"


def write_crm():
    path = os.path.join(DATA_DIR, "crm.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_id", "account_name", "plan_tier", "primary_contact_name",
                    "contact_changed_date", "renewal_date", "last_meeting_date"])
        for a in ACCOUNTS:
            w.writerow([a["account_id"], a["account_name"], a["plan_tier"], a["primary_contact_name"],
                        a["contact_changed_date"], a["renewal_date"], a["last_meeting_date"]])


def write_usage():
    path = os.path.join(DATA_DIR, "usage.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_id", "week_index", "active_users"])
        for a in ACCOUNTS:
            for i, v in enumerate(a["usage_weekly"], start=1):
                w.writerow([a["account_id"], i, v])


def write_billing():
    path = os.path.join(DATA_DIR, "billing.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_id", "invoice_overdue_days", "contract_trend_pct"])
        for a in ACCOUNTS:
            w.writerow([a["account_id"], a["invoice_overdue_days"], a["contract_trend_pct"]])


def write_tickets():
    path = os.path.join(DATA_DIR, "tickets.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticket_id", "account_id", "opened_date", "status", "severity", "body_text"])
        for a in ACCOUNTS:
            for t in a["tickets"]:
                w.writerow([t["ticket_id"], a["account_id"], t["opened_date"], t["status"],
                            t["severity"], t["body_text"]])


def write_notes():
    path = os.path.join(DATA_DIR, "notes.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_id", "date", "author", "note_text"])
        for a in ACCOUNTS:
            for n in a["notes"]:
                w.writerow([a["account_id"], n["date"], n["author"], n["note_text"]])


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    write_crm()
    write_usage()
    write_billing()
    write_tickets()
    write_notes()
    print(f"Wrote synthetic data for {len(ACCOUNTS)} accounts to {os.path.abspath(DATA_DIR)}")
