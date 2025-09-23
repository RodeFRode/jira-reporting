from __future__ import annotations
"""ETL orchestration for Jira DC -> Postgres."""
import os, json, hashlib, logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from .config import load_config
from .db import DB
from .jira_dc import JiraClient
from .transforms import load_mapping, parse_ts, lift_custom_fields
log = logging.getLogger(__name__)

def scope_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def run_once(run_id: str | None = None):
    load_dotenv()
    cfg = load_config()
    mapping = load_mapping("mapping.yaml")
    if not cfg.jira_base_url: raise SystemExit("JIRA_BASE_URL is required")

    db = DB(cfg.pg_host, cfg.pg_port, cfg.pg_db, cfg.pg_user, cfg.pg_password)
    jc = JiraClient(
        cfg.jira_base_url, cfg.jira_auth_type, cfg.jira_token, cfg.jira_username, cfg.jira_password,
        cf_access_client_id=cfg.cf_access_client_id,
        cf_access_client_secret=cfg.cf_access_client_secret,
        cf_access_jwt=cfg.cf_access_jwt,
    )
    try:
        entity = "issues"
        sc_hash = scope_hash(cfg.etl_scope_name + "|" + cfg.jql)
        st = db.get_sync_state(entity, sc_hash)
        if st and st.get("last_cursor_value"):
            last_cursor_dt = parse_ts(st["last_cursor_value"])
            log.info("Continuing incremental load", extra={"cursor": st["last_cursor_value"], "scope_hash": sc_hash})
        else:
            last_cursor_dt = datetime.now(timezone.utc) - timedelta(days=30)
            log.info("Starting initial/backfill window", extra={"from_utc": last_cursor_dt.isoformat(), "scope_hash": sc_hash})

        overlap = timedelta(minutes=cfg.etl_overlap_min)
        effective_from = (last_cursor_dt - overlap) if last_cursor_dt else None

        jql = cfg.jql
        if effective_from:
            iso = effective_from.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
            jql = f'updated >= "{iso}" AND ({cfg.jql})'

        start_at = 0
        page_size = cfg.page_size
        max_updated_seen: str | None = None
        log.info("Search starting", extra={"jql": jql, "page_size": page_size})

        while True:
            data = jc.search_issues(jql, start_at=start_at, max_results=page_size, expand=["changelog"])
            issues = data.get("issues", [])
            total = data.get("total", 0)
            if not issues:
                log.info("No more issues in page", extra={"start_at": start_at})
                break

            for it in issues:
                issue_id = int(it["id"]); key = it["key"]; f = it.get("fields", {})
                upd = parse_ts(f.get("updated"))
                if upd:
                    upd_iso = upd.astimezone(timezone.utc).isoformat()
                    if (max_updated_seen is None) or (upd_iso > max_updated_seen):
                        max_updated_seen = upd_iso

                proj = f.get("project") or {}; db.upsert_project(int(proj["id"]), proj.get("key"), proj.get("name"))
                itype = f.get("issuetype") or {}; db.upsert_issue_type(int(itype["id"]), itype.get("name"), bool(itype.get("subtask")))
                status = f.get("status") or {}; status_cat = (status.get("statusCategory") or {}).get("key") or "indeterminate"
                db.upsert_status(int(status["id"]), status.get("name"), status_cat)
                prio = f.get("priority");
                if prio: db.upsert_priority(int(prio["id"]), prio.get("name"))

                custom_fields_raw = {k: v for k, v in f.items() if k.startswith("customfield_")}
                lifted = lift_custom_fields(f, mapping, itype.get("name"))
                row = {
                    "issue_id": issue_id, "issue_key": key, "project_id": int(proj["id"]), "issue_type_id": int(itype["id"]),
                    "parent_issue_id": int(f["parent"]["id"]) if f.get("parent") else None,
                    "epic_issue_id": None,
                    "reporter_user_id": (f.get("reporter") or {}).get("name") or (f.get("reporter") or {}).get("key"),
                    "assignee_user_id": (f.get("assignee") or {}).get("name") or (f.get("assignee") or {}).get("key"),
                    "status_id_current": int(status["id"]),
                    "priority_id": int(prio["id"]) if prio else None,
                    "summary": f.get("summary"),
                    "created_at": parse_ts(f.get("created")),
                    "updated_at": upd,
                    "resolved_at": parse_ts(f.get("resolutiondate")),
                    "duedate": parse_ts(f.get("duedate")),
                    "story_points": lifted.get("story_points"),
                    "custom_fields": json.dumps(custom_fields_raw),
                }
                db.upsert_issue_snapshot(row)

                db.replace_issue_labels(issue_id, f.get("labels") or [])

                comps = [{"id": c["id"], "projectId": proj["id"], "name": c["name"]} for c in (f.get("components") or [])]
                db.replace_issue_components(issue_id, comps)

                vers = [{"id": v["id"], "projectId": proj["id"], "name": v["name"], "released": v.get("released"), "releaseDate": v.get("releaseDate")} for v in (f.get("fixVersions") or [])]
                db.replace_issue_fix_versions(issue_id, vers)

                ch = it.get("changelog") or {}; histories = ch.get("histories") or []
                if ch.get("total") and len(histories) < ch.get("total"):
                    ch_full = jc.get_issue_changelog_full(key); histories = ch_full.get("histories") or histories

                for h in histories:
                    hid = int(h["id"]); ts = parse_ts(h.get("created"))
                    author = (h.get("author") or {}).get("name") or (h.get("author") or {}).get("key")
                    for idx, item in enumerate(h.get("items") or []):
                        evt = {"issue_id": issue_id, "history_id": hid, "item_idx": idx, "event_ts": ts,
                               "field": item.get("field"), "field_type": item.get("fieldtype"),
                               "from_value": str(item.get("from")) if item.get("from") is not None else None,
                               "from_string": item.get("fromString"), "to_value": str(item.get("to")) if item.get("to") is not None else None,
                               "to_string": item.get("toString"), "author_user_id": author}
                        db.upsert_issue_event(evt)

                db.rebuild_status_spans(issue_id)
                db.commit()

            start_at += len(issues)
            if start_at >= total: break

        if max_updated_seen:
            db.upsert_sync_state(entity, sc_hash, max_updated_seen, notes={"jql": cfg.jql})
            db.commit(); log.info("Cursor updated", extra={"last_cursor": max_updated_seen})
        log.info("Run complete")
    except Exception:
        log.exception("ETL run failed"); db.rollback(); raise
    finally:
        db.close()
