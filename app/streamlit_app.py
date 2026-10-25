"""Dashboard for the unified data + a submission form linked to people by phone.

Run:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from unify.db import add_submission  # noqa: E402
from unify.normalize import normalize_email, normalize_phone  # noqa: E402
from unify.pipeline import Unifier  # noqa: E402
from unify.db import write_database  # noqa: E402
from unify.quality import ISSUE_TYPES  # noqa: E402

DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "unified.db"))
RAW_DIR = Path(os.getenv("RAW_DIR", ROOT / "data" / "raw"))
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

st.set_page_config(page_title="Data Unification & Quality Check", layout="wide")


def query(sql: str, params=()) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(sql, con, params=params)


def n8n_duplicate_check(phone: str) -> dict | None:
    """Ask the n8n workflow whether this phone was seen recently. Returns None if n8n isn't set up."""
    if not N8N_WEBHOOK_URL:
        return None
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json={"phone": phone}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}


st.title("Data Unification & Quality Check")

with st.sidebar:
    st.caption("Source files: job_portal.csv, gig_workers.csv, contacts.csv")
    if st.button("Re-run clean-up pipeline", type="primary") or not DB_PATH.exists():
        write_database(Unifier().run(RAW_DIR), DB_PATH)
        st.success("Pipeline finished")

people = query("SELECT * FROM people")
links = query("SELECT * FROM person_sources")
issues = query("SELECT * FROM quality_issues")
quarantine = query("SELECT * FROM quarantine")

tab_overview, tab_people, tab_issues, tab_quarantine, tab_submit = st.tabs(
    ["Overview", "People", "Data issues", "Quarantine", "New submission"])

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Source rows imported", len(links))
    c2.metric("Unique people", len(people))
    c3.metric("Found in 2+ sources", int((people["source_count"] > 1).sum()))
    c4.metric("Rows quarantined", len(quarantine))
    left, right = st.columns(2)
    left.subheader("Issues by type")
    left.bar_chart(issues["issue_code"].value_counts())
    right.subheader("How rows were matched")
    right.bar_chart(links["match_method"].value_counts())

with tab_people:
    search = st.text_input("Search by name, phone or email")
    shown = people
    if search:
        mask = people[["name", "phone", "email"]].apply(
            lambda col: col.fillna("").str.contains(search, case=False, regex=False)).any(axis=1)
        shown = people[mask]
    st.dataframe(shown, use_container_width=True, hide_index=True)
    pid = st.selectbox("See where a person came from", shown["person_id"]) if len(shown) else None
    if pid is not None:
        st.dataframe(links[links["person_id"] == pid], use_container_width=True, hide_index=True)

with tab_issues:
    st.dataframe(pd.DataFrame([{"issue_code": k, "severity": v[0], "action": v[1], "meaning": v[2]}
                               for k, v in ISSUE_TYPES.items()]), use_container_width=True, hide_index=True)
    sev = st.multiselect("Severity", ["high", "medium", "low"], default=["high", "medium", "low"])
    st.dataframe(issues[issues["severity"].isin(sev)], use_container_width=True, hide_index=True)

with tab_quarantine:
    st.write("These rows were **not** merged. Each one needs a person to check it.")
    st.dataframe(quarantine, use_container_width=True, hide_index=True)

with tab_submit:
    st.write("New entries are linked to an existing person by phone number, and repeats are flagged.")
    with st.form("submission", clear_on_submit=True):
        name = st.text_input("Name")
        phone_raw = st.text_input("Phone *")
        email_raw = st.text_input("Email")
        city = st.text_input("City")
        note = st.text_area("Note")
        sent = st.form_submit_button("Submit")
    if sent:
        phone = normalize_phone(phone_raw)
        if not phone:
            st.error("Please enter a valid 10-digit mobile number.")
        else:
            res = add_submission(DB_PATH, name.strip(), phone, normalize_email(email_raw), city.strip(), note.strip())
            if res["person"]:
                st.success(f"Linked to existing person #{res['person'][0]} {res['person'][1]} ({res['person'][2]})")
            else:
                st.info("New phone number: not linked to any existing person.")
            if res["is_duplicate"]:
                st.warning("Duplicate: this phone already submitted in the last 24 hours.")
            n8n = n8n_duplicate_check(phone)
            if n8n is not None:
                st.caption(f"n8n duplicate check: {n8n}")
    st.subheader("Recent submissions")
    st.dataframe(query("SELECT * FROM submissions ORDER BY submission_id DESC LIMIT 20"),
                 use_container_width=True, hide_index=True)
