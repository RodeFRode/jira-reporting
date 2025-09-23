from __future__ import annotations

import logging, os, sys, uuid
from logging.handlers import RotatingFileHandler

try:
    from pythonjsonlogger import jsonlogger
    _HAS_JSON = True
except Exception:
    _HAS_JSON = False


def _build_formatter(json_mode: bool) -> logging.Formatter:
    if json_mode and _HAS_JSON:
        return jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(run_id)s',
            datefmt='%Y-%m-%dT%H:%M:%S%z'
        )
    return logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s [%(run_id)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def setup_logging_from_env() -> str:
    """Initialize logging with a guaranteed 'run_id' on every record."""
    run_id = os.getenv("RUN_ID", str(uuid.uuid4()))

    # Inject run_id globally into every LogRecord (robust in Py3.13)
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "run_id"):
            record.run_id = run_id
        return record
    logging.setLogRecordFactory(record_factory)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)
    json_mode = os.getenv("LOG_JSON", "false").lower() == "true"
    log_file = os.getenv("LOG_FILE", "etl.log")
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    root = logging.getLogger()
    root.setLevel(log_level)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = _build_formatter(json_mode)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    try:
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        # Falls kein Schreibrecht – weiter nur mit Console
        pass

    if log_level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging initialized")
    return run_id
