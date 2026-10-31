"""End of stay (PI 2026-10-31): once a baby has died or left, the DMS and the
Helper logs take no later days. The day of death or discharge stays open, so a
"did not survive" entered by mistake can be corrected there.

End = the earliest of the Form H discharge date (for a death, the date in the
same field) and the first Helper 5 "did not survive" day. Day 1 = date of birth.
Form H outcome Died with no date gives no end date, so nothing is locked yet.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException


def end_of_stay(dob: date | None, discharge_date: date | None, outcome: str | None, death_days) -> dict | None:
    """{date, day, died} or None while the stay runs."""
    first_death = min(death_days, default=None)
    ends = [d for d in (discharge_date, dob + timedelta(days=first_death - 1) if dob and first_death else None) if d]
    if not ends:
        return None
    end = min(ends)
    return {"date": end, "day": (end - dob).days + 1 if dob else first_death,
            "died": outcome == "Died" or first_death is not None}


def stay_end(db, enrollment_id: str) -> dict | None:
    from models import BirthResuscitation, MetabRenalVascEyeDayLog, NeonatalMorbidities
    br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
    nm = (db.query(NeonatalMorbidities).filter(NeonatalMorbidities.enrollment_id == enrollment_id)
          .order_by(NeonatalMorbidities.id.desc()).first())
    days = [r[0] for r in db.query(MetabRenalVascEyeDayLog.nicu_day)
            .filter(MetabRenalVascEyeDayLog.enrollment_id == enrollment_id,
                    MetabRenalVascEyeDayLog.survived_the_day.is_(False)) if r[0]]
    return end_of_stay(br.date_of_birth if br else None, nm.discharge_date if nm else None,
                       nm.outcome if nm else None, days)


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


def refuse_after_stay(db, enrollment_id: str, nicu_day: int | None = None, on_date: str | None = None) -> None:
    message = refusal(stay_end(db, enrollment_id), nicu_day, on_date)
    if message:
        raise HTTPException(status_code=422, detail=message)
