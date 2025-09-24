# src/jira_reporting/main.py
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid

from .config import Settings
from .jira_api import JiraClient
from .extract import extract_issues

log = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)


def cmd_extract(args: argparse.Namespace) -> int:
    settings = Settings.from_env()  # liest .env / env vars, wie zuvor
    issues_iter = extract_issues(
        settings=settings,
        jql=args.jql,
        page_size=args.page_size,
        fields=args.fields.split(",") if args.fields else None,
        include_recent_changelog=args.expand_changelog,
        fetch_full_changelog=args.full_changelog,
    )
    count = 0
    for issue in issues_iter:
        count += 1
        if args.print_json:
            print(json.dumps(issue, ensure_ascii=False))
    log.info("Extract done", extra={"count": count})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jira-reporting")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ext = sub.add_parser("extract", help="Issues per JQL auslesen (paginiert)")
    p_ext.add_argument("--jql", required=True, help="z.B. 'project = XYZ AND updated >= -14d ORDER BY updated asc'")
    p_ext.add_argument("--page-size", type=int, default=100)
    p_ext.add_argument("--fields", help="Kommagetrennt; Standard, wenn leer")
    p_ext.add_argument("--expand-changelog", action="store_true", help="liefert die letzten ~100 Changelog-Einträge mit")
    p_ext.add_argument("--full-changelog", action="store_true", help="lädt vollständigen Changelog pro Issue (separat, paginiert)")
    p_ext.add_argument("--print-json", action="store_true", help="Issues als JSON auf stdout ausgeben")
    p_ext.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
