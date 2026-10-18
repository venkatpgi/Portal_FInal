"""Re-run the data checks shortly after data is saved (Phase 1 on-save trigger).

Called by a middleware in main.py after every successful write. Debounced:
the first save starts a 60-second timer and further saves in that window
join it, so a burst of autosaves causes one run. Each worker process has its
own timer; data_checks.run_checks takes an advisory lock, so overlapping
runs from two workers or the hourly timer simply skip.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

DELAY_SECONDS = 60
_lock = threading.Lock()
_pending = False


def request_run() -> None:
    global _pending
    with _lock:
        if _pending:
            return
        _pending = True
    t = threading.Timer(DELAY_SECONDS, _run)
    t.daemon = True
    t.start()


def _run() -> None:
    global _pending
    with _lock:
        _pending = False
    from db import SessionLocal
    from data_checks import run_checks
    db = SessionLocal()
    try:
        run_checks(db)
    except Exception:
        logger.exception("on-save data checks failed")
        db.rollback()
    finally:
        db.close()
