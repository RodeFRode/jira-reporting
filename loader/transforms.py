"""Transformation helpers for Jira -> DB mapping."""
import yaml
from datetime import datetime, timezone

def load_mapping(path: str = "mapping.yaml") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def parse_ts(s: str | None):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: return None

def lift_custom_fields(issue_fields: dict, mapping: dict, issue_type_name: str):
    lifted = {}
    for col, spec in (mapping.get("defaults") or {}).items():
        key = spec.get("key"); typ = spec.get("type", "text"); val = issue_fields.get(key); lifted[col] = cast_value(val, typ)
    it_map = (mapping.get("issue_types") or {}).get(issue_type_name, {})
    for col, spec in it_map.items():
        key = spec.get("key"); typ = spec.get("type", "text"); val = issue_fields.get(key); lifted[col] = cast_value(val, typ)
    return lifted

def cast_value(val, typ: str):
    if val is None: return None
    if typ == "numeric":
        try: return float(val)
        except Exception: return None
    if typ == "issue": return str(val)
    if typ == "date": return parse_ts(val)
    return str(val)
