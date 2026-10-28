from datetime import date, timedelta

import pytest

from src.opportunity_engine import (
    add_opportunity,
    delete_opportunity,
    init_db,
    list_opportunities,
    score_opportunity,
    update_status,
)


def valid_record(**overrides):
    record = {
        "title": "Data Analyst Contract",
        "organization": "Example Organisation",
        "opportunity_type": "Freelance contract",
        "work_mode": "Remote",
        "eligible_countries": "Nigeria",
        "skills": "Python, SQL, Power BI",
        "skill_match": 80,
        "eligibility_status": "Eligible",
        "compensation_min": 200,
        "compensation_max": 500,
        "currency": "USD",
        "deadline": (date.today() + timedelta(days=10)).isoformat(),
        "source_url": "https://example.com/opportunity",
        "application_url": "https://example.com/apply",
        "source_type": "Official employer/organisation page",
        "source_checked_at": date.today().isoformat(),
        "verification_status": "Application window checked",
        "status": "Saved",
        "notes": "Test fixture only; not a real opportunity.",
    }
    record.update(overrides)
    return record


def test_add_and_list_opportunity(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)

    record_id = add_opportunity(db_path, valid_record())

    records = list_opportunities(db_path)
    assert len(records) == 1
    assert records[0]["id"] == record_id
    assert records[0]["title"] == "Data Analyst Contract"
    assert records[0]["verification_status"] == "Application window checked"


def test_rejects_missing_source_url(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)

    with pytest.raises(ValueError, match="Source URL is required"):
        add_opportunity(db_path, valid_record(source_url=""))


def test_rejects_non_http_source_url(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)

    with pytest.raises(ValueError, match="complete http or https URL"):
        add_opportunity(db_path, valid_record(source_url="example.com/role"))


def test_rejects_invalid_compensation_range(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)

    with pytest.raises(ValueError, match="Maximum compensation"):
        add_opportunity(
            db_path,
            valid_record(compensation_min=900, compensation_max=100),
        )


def test_priority_score_and_expired_deadline(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)
    record_id = add_opportunity(db_path, valid_record())
    record = next(row for row in list_opportunities(db_path) if row["id"] == record_id)

    score = score_opportunity(record, today=date.today())
    assert score["priority_score"] == 90.0
    assert score["deadline_state"] == "Deadline not passed"

    expired = score_opportunity(
        {**record, "deadline": (date.today() - timedelta(days=1)).isoformat()},
        today=date.today(),
    )
    assert expired["priority_score"] == 0.0
    assert expired["deadline_state"] == "Deadline passed"


def test_stale_source_check_loses_evidence_weight(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)
    record_id = add_opportunity(db_path, valid_record())
    record = next(row for row in list_opportunities(db_path) if row["id"] == record_id)

    fresh_score = score_opportunity(record, today=date.today())["priority_score"]
    record["source_checked_at"] = (date.today() - timedelta(days=45)).isoformat()
    stale_score = score_opportunity(record, today=date.today())["priority_score"]

    assert fresh_score > stale_score


def test_ineligible_record_scores_zero(tmp_path):
    record = valid_record(eligibility_status="Ineligible")
    assert score_opportunity(record, today=date.today())["priority_score"] == 0.0


def test_update_and_delete(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)
    record_id = add_opportunity(db_path, valid_record())

    update_status(db_path, record_id, "Applied")
    assert list_opportunities(db_path)[0]["status"] == "Applied"

    delete_opportunity(db_path, record_id)
    assert list_opportunities(db_path) == []


def test_unverified_record_does_not_gain_evidence_points(tmp_path):
    db_path = tmp_path / "opportunities.db"
    init_db(db_path)
    record_id = add_opportunity(
        db_path,
        valid_record(verification_status="Unverified", source_checked_at=None),
    )
    record = next(row for row in list_opportunities(db_path) if row["id"] == record_id)

    score = score_opportunity(record, today=date.today())
    assert score["priority_score"] == 70.0
    assert score["evidence_freshness"] == 0.0
