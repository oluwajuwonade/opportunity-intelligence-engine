# Opportunity Intelligence Engine

A personal opportunity discovery and application-tracking workspace for remote jobs, freelance contracts, AI evaluation work, grants, and research opportunities.

## What it does

- Stores opportunities in a local SQLite database.
- Records source and application URLs, source type, eligibility, required skills, compensation, deadlines, and application status.
- Separates manual source checks from application-window checks. New records are unverified by default.
- Calculates a transparent triage priority score from skill match, eligibility, and freshness of the source check.
- Filters and exports your opportunity queue to CSV.
- Includes tests for storage, status changes, deletion, validation, and ranking.

## Important scope boundary

This is a tracking and decision-support MVP, not a live job scraper. It does not claim opportunities are currently open, that you are eligible, or that an application will succeed. Enter listings from trustworthy sources and record what you personally checked. The score is a prioritisation aid, not a probability of acceptance or a measure of opportunity quality.

No real opportunity listings are bundled into the repository; this avoids presenting fictional examples as live opportunities.

## Requirements

- Python 3.10 or newer
- pip

## Run locally

1. Clone or download this repository.
2. Create and activate a virtual environment.
3. Install dependencies.
4. Start the Streamlit application.

Commands:

    python -m venv .venv

Windows activation:

    .venv\Scripts\activate

macOS/Linux activation:

    source .venv/bin/activate

Install and run:

    pip install -r requirements.txt
    streamlit run app.py

The app creates data/opportunities.db on first launch. The database is ignored by Git and remains local to the machine running the app.

## Run tests

    pip install -r requirements.txt
    pytest -q

## Priority score

The score ranges from 0 to 100 and is deliberately interpretable:

- Skill match contributes up to 50 points.
- Eligibility contributes up to 30 points: Eligible = 100, Potentially eligible = 65, Not checked = 25, Ineligible = 0.
- Source evidence contributes up to 20 points: Application window checked = 100, Source checked = 70, Unverified = 0. Evidence points are reduced as the source check gets older.
- A passed deadline or an Ineligible record receives a score of 0.

Freshness rules for source evidence: checks from the last 7 days receive full evidence weight; 8–30 days receive half weight; older checks receive no evidence weight. These are workflow heuristics, not empirical predictions.

## Source-check protocol

For each opportunity:

1. Prefer the official employer, funder, research organisation, or programme page.
2. Confirm the role or programme still exists.
3. Read country restrictions, work mode, professional requirements, compensation, and deadline.
4. Record the URL you checked and the date you checked it.
5. Mark eligibility as Eligible only when the published requirements support that conclusion; otherwise use Potentially eligible or Not checked.
6. Recheck before applying. Aggregator listings can be stale even when they remain online.

## Privacy and deployment

The database may contain private notes about your applications. Keep it local and do not commit it. Do not enter passwords, API keys, identity documents, or unnecessary sensitive personal data. If you deploy the app publicly, do not use it as a private application tracker without adding authentication and a secure persistent database. Some hosted app filesystems are ephemeral, so SQLite data may not persist across restarts.

## Roadmap

- Source connectors through permitted APIs and RSS feeds.
- Scheduled checks and reminder notifications.
- More granular matching by skills, compensation, and location.
- Optional authenticated deployment with durable database storage.
- Evidence history for source changes and deadline changes.

## Licence

No licence has been added yet. Add an explicit licence before encouraging reuse or external contributions.
