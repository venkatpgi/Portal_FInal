"""True-trial start date (PI 2026-10-14), shared by the CONSORT counts and the
Log of All Births alerts. Log entries dated before it are real but are not
part of the trial's flow. Override with the TRIAL_START_DATE env var."""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

TRIAL_START_DATE = os.getenv("TRIAL_START_DATE", "2026-10-14")


def trial_start() -> date:
    return date.fromisoformat(TRIAL_START_DATE)


def is_pre_trial(event_date, created_at=None) -> Optional[bool]:
    """True when the event (else the record's creation) is before the start."""
    d = event_date if event_date is not None else created_at
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    elif not isinstance(d, date):
        try:
            d = date.fromisoformat(str(d)[:10])
        except ValueError:
            return None
    return d < trial_start()
