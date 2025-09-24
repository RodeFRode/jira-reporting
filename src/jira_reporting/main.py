from __future__ import annotations
import logging
import sys
from .config import Settings
from .jira_api import JiraAPI

def setup_logging() -> None:
    # kompakt & konsistent
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
    )
    logging.getLogger("httpx").setLevel(logging.INFO)

def main() -> int:
    setup_logging()
    log = logging.getLogger("main")
    try:
        cfg = Settings.from_env()
    except Exception as e:
        log.error("Konfiguration fehlerhaft: %s", e)
        return 2

    api = JiraAPI(cfg)
    try:
        me = api.auth_check()
    except Exception as e:
        log.error("myself-Check fehlgeschlagen: %s", e)
        return 3
    finally:
        api.close()

    log.info("Auth ok – angemeldet als: %s (%s)", me.get("displayName"), me.get("name") or me.get("key"))
    # -> ab hier erst weitere Schritte (später: ETL/DB, JQL, etc.)
    return 0

if __name__ == "__main__":
    sys.exit(main())
