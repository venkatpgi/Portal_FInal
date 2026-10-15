"""Run every data-quality check and reconcile data_queries (hourly timer).

    cd /home/ubuntu/portal/backend && venv/bin/python run_data_checks.py

Runs only against the database in DATABASE_URL; the systemd timer uses the
trial server's .env. Prints a one-line summary for the journal.
"""
import logging
import sys

logging.basicConfig(level=logging.WARNING)

from db import SessionLocal  # noqa: E402
from data_checks import run_checks  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        counts = run_checks(db)
    finally:
        db.close()
    print("data checks:", counts)
    return 1 if counts.get("failed_checks") else 0


if __name__ == "__main__":
    sys.exit(main())
