"""Which DMS sheets can be opened, and for what (PI 2026-11-03).

New readings go on today's sheet, or yesterday's until 08:00 (unchanged).
An earlier sheet, from the date of birth to the end of stay, opens for
corrections: saved readings can be edited or removed, nothing added. It
closes once any of that day's Helper 2 / 4 / 5 days is locked (Submit),
because the DMS has then been signed off into the CRF; an active Override &
Unlock on the locked Helper day reopens it. Day N = date of birth + N - 1,
as in stay_end.py. Corrections are kept in the audit log (audit_trail.py).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import HTTPException

CUTOFF_HOUR = 8          # = MML_DROPDOWN_CUTOFF_HOUR in datetime.js
HELPERS = ("Helper 2", "Helper 4", "Helper 5")
META = ("id", "date", "time", "slot_time")   # as hasEntryData in MinimalMonitoringLog.jsx


def open_dates(now: datetime) -> list[date]:
    """Sheets that take new readings."""
    today = now.date()
    return [today - timedelta(days=1), today] if now.hour < CUTOFF_HOUR else [today]


def sheet_mode(on: date, now: datetime, dob: date | None, end: date | None, locked_by: list[str]) -> dict:
    """{mode: open | correction | closed, reason}. locked_by: Helpers whose day for `on` is locked."""
    if on in open_dates(now):
        return {"mode": "open", "reason": None}
    if on > now.date():
        return {"mode": "closed", "reason": "This date is in the future."}
    if dob and on < dob:
        return {"mode": "closed", "reason": "This date is before the date of birth."}
    if end and on > end:
        return {"mode": "closed", "reason": "This date is after the end of stay."}
    if locked_by:
        return {"mode": "closed",
                "reason": f"{', '.join(locked_by)} for this day {'is' if len(locked_by) == 1 else 'are'} locked. "
                          "Ask the Global PI to unlock the Helper day to correct it."}
    return {"mode": "correction", "reason": None}


def _locked(row, now_utc: datetime) -> bool:
    if not row or row.submission_status != "submitted":
        return False
    return not (row.override_unlocked_until and row.override_unlocked_until > now_utc)


def locked_helpers(db, enrollment_id: str, dob: date | None) -> dict[date, list[str]]:
    """{calendar date: [Helper names locked that day]}."""
    from models import InfectGIHemaDayLog, MetabRenalVascEyeDayLog, RespCVNeuroDayLog
    if not dob:
        return {}
    now_utc = datetime.utcnow()
    out: dict[date, list[str]] = {}
    for name, model in zip(HELPERS, (RespCVNeuroDayLog, InfectGIHemaDayLog, MetabRenalVascEyeDayLog)):
        for row in db.query(model).filter(model.enrollment_id == enrollment_id,
                                          model.submission_status == "submitted"):
            if row.nicu_day and _locked(row, now_utc):
                out.setdefault(dob + timedelta(days=row.nicu_day - 1), []).append(name)
    return out


def _context(db, enrollment_id: str):
    from models import BirthResuscitation
    from stay_end import stay_end
    br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
    dob = br.date_of_birth if br else None
    end = stay_end(db, enrollment_id)
    return dob, (end["date"] if end else None)


def sheet_dates(db, enrollment_id: str, now: datetime) -> list[dict]:
    """Every sheet from the date of birth (or the open dates without one) to the
    end of stay or today, newest first, closed ones included with the reason."""
    dob, end = _context(db, enrollment_id)
    locks = locked_helpers(db, enrollment_id, dob)
    last = min(now.date(), end) if end else now.date()
    first = dob or open_dates(now)[0]
    out, d = [], last
    while d >= first:
        m = sheet_mode(d, now, dob, end, locks.get(d, []))
        out.append({"date": d.isoformat(), "mode": m["mode"], "reason": m["reason"]})
        d -= timedelta(days=1)
    return out


def check_sheet(db, enrollment_id: str, on_date: str, now: datetime) -> str:
    """Mode for a save to this sheet; raises 400/403 when the sheet is closed."""
    try:
        on = datetime.strptime(on_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="on_date must be YYYY-MM-DD")
    if on in open_dates(now):
        return "open"
    dob, end = _context(db, enrollment_id)
    m = sheet_mode(on, now, dob, end, locked_helpers(db, enrollment_id, dob).get(on, []))
    if m["mode"] == "closed":
        raise HTTPException(status_code=403 if "locked" in m["reason"] else 400, detail=m["reason"])
    return m["mode"]


def _parse(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def _has_value(entry) -> bool:
    return isinstance(entry, dict) and any(
        k not in META and v not in (None, "", [], False) for k, v in entry.items())


def new_readings(stored_raw, incoming_raw) -> list[str]:
    """Readings in a save that the sheet does not already hold, as 'block time'."""
    stored = _parse(stored_raw)
    ids = {str(e.get("id")) for rows in stored.values() if isinstance(rows, list)
           for e in rows if isinstance(e, dict) and e.get("id")}
    same = {json.dumps(e, sort_keys=True) for rows in stored.values() if isinstance(rows, list)
            for e in rows if isinstance(e, dict)}
    out = []
    for block, rows in _parse(incoming_raw).items():
        for e in rows if isinstance(rows, list) else []:
            if not _has_value(e):
                continue
            if e.get("id") and str(e["id"]) in ids:
                continue
            if not e.get("id") and json.dumps(e, sort_keys=True) in same:
                continue
            out.append(f"{block} {e.get('time') or e.get('time_range') or ''}".strip())
    return out
