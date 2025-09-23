
-- Jira Analytics Data Model v1.2 (Data Center) — minimal scope
-- Schema + search_path
CREATE SCHEMA IF NOT EXISTS jira;
SET search_path = jira, public;

-- =========================
-- Dimensionen (Kern)
-- =========================

CREATE TABLE IF NOT EXISTS dim_project (
  project_id   BIGINT PRIMARY KEY,
  project_key  TEXT UNIQUE NOT NULL,
  name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_issue_type (
  issue_type_id BIGINT PRIMARY KEY,
  name          TEXT NOT NULL,
  is_subtask    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_status (
  status_id     BIGINT PRIMARY KEY,
  name          TEXT NOT NULL,
  category_key  TEXT NOT NULL            -- z.B. new | indeterminate | done
);

CREATE TABLE IF NOT EXISTS dim_priority (
  priority_id BIGINT PRIMARY KEY,
  name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_component (
  component_id BIGINT PRIMARY KEY,
  project_id   BIGINT REFERENCES dim_project(project_id),
  name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_version (
  version_id   BIGINT PRIMARY KEY,
  project_id   BIGINT REFERENCES dim_project(project_id),
  name         TEXT NOT NULL,
  released     BOOLEAN,
  release_date TIMESTAMPTZ
);

-- =========================
-- Issue Snapshot (aktueller Stand)
-- =========================

CREATE TABLE IF NOT EXISTS fact_issue_snapshot (
  issue_id            BIGINT PRIMARY KEY,
  issue_key           TEXT UNIQUE NOT NULL,
  project_id          BIGINT NOT NULL REFERENCES dim_project(project_id),
  issue_type_id       BIGINT NOT NULL REFERENCES dim_issue_type(issue_type_id),
  parent_issue_id     BIGINT,                   -- Subtask-Eltern
  epic_issue_id       BIGINT,                   -- via Epic-Link (optional)
  reporter_user_id    TEXT,                     -- reine Text-ID (DC)
  assignee_user_id    TEXT,                     -- reine Text-ID (DC)
  status_id_current   BIGINT NOT NULL REFERENCES dim_status(status_id),
  priority_id         BIGINT REFERENCES dim_priority(priority_id),
  summary             TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL,
  resolved_at         TIMESTAMPTZ,
  duedate             TIMESTAMPTZ,
  story_points        NUMERIC,                  -- optional „geliftet“
  custom_fields       JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingestion_ts        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Labels / Komponenten / FixVersions (keine AffectsVersions)
CREATE TABLE IF NOT EXISTS bridge_issue_label (
  issue_id BIGINT REFERENCES fact_issue_snapshot(issue_id) ON DELETE CASCADE,
  label    TEXT NOT NULL,
  PRIMARY KEY (issue_id, label)
);

CREATE TABLE IF NOT EXISTS bridge_issue_component (
  issue_id     BIGINT REFERENCES fact_issue_snapshot(issue_id) ON DELETE CASCADE,
  component_id BIGINT REFERENCES dim_component(component_id),
  PRIMARY KEY (issue_id, component_id)
);

CREATE TABLE IF NOT EXISTS bridge_issue_fix_version (
  issue_id   BIGINT REFERENCES fact_issue_snapshot(issue_id) ON DELETE CASCADE,
  version_id BIGINT REFERENCES dim_version(version_id),
  PRIMARY KEY (issue_id, version_id)
);

-- =========================
-- Event-Log (Quelle der Wahrheit)
-- =========================
-- Aus changelog.histories[].items[]; item_idx ist 0-basiert.

CREATE TABLE IF NOT EXISTS fact_issue_event (
  issue_id        BIGINT NOT NULL,
  history_id      BIGINT NOT NULL,          -- stabil pro Issue in DC
  item_idx        INTEGER NOT NULL,         -- Position im items[] Array
  event_ts        TIMESTAMPTZ NOT NULL,     -- history.created
  field           TEXT NOT NULL,            -- "status", "assignee", "Sprint", "Epic Link", ...
  field_type      TEXT,                     -- "jira", "custom", ...
  from_value      TEXT,
  from_string     TEXT,
  to_value        TEXT,
  to_string       TEXT,
  author_user_id  TEXT,                     -- reine Text-ID (DC)
  ingestion_ts    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (issue_id, history_id, item_idx)
);

CREATE INDEX IF NOT EXISTS idx_issue_event_issue_ts ON fact_issue_event (issue_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_issue_event_field_ts ON fact_issue_event (field, event_ts);

-- =========================
-- Abgeleitete Status-Spannen
-- =========================

CREATE TABLE IF NOT EXISTS fact_issue_status_span (
  issue_id     BIGINT NOT NULL,
  status_id    BIGINT NOT NULL REFERENCES dim_status(status_id),
  start_ts     TIMESTAMPTZ NOT NULL,
  end_ts       TIMESTAMPTZ,                 -- NULL = aktuell offen
  from_history_id BIGINT,                   -- Quelle Start (optional)
  to_history_id   BIGINT,                   -- Quelle Ende  (optional)
  PRIMARY KEY (issue_id, status_id, start_ts)
);

CREATE INDEX IF NOT EXISTS idx_status_span_status_start ON fact_issue_status_span (status_id, start_ts);

-- =========================
-- Issue-Links
-- =========================

CREATE TABLE IF NOT EXISTS bridge_issue_link (
  source_issue_id  BIGINT NOT NULL REFERENCES fact_issue_snapshot(issue_id) ON DELETE CASCADE,
  link_type        TEXT NOT NULL,           -- "blocks", "relates to", ...
  target_issue_id  BIGINT NOT NULL REFERENCES fact_issue_snapshot(issue_id) ON DELETE CASCADE,
  created_ts       TIMESTAMPTZ,             -- wenn ermittelbar
  PRIMARY KEY (source_issue_id, link_type, target_issue_id)
);

-- =========================
-- ETL Steuerung
-- =========================

CREATE TABLE IF NOT EXISTS etl_sync_state (
  entity            TEXT PRIMARY KEY,       -- 'issues', 'events', 'links', 'versions', ...
  scope_hash        TEXT NOT NULL,          -- Hash aus JQL/ProjectKey usw.
  last_cursor_value TEXT,                   -- z.B. ISO-TS oder ID
  last_run_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes             JSONB
);
