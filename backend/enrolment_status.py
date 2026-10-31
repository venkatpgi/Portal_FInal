"""Enrolment status (PI 2026-10-31): the 8-to-8 message nurses used to count by
hand, generated from the portal for the site's WhatsApp group. Counts only, so
no ID or name leaves the portal; nothing by arm.

The window is the last finished 8 am-8 pm or 8 pm-8 am (India time), so a
report generated at 08:15 covers last night. A record counts in the window
of:
  files screened / eligible  when the Gestation Log entry was saved (the log
                             has a date but no time). Retrospective "missed"
                             entries are left out; a woman logged twice in the
                             window counts once.
  consent / refused / not    Form A consent date and time, else its screening
  approached                 date and time.
  randomised                 Form B date and time of birth, else when Form B
                             was saved. Counts babies.
A form saved after the report is not picked up by a later report if its own
date and time fall in the earlier window.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from clinical_time import clinical_now
from deps import logins_from_trial
from ga_log_status import norm_cr
from site_summary import _site_display

IST_OFFSET = timedelta(hours=5, minutes=30)
SCREENED_FROM_WEEKS = 25
LINES = (("screened", "No. of files screened, 25 weeks and above"), ("eligible", "No. of eligible mothers"),
         ("consented", "No. given consent"), ("refused", "Refused consent"),
         ("not_approached", "Not approached for consent"), ("randomised", "No. randomised (babies)"))


def window_of(now: datetime) -> tuple[datetime, datetime]:
    """(start, end) of the last finished 12 hours, on the 8 o'clock marks."""
    eight_am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now < eight_am:
        end = eight_am - timedelta(hours=12)
    elif now.hour < 20:
        end = eight_am
    else:
        end = eight_am + timedelta(hours=12)
    return end - timedelta(hours=12), end


def message_of(site_name: str, start: datetime, counts: dict, training: bool = False) -> str:
    morning = start.hour == 20
    lines = [f"Good {'morning' if morning else 'evening'}", f"PORTAL Trial: {site_name}",
             f"Data from {start.strftime('%d/%m/%y')} ({'8pm-8am' if morning else '8am-8pm'})"]
    lines += [f"{i}. {label} - {counts[key]:02d}" for i, (key, label) in enumerate(LINES, 1)]
    return "\n".join((["TRAINING SITE: practice data"] if training else []) + lines)


def build(db, site: str, now: datetime | None = None) -> dict:
    from models import BirthResuscitation, GACheckEntry, Screening
    start, end = window_of(now or clinical_now())

    def inside(t):
        return t is not None and start <= t < end

    checks = (db.query(GACheckEntry)
              .filter(GACheckEntry.site_name == site, GACheckEntry.created_at >= start - IST_OFFSET,
                      GACheckEntry.created_at < end - IST_OFFSET).all())
    screened, eligible = {}, {}
    for c in checks:
        if (c.identification_type or "").startswith("Missed") or (c.gestation_weeks or 0) < SCREENED_FROM_WEEKS:
            continue
        woman = norm_cr(c.mother_uid) or f"entry {c.id}"
        screened[woman] = True
        if c.eligible is True:
            eligible[woman] = True

    forms = (db.query(Screening.consent_given, Screening.consent_datetime, Screening.screening_datetime)
             .filter(Screening.site_name == site, Screening.is_deleted.isnot(True)).all())
    answers = [f.consent_given for f in forms if inside(f.consent_datetime or f.screening_datetime)]

    babies = (db.query(BirthResuscitation.date_of_birth, BirthResuscitation.time_of_birth,
                       BirthResuscitation.created_at)
              .join(Screening, Screening.screening_id == BirthResuscitation.screening_id)
              .filter(Screening.site_name == site, Screening.is_deleted.isnot(True),
                      BirthResuscitation.randomised.is_(True)).all())
    randomised = 0
    for b in babies:
        if b.date_of_birth and b.time_of_birth:
            randomised += inside(datetime.combine(b.date_of_birth, b.time_of_birth))
        elif b.created_at:
            randomised += inside(b.created_at + IST_OFFSET)

    counts = {"screened": len(screened), "eligible": len(eligible), "consented": answers.count("Yes"),
              "refused": answers.count("No"), "not_approached": answers.count("Not approached"),
              "randomised": randomised}
    site_name = _site_display(site)
    return {"site": site, "site_name": site_name, "from": start.isoformat(timespec="minutes"),
            "to": end.isoformat(timespec="minutes"), "counts": counts,
            "message": message_of(site_name, start, counts, logins_from_trial())}
