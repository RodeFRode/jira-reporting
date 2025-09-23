# Jira Data Center ETL — Minimal Skeleton (v1.2)

Extracts Jira **Issues + full Changelog** into PostgreSQL using the v1.2 schema.

## What it does
- Pulls issues via `/rest/api/2/search` (JQL), with `expand=changelog`.
- Pages full changelog via `/rest/api/2/issue/{id}/changelog`.
- Upserts core dims + `fact_issue_snapshot` + `fact_issue_event`.
- Rebuilds `fact_issue_status_span` per changed issue.
- Maintains `etl_sync_state` cursor (with overlap).

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# edit .env

python main.py run
```

## Logging
- Configure via `.env`: `LOG_LEVEL`, `LOG_JSON`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`.
- Each run has a `run_id` for correlation.
- HTTP requests/responses are logged (method, URL, status, latency). Secrets are not logged.
