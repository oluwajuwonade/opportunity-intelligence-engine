"""Streamlit front end for Opportunity Intelligence Engine."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.opportunity_engine import (
    ELIGIBILITY_STATUSES,
    OPPORTUNITY_TYPES,
    PIPELINE_STATUSES,
    SOURCE_TYPES,
    VERIFICATION_STATUSES,
    WORK_MODES,
    add_opportunity,
    delete_opportunity,
    init_db,
    list_opportunities,
    score_opportunity,
    update_status,
)

st.set_page_config(
    page_title="Opportunity Intelligence Engine",
    page_icon="OI",
    layout="wide",
)

DEFAULT_DB_PATH = Path(os.getenv("OPPORTUNITY_DB_PATH", "data/opportunities.db"))
init_db(DEFAULT_DB_PATH)

st.title("Opportunity Intelligence Engine")
st.caption(
    "A personal workspace for discovering, evaluating, and tracking jobs, "
    "freelance contracts, AI evaluation work, grants, and research opportunities."
)
st.info(
    "This app is a tracker, not a live listings feed. New records are unverified by "
    "default. Mark source evidence only after checking the page yourself; recheck "
    "details before applying."
)

records = list_opportunities(DEFAULT_DB_PATH)
scored_records = [
    {**record, **score_opportunity(record)} for record in records
]

tab_board, tab_add, tab_workflow = st.tabs(
    ["Opportunity board", "Add opportunity", "Workflow and scoring"]
)

with tab_board:
    total = len(scored_records)
    actionable = sum(
        record["status"] in {"Ready to apply", "Applied", "Interview"}
        for record in scored_records
    )
    verified_window = sum(
        record["verification_status"] == "Application window checked"
        for record in scored_records
    )
    passed_deadline = sum(
        record["deadline_state"] == "Deadline passed"
        for record in scored_records
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Tracked", total)
    metric_cols[1].metric("Actionable pipeline", actionable)
    metric_cols[2].metric("Window checked", verified_window)
    metric_cols[3].metric("Deadlines passed", passed_deadline)

    if not scored_records:
        st.subheader("Start your opportunity queue")
        st.write(
            "There are no records yet. Use Add opportunity to save a listing from "
            "an official employer, funder, research organisation, or trusted platform."
        )
    else:
        filter_cols = st.columns([2, 1, 1, 1])
        search = filter_cols[0].text_input(
            "Search title, organisation, or skill", key="search_text"
        ).strip().lower()
        type_filter = filter_cols[1].selectbox(
            "Opportunity type", ["All"] + list(OPPORTUNITY_TYPES)
        )
        eligibility_filter = filter_cols[2].selectbox(
            "Eligibility", ["All"] + list(ELIGIBILITY_STATUSES)
        )
        status_filter = filter_cols[3].selectbox(
            "Application status", ["All"] + list(PIPELINE_STATUSES)
        )

        visible = []
        for record in scored_records:
            searchable = " ".join(
                str(record.get(key) or "")
                for key in ("title", "organization", "skills", "notes")
            ).lower()
            if search and search not in searchable:
                continue
            if type_filter != "All" and record["opportunity_type"] != type_filter:
                continue
            if (
                eligibility_filter != "All"
                and record["eligibility_status"] != eligibility_filter
            ):
                continue
            if status_filter != "All" and record["status"] != status_filter:
                continue
            visible.append(record)

        visible.sort(key=lambda row: row["priority_score"], reverse=True)
        table_rows = []
        for record in visible:
            table_rows.append(
                {
                    "ID": record["id"],
                    "Title": record["title"],
                    "Organisation": record["organization"],
                    "Type": record["opportunity_type"],
                    "Mode": record["work_mode"],
                    "Eligibility": record["eligibility_status"],
                    "Skill match": record["skill_match"],
                    "Priority score": record["priority_score"],
                    "Deadline": record["deadline"] or "—",
                    "Deadline state": record["deadline_state"],
                    "Evidence": record["verification_status"],
                    "Source checked": record["source_checked_at"] or "—",
                    "Status": record["status"],
                }
            )
        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Open record details and update an application"):
            record_ids = [record["id"] for record in visible]
            if not record_ids:
                st.write("No records match the current filters.")
            else:
                selected_id = st.selectbox(
                    "Choose an opportunity",
                    record_ids,
                    format_func=lambda item_id: next(
                        (
                            f"#{row['id']} — {row['title']} | {row['organization']}"
                            for row in visible
                            if row["id"] == item_id
                        ),
                        str(item_id),
                    ),
                )
                chosen = next(row for row in visible if row["id"] == selected_id)
                st.write(f"**Source:** {chosen['source_url']}")
                if chosen.get("application_url"):
                    st.write(f"**Application page:** {chosen['application_url']}")
                st.write(f"**Eligible countries:** {chosen['eligible_countries']}")
                st.write(f"**Skills:** {chosen['skills'] or 'Not specified'}")
                st.write(f"**Compensation:** {chosen['compensation_min'] or '—'} to {chosen['compensation_max'] or '—'} {chosen['currency']}")
                st.write(f"**Notes:** {chosen['notes'] or 'None'}")
                st.caption(
                    "Priority is a triage score, not an acceptance probability. "
                    "The score is zero for records marked ineligible or with a passed deadline."
                )

                current_status = chosen["status"]
                new_status = st.selectbox(
                    "Update application status",
                    PIPELINE_STATUSES,
                    index=PIPELINE_STATUSES.index(current_status),
                    key=f"status_{selected_id}",
                )
                if st.button("Save status", key=f"save_status_{selected_id}"):
                    update_status(DEFAULT_DB_PATH, selected_id, new_status)
                    st.success("Application status updated.")
                    st.rerun()

                confirm_delete = st.checkbox(
                    "I confirm I want to delete this opportunity",
                    key=f"confirm_delete_{selected_id}",
                )
                if st.button(
                    "Delete opportunity",
                    key=f"delete_{selected_id}",
                    disabled=not confirm_delete,
                ):
                    delete_opportunity(DEFAULT_DB_PATH, selected_id)
                    st.success("Opportunity deleted.")
                    st.rerun()

        csv_bytes = pd.DataFrame(records).to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download all records as CSV",
            data=csv_bytes,
            file_name="opportunities.csv",
            mime="text/csv",
        )

with tab_add:
    st.subheader("Add a sourced opportunity")
    st.write(
        "Enter the source page you found. The app will not fetch or verify the listing "
        "automatically in this MVP."
    )

    with st.form("new_opportunity", clear_on_submit=True):
        title = st.text_input("Opportunity title *")
        organization = st.text_input("Organisation or client *")
        col_a, col_b, col_c = st.columns(3)
        opportunity_type = col_a.selectbox("Type", OPPORTUNITY_TYPES)
        work_mode = col_b.selectbox("Work mode", WORK_MODES)
        source_type = col_c.selectbox("Source type", SOURCE_TYPES)

        eligible_countries = st.text_input(
            "Eligible countries / regions",
            value="Nigeria; confirm requirements",
            help="Use the wording from the published requirements. Separate multiple regions with semicolons.",
        )
        skills = st.text_input("Required or relevant skills")
        skill_match = st.slider(
            "Your estimated skill match (%)",
            min_value=0,
            max_value=100,
            value=50,
            help="Your own estimate, not an independently validated score.",
        )

        col_d, col_e, col_f = st.columns(3)
        eligibility_status = col_d.selectbox(
            "Eligibility assessment", ELIGIBILITY_STATUSES
        )
        currency = col_e.text_input("Compensation currency", value="USD").strip().upper()
        application_status = col_f.selectbox("Application status", PIPELINE_STATUSES)

        col_g, col_h = st.columns(2)
        compensation_min = col_g.number_input(
            "Minimum compensation (0 if unknown)",
            min_value=0.0,
            value=0.0,
            step=100.0,
        )
        compensation_max = col_h.number_input(
            "Maximum compensation (0 if unknown)",
            min_value=0.0,
            value=0.0,
            step=100.0,
        )

        has_deadline = st.checkbox("This opportunity has a published deadline")
        deadline_value = None
        if has_deadline:
            deadline_value = st.date_input(
                "Application deadline",
                value=date.today() + timedelta(days=14),
                min_value=date(2000, 1, 1),
            )

        source_url = st.text_input("Source URL *")
        application_url = st.text_input("Direct application URL (optional)")

        source_checked = st.checkbox(
            "I checked the source page and confirmed the listing details I entered"
        )
        window_checked = st.checkbox(
            "I also checked that the application window is open or the deadline has not passed",
            disabled=not source_checked,
        )
        source_checked_at = date.today() if source_checked else None
        if window_checked:
            verification_status = "Application window checked"
        elif source_checked:
            verification_status = "Source checked"
        else:
            verification_status = "Unverified"

        notes = st.text_area(
            "Notes and next action",
            placeholder="Eligibility evidence, required documents, follow-up date, or questions to resolve",
        )
        submitted = st.form_submit_button("Save opportunity")

    if submitted:
        if not title.strip() or not organization.strip() or not source_url.strip():
            st.error("Complete the title, organisation, and source URL fields.")
        else:
            opportunity = {
                "title": title,
                "organization": organization,
                "opportunity_type": opportunity_type,
                "work_mode": work_mode,
                "eligible_countries": eligible_countries,
                "skills": skills,
                "skill_match": skill_match,
                "eligibility_status": eligibility_status,
                "compensation_min": compensation_min or None,
                "compensation_max": compensation_max or None,
                "currency": currency or "USD",
                "deadline": deadline_value,
                "source_url": source_url,
                "application_url": application_url,
                "source_type": source_type,
                "source_checked_at": source_checked_at,
                "verification_status": verification_status,
                "status": application_status,
                "notes": notes,
            }
            try:
                new_id = add_opportunity(DEFAULT_DB_PATH, opportunity)
                st.success(f"Saved opportunity #{new_id}.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

with tab_workflow:
    st.subheader("How to use the tracker")
    st.markdown(
        """
1. Capture a listing only after identifying its source URL.
2. Check the source page, country requirements, work arrangement, skills, compensation, and deadline.
3. Record eligibility conservatively. Use **Potentially eligible** or **Not checked** when evidence is incomplete.
4. Mark source evidence only after you have checked the page; repeat that check before applying.
5. Review high-priority records, choose a next action, and maintain the application status.
6. Export a CSV backup periodically.
"""
    )
    st.subheader("How the priority score works")
    st.markdown(
        """
- **Skill match:** up to 50 points, based on your estimate.
- **Eligibility:** up to 30 points; Eligible = 100, Potentially eligible = 65, Not checked = 25, Ineligible = 0.
- **Evidence freshness:** up to 20 points; Application window checked = 100, Source checked = 70, Unverified = 0, multiplied by a freshness factor.
- Source checks from the last 7 days keep full evidence weight; 8–30 days keep half; older or future-dated checks get zero evidence weight.
- A passed deadline or an Ineligible assessment forces the score to zero.
"""
    )
    st.warning(
        "This is a heuristic for sorting your workload. It is not a success probability, "
        "a substitute for eligibility review, or confirmation that a listing is still open. "
        "Recheck source evidence before taking action."
    )
    st.subheader("Current storage")
    st.write(f"Database path on this machine: {DEFAULT_DB_PATH}")
    st.write(
        "The repository does not send your records to a third party. If you deploy it "
        "on a public host, protect access and configure durable storage before entering "
        "private application notes."
    )
