"""Dashboard Tasks: forms that are due but missing (PI 2026-10-20).

Used by both /dashboard/ops-summary (Tasks tab) and the data-quality action
list. The old rules flagged every consented woman without Form B (most were
simply still pregnant), flagged Form I as soon as a baby was randomised
(it is filled at 36/40/44 wk PMA and at discharge or death), and checked
only the first week of Helper 2. Now a form is a task only once it is due:

- delivered_no_form_b: consented (not withdrawn), no Form B, and a birth
  with her CR is in the Log of All Births, or her pregnancy follow-up says
  "Delivered here".
- consented_overdue_no_birth: consented, no Form B, no birth logged, no
  pregnancy outcome recorded, and her GA today (GA at screening + days
  since) is >= 37w0d -- check whether she delivered or record the outcome.
- ppv_no_form_c: Form B says PPV was needed (randomised or not), no Form C.
- form_i_due: PPV baby, no Form I, and PMA >= 36w0d (GA at birth + age)
  or the stay has ended (Form H discharge/death date, or a Helper 5 "did not
  survive" day).
- daily_logs_missing: PPV baby with 2 or more days missing in Helper 2, 4
  or 5, counting Day 1 to yesterday (stopping at discharge/death).

ROP items (rop_detected_no_form_g, rop_form_mismatch) are unchanged and
still come from SQL / rop_consistency in routers/dashboard.py.
"""
from datetime import date, datetime

from form_completion import helper_last_required_day, nicu_day_today

ACTION_LABELS = {
    "delivered_no_form_b": "Delivered (birth logged) but Form B not entered",
    "consented_overdue_no_birth": "Consented, now ≥37 wk, no birth logged: check delivery or record the pregnancy outcome on Form A",
    "ppv_no_form_c": "PPV baby, Form C (Maternal Details) missing",
    "form_i_due": "Form I (Study Outcomes) due (≥36 wk PMA or discharged/died) but missing",
    "daily_logs_missing": "Helper 2 / 4 / 5 daily logs: 2 or more days missing",
    "rop_detected_no_form_g": "ROP detected on Helper 5 but Form G screening missing for that date",
    "rop_form_mismatch": "Form H vs Form G ROP mismatch (unreviewed)",
}

# Keys counted as "pending forms" / "log gaps" in the ops-summary KPIs.
PENDING_FORM_KEYS = ("delivered_no_form_b", "ppv_no_form_c", "form_i_due")
LOG_GAP_KEYS = ("daily_logs_missing",)

TERM_DAYS = 37 * 7
PMA_36_DAYS = 36 * 7
MIN_MISSING_DAYS = 2
HELPERS = (2, 4, 5)


def _ga_days(weeks, days):
    if weeks is None:
        return None
    return int(weeks) * 7 + int(days or 0)


def _fmt_ga(total):
    return f"{total // 7}w{total % 7}d"


def woman_tasks(w, today: date):
    """w: dict with screening_id, site, consent_given, consent_withdrawn,
    has_form_b, birth_logged, pregnancy_outcome, ga_weeks, ga_days,
    screened_on (date). Returns a list of (key, detail)."""
    if w.get("consent_given") != "Yes" or w.get("consent_withdrawn") or w.get("has_form_b"):
        return []
    outcome = w.get("pregnancy_outcome")
    if w.get("birth_logged") or outcome == "Delivered here":
        return [("delivered_no_form_b", "birth logged" if w.get("birth_logged") else "follow-up: delivered here")]
    if outcome:
        return []
    ga = _ga_days(w.get("ga_weeks"), w.get("ga_days"))
    if ga is None or not w.get("screened_on"):
        return []
    now = ga + (today - w["screened_on"]).days
    if now >= TERM_DAYS:
        return [("consented_overdue_no_birth", f"now {_fmt_ga(now)}")]
    return []


def baby_tasks(b, now: datetime):
    """b: dict with enrollment_id, site, required_resuscitation, dob (date),
    ga_birth_weeks, ga_birth_days, has_form_c, has_form_i, discharge_date,
    death_day (first Helper 5 'did not survive' NICU day or None),
    helper_days {2: set, 4: set, 5: set}. Returns a list of (key, detail)."""
    if b.get("required_resuscitation") is not True:
        return []
    out = []
    if not b.get("has_form_c"):
        out.append(("ppv_no_form_c", ""))
    dob = b.get("dob")
    if not dob:
        return out
    end_day = None
    if b.get("discharge_date"):
        end_day = max(1, (b["discharge_date"] - dob).days + 1)
    if b.get("death_day"):
        end_day = b["death_day"] if end_day is None else min(end_day, b["death_day"])

    if not b.get("has_form_i"):
        ga = _ga_days(b.get("ga_birth_weeks"), b.get("ga_birth_days"))
        pma = ga + (now.date() - dob).days if ga is not None else None
        if end_day is not None:
            out.append(("form_i_due", "stay ended"))
        elif pma is not None and pma >= PMA_36_DAYS:
            out.append(("form_i_due", f"PMA {_fmt_ga(pma)}"))

    last = helper_last_required_day(nicu_day_today(dob, now), end_day)
    if last:
        gaps = []
        for h in HELPERS:
            logged = (b.get("helper_days") or {}).get(h) or set()
            missing = sum(1 for d in range(1, last + 1) if d not in logged)
            if missing >= MIN_MISSING_DAYS:
                gaps.append(f"Helper {h}: {missing} of {last} days")
        if gaps:
            out.append(("daily_logs_missing", "; ".join(gaps)))
    return out


# ------------------------------------------------------------------ database
def iter_form_tasks(db, now: datetime | None = None):
    """Yield (key, site, ref, detail) for every live Form A / Form B."""
    from models import (BirthLogEntry, BirthResuscitation, InfectGIHemaDayLog, MaternalDetails,
                        MetabRenalVascEyeDayLog, NeonatalMorbidities, RespCVNeuroDayLog,
                        Screening, StudyOutcomes)
    now = now or datetime.now()
    screenings = (db.query(Screening).filter(Screening.is_deleted.isnot(True),
                                             Screening.site_name.isnot(None), Screening.site_name != "")
                  .all())
    by_sid = {s.screening_id: s for s in screenings}
    births = {b.screening_id: b for b in db.query(BirthResuscitation)
              .filter(BirthResuscitation.screening_id.in_(list(by_sid))).all()} if by_sid else {}
    logged = {sid for (sid,) in db.query(BirthLogEntry.matched_screening_id)
              .filter(BirthLogEntry.match_status == "matched",
                      BirthLogEntry.matched_screening_id.isnot(None)).all()}

    for s in screenings:
        screened_on = s.screening_datetime or s.created_at
        if isinstance(screened_on, datetime):
            screened_on = screened_on.date()
        w = {"consent_given": s.consent_given, "consent_withdrawn": bool(getattr(s, "consent_withdrawn", None)),
             "has_form_b": s.screening_id in births, "birth_logged": s.screening_id in logged,
             "pregnancy_outcome": getattr(s, "pregnancy_outcome", None),
             "ga_weeks": s.gestation_weeks, "ga_days": s.gestation_days, "screened_on": screened_on}
        for key, detail in woman_tasks(w, now.date()):
            yield key, s.site_name, s.screening_id, detail

    eids = [b.enrollment_id for b in births.values() if b.enrollment_id and b.required_resuscitation is True]
    if not eids:
        return
    form_c = {e for (e,) in db.query(MaternalDetails.enrollment_id).filter(MaternalDetails.enrollment_id.in_(eids))}
    form_i = {e for (e,) in db.query(StudyOutcomes.enrollment_id).filter(StudyOutcomes.enrollment_id.in_(eids))}
    discharge = {e: d for e, d in db.query(NeonatalMorbidities.enrollment_id, NeonatalMorbidities.discharge_date)
                 .filter(NeonatalMorbidities.enrollment_id.in_(eids)) if d}
    helper_days = {e: {2: set(), 4: set(), 5: set()} for e in eids}
    for h, model in ((2, RespCVNeuroDayLog), (4, InfectGIHemaDayLog), (5, MetabRenalVascEyeDayLog)):
        for e, d in db.query(model.enrollment_id, model.nicu_day).filter(model.enrollment_id.in_(eids)):
            helper_days[e][h].add(d)
    death_day = {}
    for e, d in (db.query(MetabRenalVascEyeDayLog.enrollment_id, MetabRenalVascEyeDayLog.nicu_day)
                 .filter(MetabRenalVascEyeDayLog.enrollment_id.in_(eids),
                         MetabRenalVascEyeDayLog.survived_the_day.is_(False))):
        death_day[e] = min(d, death_day.get(e, d))

    for b in births.values():
        if b.enrollment_id not in helper_days:
            continue
        s = by_sid[b.screening_id]
        baby = {"required_resuscitation": b.required_resuscitation, "dob": b.date_of_birth,
                "ga_birth_weeks": b.gestation_weeks, "ga_birth_days": b.gestation_days,
                "has_form_c": b.enrollment_id in form_c, "has_form_i": b.enrollment_id in form_i,
                "discharge_date": discharge.get(b.enrollment_id), "death_day": death_day.get(b.enrollment_id),
                "helper_days": helper_days[b.enrollment_id]}
        for key, detail in baby_tasks(baby, now):
            yield key, s.site_name, b.enrollment_id, detail
