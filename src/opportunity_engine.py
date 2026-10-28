"""Storage, validation, and prioritisation logic for opportunity records."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

OPPORTUNITY_TYPES = (
    "Remote job",
    "Freelance contract",
    "AI evaluation",
    "Grant or donation",
    "Research opportunity",
    "Bounty or project",
    "Other",
)
WORK_MODES = ("Remote", "Hybrid", "On-site", "Flexible", "Not specified")
ELIGIBILITY_STATUSES = ("Not checked", "Potentially eligible", "Eligible", "Ineligible")
VERIFICATION_STATUSES = ("Unverified", "Source checked", "Application window checked")
PIPELINE_STATUSES = (
    "Saved",
    "Review",
    "Ready to apply",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
)
SOURCE_TYPES = (
    "Official employer/organisation page",
    "Official platform listing",
    "Job board/aggregator",
    "Referral/other",
)

ELIGIBILITY_POINTS = {
    "Eligible": 100,
    "Potentially eligible": 65,
    "Not checked": 25,
    "Ineligible": 0,
}
VERIFICATION_POINTS = {
    "Unverified": 0,
    "Source checked": 70,
    "Application window checked": 100,
}

FIELDS = (
    "title",
    "organization",
    "opportunity_type",
    "work_mode",
    "eligible_countries",
    "skills",
    "skill_match",
    "eligibility_status",
    "compensation_min",
    "compensation_max",
    "currency",
    "deadline",
    "source_url",
    "application_url",
    "source_type",
    "source_checked_at",
    "verification_status",
    "status",
    "notes",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path) -> None:
    """Create the local opportunity table when it does not exist."""
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                organization TEXT NOT NULL,
                opportunity_type TEXT NOT NULL,
                work_mode TEXT NOT NULL,
                eligible_countries TEXT NOT NULL DEFAULT 'Not specified',
                skills TEXT NOT NULL DEFAULT '',
                skill_match INTEGER NOT NULL DEFAULT 0,
                eligibility_status TEXT NOT NULL DEFAULT 'Not checked',
                compensation_min REAL,
                compensation_max REAL,
                currency TEXT NOT NULL DEFAULT 'USD',
                deadline TEXT,
                source_url TEXT NOT NULL,
                application_url TEXT,
                source_type TEXT NOT NULL,
                source_checked_at TEXT,
                verification_status TEXT NOT NULL DEFAULT 'Unverified',
                status TEXT NOT NULL DEFAULT 'Saved',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _validate_url(value: str, field_name: str, required: bool = False) -> None:
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"{field_name} is required.")
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be a complete http or https URL.")


def add_opportunity(db_path: str | Path, opportunity: dict[str, Any]) -> int:
    """Validate and insert an opportunity; return its database ID."""
    record = {field: opportunity.get(field) for field in FIELDS}

    for field in ("title", "organization", "source_url"):
        if not str(record.get(field) or "").strip():
            raise ValueError(f"{field.replace('_', ' ').title()} is required.")

    _validate_url(str(record["source_url"]), "Source URL", required=True)
    _validate_url(str(record.get("application_url") or ""), "Application URL")

    record["title"] = str(record["title"]).strip()
    record["organization"] = str(record["organization"]).strip()
    record["eligible_countries"] = str(
        record.get("eligible_countries") or "Not specified"
    ).strip()
    record["skills"] = str(record.get("skills") or "").strip()
    record["currency"] = str(record.get("currency") or "USD").strip().upper()
    record["notes"] = str(record.get("notes") or "").strip()

    record["opportunity_type"] = record.get("opportunity_type") or "Other"
    record["work_mode"] = record.get("work_mode") or "Not specified"
    record["source_type"] = record.get("source_type") or "Referral/other"
    record["eligibility_status"] = record.get("eligibility_status") or "Not checked"
    record["verification_status"] = (
        record.get("verification_status") or "Unverified"
    )
    record["status"] = record.get("status") or "Saved"

    if record["opportunity_type"] not in OPPORTUNITY_TYPES:
        raise ValueError("Select a valid opportunity type.")
    if record["work_mode"] not in WORK_MODES:
        raise ValueError("Select a valid work mode.")
    if record["source_type"] not in SOURCE_TYPES:
        raise ValueError("Select a valid source type.")
    if record["eligibility_status"] not in ELIGIBILITY_STATUSES:
        raise ValueError("Select a valid eligibility status.")
    if record["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError("Select a valid source verification status.")
    if record["status"] not in PIPELINE_STATUSES:
        raise ValueError("Select a valid application status.")

    skill_match = int(record.get("skill_match") or 0)
    if not 0 <= skill_match <= 100:
        raise ValueError("Skill match must be between 0 and 100.")
    record["skill_match"] = skill_match

    for field in ("compensation_min", "compensation_max"):
        value = record.get(field)
        if value in ("", None):
            record[field] = None
        else:
            number = float(value)
            if number < 0:
                raise ValueError("Compensation cannot be negative.")
            record[field] = number

    minimum = record["compensation_min"]
    maximum = record["compensation_max"]
    if minimum is not None and maximum is not None and maximum < minimum:
        raise ValueError("Maximum compensation must be greater than or equal to minimum.")

    for field in ("deadline", "source_checked_at"):
        value = record.get(field)
        if value in ("", None):
            record[field] = None
        elif isinstance(value, date):
            record[field] = value.isoformat()
        else:
            try:
                record[field] = date.fromisoformat(str(value)).isoformat()
            except ValueError as exc:
                raise ValueError(f"{field.replace('_', ' ').title()} must be YYYY-MM-DD.") from exc

    if record["verification_status"] == "Unverified":
        record["source_checked_at"] = None
    elif not record["source_checked_at"]:
        raise ValueError("A source-check date is required when source evidence is recorded.")

    now = _utc_now()
    columns = ", ".join(FIELDS) + ", created_at, updated_at"
    placeholders = ", ".join("?" for _ in range(len(FIELDS) + 2))
    values = [record[field] for field in FIELDS] + [now, now]

    with _connect(db_path) as connection:
        cursor = connection.execute(
            f"INSERT INTO opportunities ({columns}) VALUES ({placeholders})",
            values,
        )
        return int(cursor.lastrowid)


def list_opportunities(db_path: str | Path) -> list[dict[str, Any]]:
    """Return opportunity records, newest first."""
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM opportunities ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def update_status(
    db_path: str | Path, opportunity_id: int, new_status: str
) -> None:
    """Update the application pipeline status for one record."""
    if new_status not in PIPELINE_STATUSES:
        raise ValueError("Select a valid application status.")
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, _utc_now(), int(opportunity_id)),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No opportunity found with ID {opportunity_id}.")


def delete_opportunity(db_path: str | Path, opportunity_id: int) -> None:
    """Delete one record by ID."""
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM opportunities WHERE id = ?", (int(opportunity_id),)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No opportunity found with ID {opportunity_id}.")


def score_opportunity(
    opportunity: dict[str, Any], today: date | None = None
) -> dict[str, Any]:
    """Return a transparent triage score and deadline label for one opportunity.

    Score is a workflow heuristic, not an estimated probability of acceptance.
    """
    today = today or date.today()
    deadline_text = opportunity.get("deadline")
    deadline_state = "No deadline recorded"
    if deadline_text:
        try:
            deadline = date.fromisoformat(str(deadline_text))
            deadline_state = "Deadline passed" if deadline < today else "Deadline not passed"
        except ValueError:
            deadline_state = "Invalid deadline date"

    eligibility = opportunity.get("eligibility_status", "Not checked")
    verification = opportunity.get("verification_status", "Unverified")
    try:
        skill_match = max(0, min(100, int(opportunity.get("skill_match") or 0)))
    except (TypeError, ValueError):
        skill_match = 0

    evidence_freshness = 0.0
    checked_at = opportunity.get("source_checked_at")
    if verification != "Unverified" and checked_at:
        try:
            age_days = (today - date.fromisoformat(str(checked_at))).days
            if 0 <= age_days <= 7:
                evidence_freshness = 1.0
            elif 8 <= age_days <= 30:
                evidence_freshness = 0.5
        except ValueError:
            evidence_freshness = 0.0

    score = (
        skill_match * 0.50
        + ELIGIBILITY_POINTS.get(eligibility, 25) * 0.30
        + VERIFICATION_POINTS.get(verification, 0) * evidence_freshness * 0.20
    )

    if deadline_state == "Deadline passed" or eligibility == "Ineligible":
        score = 0.0

    return {
        "priority_score": round(score, 1),
        "deadline_state": deadline_state,
        "evidence_freshness": evidence_freshness,
    }
