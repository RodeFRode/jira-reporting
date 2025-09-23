from __future__ import annotations
"""Database access layer for the Jira DC ETL."""
import logging
import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

class DB:
    def __init__(self, host, port, dbname, user, password):
        self._conn = psycopg.connect(
            host=host, port=port, dbname=dbname, user=user, password=password,
            autocommit=False, row_factory=dict_row
        )
        with self._conn.cursor() as cur:
            cur.execute("SET search_path = jira, public;")
        log.info("Connected to Postgres", extra={"host": host, "port": port, "db": dbname})

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def get_sync_state(self, entity: str, scope_hash: str):
        q = """SELECT entity, scope_hash, last_cursor_value, last_run_ts, notes
                 FROM etl_sync_state WHERE entity = %s"""
        with self._conn.cursor() as cur:
            cur.execute(q, (entity,))
            row = cur.fetchone()
            if row and row.get("scope_hash") != scope_hash:
                log.info("Scope hash changed; ignoring stored cursor", extra={
                    "entity": entity, "old_scope_hash": row.get("scope_hash")
                })
                return None
            return row

    def upsert_sync_state(self, entity: str, scope_hash: str, last_cursor_value: str, notes: dict | None = None):
        from psycopg.types.json import Json
        q = """INSERT INTO etl_sync_state (entity, scope_hash, last_cursor_value, notes)
                 VALUES (%s, %s, %s, %s::jsonb)
                 ON CONFLICT (entity) DO UPDATE
                 SET scope_hash = EXCLUDED.scope_hash,
                     last_cursor_value = EXCLUDED.last_cursor_value,
                     last_run_ts = now(),
                     notes = EXCLUDED.notes;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (entity, scope_hash, last_cursor_value, Json(notes or {})))

    def upsert_project(self, project_id: int, key: str, name: str):
        q = """INSERT INTO dim_project(project_id, project_key, name)
                 VALUES (%s, %s, %s)
                 ON CONFLICT (project_id) DO UPDATE
                 SET project_key=EXCLUDED.project_key, name=EXCLUDED.name;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (project_id, key, name))

    def upsert_issue_type(self, issue_type_id: int, name: str, is_subtask: bool):
        q = """INSERT INTO dim_issue_type(issue_type_id, name, is_subtask)
                 VALUES (%s, %s, %s)
                 ON CONFLICT (issue_type_id) DO UPDATE
                 SET name=EXCLUDED.name, is_subtask=EXCLUDED.is_subtask;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (issue_type_id, name, is_subtask))

    def upsert_status(self, status_id: int, name: str, category_key: str):
        q = """INSERT INTO dim_status(status_id, name, category_key)
                 VALUES (%s, %s, %s)
                 ON CONFLICT (status_id) DO UPDATE
                 SET name=EXCLUDED.name, category_key=EXCLUDED.category_key;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (status_id, name, category_key))

    def upsert_priority(self, priority_id: int, name: str):
        q = """INSERT INTO dim_priority(priority_id, name)
                 VALUES (%s, %s)
                 ON CONFLICT (priority_id) DO UPDATE SET name=EXCLUDED.name;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (priority_id, name))

    def upsert_component(self, component_id: int, project_id: int, name: str):
        q = """INSERT INTO dim_component(component_id, project_id, name)
                 VALUES (%s, %s, %s)
                 ON CONFLICT (component_id) DO UPDATE
                 SET project_id=EXCLUDED.project_id, name=EXCLUDED.name;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (component_id, project_id, name))

    def upsert_version(self, version_id: int, project_id: int, name: str, released: bool | None, release_date):
        q = """INSERT INTO dim_version(version_id, project_id, name, released, release_date)
                 VALUES (%s, %s, %s, %s, %s)
                 ON CONFLICT (version_id) DO UPDATE
                 SET project_id=EXCLUDED.project_id, name=EXCLUDED.name,
                     released=EXCLUDED.released, release_date=EXCLUDED.release_date;"""
        with self._conn.cursor() as cur:
            cur.execute(q, (version_id, project_id, name, released, release_date))

    def upsert_issue_snapshot(self, row: dict):
        cols = [
            "issue_id","issue_key","project_id","issue_type_id","parent_issue_id","epic_issue_id",
            "reporter_user_id","assignee_user_id","status_id_current","priority_id","summary",
            "created_at","updated_at","resolved_at","duedate","story_points","custom_fields"
        ]
        values = [row.get(k) for k in cols]
        q = f"""INSERT INTO fact_issue_snapshot ({','.join(cols)})
                 VALUES ({','.join(['%s']*len(cols))})
                 ON CONFLICT (issue_id) DO UPDATE SET
                 issue_key=EXCLUDED.issue_key, project_id=EXCLUDED.project_id,
                 issue_type_id=EXCLUDED.issue_type_id, parent_issue_id=EXCLUDED.parent_issue_id,
                 epic_issue_id=EXCLUDED.epic_issue_id, reporter_user_id=EXCLUDED.reporter_user_id,
                 assignee_user_id=EXCLUDED.assignee_user_id, status_id_current=EXCLUDED.status_id_current,
                 priority_id=EXCLUDED.priority_id, summary=EXCLUDED.summary, created_at=EXCLUDED.created_at,
                 updated_at=EXCLUDED.updated_at, resolved_at=EXCLUDED.resolved_at, duedate=EXCLUDED.duedate,
                 story_points=EXCLUDED.story_points, custom_fields=EXCLUDED.custom_fields;"""
        with self._conn.cursor() as cur:
            cur.execute(q, values)

    def replace_issue_labels(self, issue_id: int, labels: list[str]):
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM bridge_issue_label WHERE issue_id=%s", (issue_id,))
            for lab in labels or []:
                cur.execute("INSERT INTO bridge_issue_label(issue_id,label) VALUES (%s,%s) ON CONFLICT DO NOTHING", (issue_id, lab))

    def replace_issue_components(self, issue_id: int, comps: list[dict]):
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM bridge_issue_component WHERE issue_id=%s", (issue_id,))
            for c in comps or []:
                cur.execute("INSERT INTO dim_component(component_id, project_id, name) VALUES (%s,%s,%s) ON CONFLICT (component_id) DO NOTHING", (int(c['id']), int(c['projectId']), c['name']))
                cur.execute("INSERT INTO bridge_issue_component(issue_id, component_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (issue_id, int(c['id'])))

    def replace_issue_fix_versions(self, issue_id: int, versions: list[dict]):
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM bridge_issue_fix_version WHERE issue_id=%s", (issue_id,))
            for v in versions or []:
                cur.execute("INSERT INTO dim_version(version_id, project_id, name, released, release_date) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (version_id) DO NOTHING", (int(v['id']), int(v['projectId']), v['name'], v.get('released'), v.get('releaseDate')))
                cur.execute("INSERT INTO bridge_issue_fix_version(issue_id, version_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (issue_id, int(v['id'])))

    def upsert_issue_event(self, evt: dict):
        q = """INSERT INTO fact_issue_event(issue_id, history_id, item_idx, event_ts, field, field_type,
                 from_value, from_string, to_value, to_string, author_user_id)
                 VALUES (%(issue_id)s, %(history_id)s, %(item_idx)s, %(event_ts)s, %(field)s, %(field_type)s,
                        %(from_value)s, %(from_string)s, %(to_value)s, %(to_string)s, %(author_user_id)s)
                 ON CONFLICT (issue_id, history_id, item_idx) DO NOTHING;"""
        with self._conn.cursor() as cur:
            cur.execute(q, evt)

    def rebuild_status_spans(self, issue_id: int):
        with self._conn.cursor() as cur:
            cur.execute("SELECT created_at, status_id_current FROM fact_issue_snapshot WHERE issue_id=%s", (issue_id,))
            snap = cur.fetchone()
            if not snap:
                return
            created_at = snap["created_at"]
            cur.execute("""SELECT event_ts, from_string, to_string
                            FROM fact_issue_event
                            WHERE issue_id=%s AND field='status'
                            ORDER BY event_ts ASC, history_id ASC, item_idx ASC""", (issue_id,))
            evts = cur.fetchall()
            cur.execute("SELECT status_id, name FROM dim_status")
            name2id = {r['name']: r['status_id'] for r in cur.fetchall()}

            if evts and evts[0]['from_string']:
                initial_status_name = evts[0]['from_string']
            else:
                cur.execute("SELECT name FROM dim_status WHERE status_id=%s", (snap["status_id_current"],))
                r = cur.fetchone()
                initial_status_name = r['name'] if r else None

            cur.execute("DELETE FROM fact_issue_status_span WHERE issue_id=%s", (issue_id,))
            if not initial_status_name:
                return

            current_status = initial_status_name
            current_start = created_at

            for e in evts:
                cur.execute("INSERT INTO fact_issue_status_span(issue_id, status_id, start_ts, end_ts) VALUES (%s,%s,%s,%s)",
                            (issue_id, name2id.get(current_status), current_start, e['event_ts']))
                current_status = e['to_string']
                current_start = e['event_ts']

            cur.execute("INSERT INTO fact_issue_status_span(issue_id, status_id, start_ts, end_ts) VALUES (%s,%s,%s,%s)",
                        (issue_id, name2id.get(current_status), current_start, None))
