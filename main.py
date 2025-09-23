"""Entry point for Jira DC ETL.
Usage:
    python main.py run
"""
import sys
from loader.etl import run_once
from loader.logging_setup import setup_logging_from_env

def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        die("Usage: python main.py run")
    run_id = setup_logging_from_env()
    cmd = sys.argv[1]
    if cmd == "run":
        run_once(run_id=run_id)
    else:
        die(f"Unknown command: {cmd}")
