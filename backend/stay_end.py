"""End of stay (PI 2026-10-31): once a baby has died or left, the DMS and the
Helper logs take no later days. The day of death or discharge stays open, so a
"did not survive" entered by mistake can be corrected there.

End = the earliest of the Form H discharge date (for a death, Form H's Date of
death, the same column) and the first Helper 5 "did not survive" day. Day 1 =
date of birth. Form H outcome Died with no date gives no end date yet.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import HTTPException


def end_of_stay(dob: date | None, discharge_date: date | None, outcome: str | None, death_days,
                death_time: str | None = None) -> dict | None:
    """{date, day, died, time} or None while the stay runs. time: Form H's time
    of death, only when that date is the end date."""
    first_death = min(death_days, default=None)
    ends = [d for d in (discharge_date, dob + timedelta(days=first_death - 1) if dob and first_death else None) if d]
    if not ends:
        return None
    end = min(ends)
    return {"date": end, "day": (end - dob).days + 1 if dob else first_death,
            "died": outcome == "Died" or first_death is not None,
            "time": (death_time or None) if outcome == "Died" and discharge_date == end else None}


def stay_end(db, enrollment_id: str) -> dict | None:
    from models import BirthResuscitation, MetabRenalVascEyeDayLog, NeonatalMorbidities
    br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
    nm = (db.query(NeonatalMorbidities).filter(NeonatalMorbidities.enrollment_id == enrollment_id)
          .order_by(NeonatalMorbidities.id.desc()).first())
    days = [r[0] for r in db.query(MetabRenalVascEyeDayLog.nicu_day)
            .filter(MetabRenalVascEyeDayLog.enrollment_id == enrollment_id,
                    MetabRenalVascEyeDayLog.survived_the_day.is_(False)) if r[0]]
    return end_of_stay(br.date_of_birth if br else None, nm.discharge_date if nm else None,
                       nm.outcome if nm else None, days, nm.death_time if nm else None)


def refusal(end: dict | None, nicu_day: int | None = None, on_date: str | None = None) -> str | None:
    """Why an entry for this day cannot be saved, or None."""
    if not end:
        return None
    late = (nicu_day is not None and end["day"] is not None and nicu_day > end["day"]) or (
        on_date is not None and end["date"] is not None and on_date > end["date"].isoformat())
    if not late:
        return None
    what = "died" if end["died"] else "left the hospital"
    return (f"This baby {what} on {end['date'].strftime('%d %b %Y')} (Day {end['day']}): no entries after that day. "
            "If that is wrong, correct Form H or the Helper 5 entry first.")


ENTRY_META = ("id", "date", "time", "slot_time")   # as hasEntryData in MinimalMonitoringLog.jsx


def _has_value(entry) -> bool:
    return isinstance(entry, dict) and any(k not in ENTRY_META and v not in (None, "", [], False)
                                           for k, v in entry.items())


def _entries(raw) -> dict:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def entries_after_death(end: dict | None, record_date: str, raw, known_raw=None) -> list[str]:
    """Times of DMS readings on the day of death later than the time of death.
    known_raw: readings already saved, left alone so a save is not blocked by them."""
    if not end or not end.get("time") or str(record_date) != end["date"].isoformat():
        return []
    known = {e.get("id") for rows in _entries(known_raw).values() if isinstance(rows, list)
             for e in rows if isinstance(e, dict)}
    late = []
    for rows in _entries(raw).values():
        for e in rows if isinstance(rows, list) else []:
            when = (e.get("time") or e.get("slot_time") or "") if isinstance(e, dict) else ""
            if _has_value(e) and e.get("id") not in known and str(e.get("date") or record_date) == str(record_date) \
                    and when[:5] > end["time"][:5]:
                late.append(when[:5])
    return sorted(late)


def is_blank_helper_day(values: dict) -> bool:
    """True when a Helper day holds no answer at all. An explicit No is an answer."""
    meta = ("enrollment_id", "nicu_day", "submission_status", "saved_at", "saved_by", "submitted_at", "submitted_by")
    for k, v in values.items():
        if k in meta or v in (None, "", []):
            continue
        if k.endswith("_json") and isinstance(v, str):
            try:
                rows = json.loads(v)
            except ValueError:
                return False
            if isinstance(rows, list) and not any(_has_value(r) for r in rows):
                continue
        return False
    return True


def refuse_after_stay(db, enrollment_id: str, nicu_day: int | None = None, on_date: str | None = None) -> None:
    message = refusal(stay_end(db, enrollment_id), nicu_day, on_date)
    if message:
        raise HTTPException(status_code=422, detail=message)
