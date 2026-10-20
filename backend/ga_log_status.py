"""Live status of a Gestation (Inclusion Criteria) Screening Log entry
(PI / trial nurses 2026-10-14). Computed every time the log is read, never
stored: the stored `eligible` stays "eligible at the time of the check",
which is what the CONSORT boxes count.

Delivered = a birth of the SAME mother's CR number at the same site (Log of
All Births, or Form B of a Form A with that CR) on/after the check date whose
GA at birth fits the GA at the check plus the days since (within 14 days).
The CR is the only way to match; name and dates are checks, never a match on
their own (same-name matches were mostly wrong in live data). A mother keeps
her CR across pregnancies, so a birth before the check or with an impossible
GA is not her delivery: shown as "cr_check" for the nurse to look at.

Not delivered -> current GA = GA at check + days since, and:
  overdue      current GA >= 42w0d (no birth found: a missing/mistyped birth entry)
  crossed_32   eligible at the check, now >= 32w0d
  now_eligible logged (Reliable) before 25w0d, now 25w0d-31w6d

Entries checked before the trial start date (PI 2026-10-17): a "CR match --
check" or "Delivery not logged?" is shown as "pre_trial" instead. Those women
delivered before the trial began and are outside its flow, so they raise no
data query. "Now eligible" and the "Eligible, no Form A" gap still apply: a
woman logged before the start can still enter the trial.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Iterable, Optional

GA_MIN_DAYS = 25 * 7
GA_MAX_DAYS = 31 * 7 + 6
OVERDUE_DAYS = 42 * 7
PLAUSIBLE_DAYS = 14
# A birth logged up to this many days BEFORE the check date still counts when
# its GA fits (e.g. a check entered the day after the birth). An earlier
# pregnancy of the same mother can never fit, so the GA check protects it.
BIRTH_BEFORE_CHECK_DAYS = 28


def norm_cr(value) -> str:
    return re.sub(r"[\s\-]+", "", str(value or "").strip().upper())


def _tokens(name) -> set:
    return {t for t in re.split(r"[^a-z]+", str(name or "").lower()) if len(t) > 2}


def names_differ(a, b) -> bool:
    """True only when both names are known and no word of one resembles a
    word of the other (allows spelling variants: pooonam / Poonam)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    for x in ta:
        for y in tb:
            if x == y or x in y or y in x or SequenceMatcher(None, x, y).ratio() >= 0.75:
                return False
    return True


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _ga_days(weeks, days) -> Optional[int]:
    if weeks is None:
        return None
    return int(weeks) * 7 + int(days or 0)


def live_status(entry: dict, births: Iterable[dict], today: date,
                trial_start: Optional[date] = None) -> dict:
    """Status of one entry; see the module docstring. `trial_start` turns a
    pre-trial cr_check / overdue into "pre_trial" (the reason stays in
    live_note)."""
    out = _live_status(entry, births, today)
    check = _as_date(entry.get("check_date"))
    if (trial_start and check and check < trial_start
            and out["live_status"] in ("cr_check", "overdue")):
        if out["live_status"] == "overdue":
            out["live_note"] = "No birth found for this CR by 42 weeks"
        out["live_status"] = "pre_trial"
    return out


def _live_status(entry: dict, births: Iterable[dict], today: date) -> dict:
    """entry: check_date, gestation_weeks/days, eligible, found_iufd, ga_source,
    mother_uid, mother_name, has_form_a. births (same site): mother_uid,
    mother_name, date_of_birth, gestation_weeks/days, source."""
    check = _as_date(entry.get("check_date"))
    ga0 = _ga_days(entry.get("gestation_weeks"), entry.get("gestation_days"))
    cr = norm_cr(entry.get("mother_uid"))
    out = {"live_status": None, "current_ga_days": None, "delivered_on": None,
           "delivered_ga_days": None, "delivered_source": None, "live_note": None}
    if entry.get("found_iufd"):
        return out

    # Delivery: same mother's CR, born on/after the check, GA fits.
    if cr and check:
        fits, misfits = [], []
        for b in births:
            if norm_cr(b.get("mother_uid")) != cr:
                continue
            dob = _as_date(b.get("date_of_birth"))
            bga = _ga_days(b.get("gestation_weeks"), b.get("gestation_days"))
            reasons = []
            gap = (dob - check).days if dob else None
            fits_ga = (None if ga0 is None or bga is None
                       else abs(ga0 + gap - bga) <= PLAUSIBLE_DAYS)
            if dob is None:
                reasons.append("no date of birth")
            elif gap < 0 and not (fits_ga and -gap <= BIRTH_BEFORE_CHECK_DAYS):
                reasons.append("born before the check date")
            elif fits_ga is False:
                reasons.append("GA at birth does not fit")
            if names_differ(entry.get("mother_name"), b.get("mother_name")):
                reasons.append("name differs")
            (misfits if reasons else fits).append((dob, bga, b.get("source"), reasons))
        if fits:
            dob, bga, src, _ = min(fits, key=lambda x: x[0])
            out.update(live_status="delivered", delivered_on=dob.isoformat(),
                       delivered_ga_days=bga, delivered_source=src)
            return out
        # A birth before the check is most likely an earlier pregnancy of the
        # same mother -- not a problem with this entry. Flag only the rest.
        current = [m for m in misfits if m[0] is not None
                   and (m[0] - check).days >= -BIRTH_BEFORE_CHECK_DAYS
                   and m[3] != ["born before the check date"]]
        if current:
            dob, _, src, reasons = current[0]
            out.update(live_status="cr_check",
                       live_note=f"Same CR in {src} (born {dob.isoformat()}): {', '.join(reasons)}")
            return out

    if ga0 is None or check is None:
        return out
    now = ga0 + (today - check).days
    out["current_ga_days"] = now
    if now >= OVERDUE_DAYS:
        out["live_status"] = "overdue"
    elif entry.get("eligible") is True and now > GA_MAX_DAYS:
        out["live_status"] = "crossed_32"
    elif (entry.get("eligible") is False and entry.get("ga_source") == "Reliable"
          and ga0 < GA_MIN_DAYS and GA_MIN_DAYS <= now <= GA_MAX_DAYS and not entry.get("has_form_a")):
        out["live_status"] = "now_eligible"
    return out


def still_eligible_gap(entry: dict, status: dict) -> bool:
    """'Eligible, no Form A yet': eligible at the check, no Form A, and still
    pregnant within the window (or newly in it)."""
    if entry.get("has_form_a"):
        return False
    if status["live_status"] == "now_eligible":
        return True
    return entry.get("eligible") is True and status["live_status"] is None


def attach_live_status(db, records, today):
    """Live 'Delivered / Crossed 32 wk / Now eligible / Overdue' status for
    Gestation Log entries (ga_log_status.py). Computed per read, not stored;
    must run before PII masking. Births come from the Log of All Births and
    from Form B of any Form A carrying the same mother's CR."""
    from models import BirthLogEntry, BirthResuscitation, ParticipantPII, Screening
    from trial_dates import trial_start

    by_site = {}
    for r in records:
        by_site.setdefault(r.site_name, []).append(r)
    for site, rows in by_site.items():
        births = [
            {"mother_uid": b.mother_uid, "mother_name": b.mother_name, "date_of_birth": b.date_of_birth,
             "gestation_weeks": b.gestation_weeks, "gestation_days": b.gestation_days,
             "source": "Log of All Births"}
            for b in db.query(BirthLogEntry).filter(BirthLogEntry.site_name == site).all()
        ]
        consent_by_sid = dict(db.query(Screening.screening_id, Screening.consent_given).filter(
            Screening.site_name == site, Screening.is_deleted.isnot(True)).all())
        live_sids = set(consent_by_sid)
        pii = {p.screening_id: p for p in db.query(ParticipantPII).filter(
            ParticipantPII.site_name == site).all() if p.screening_id in live_sids}
        form_a_crs = {norm_cr(p.maternal_uid) for p in pii.values() if norm_cr(p.maternal_uid)}
        # Her Form A consent, shown when she is logged again on a readmission
        # (refused: not approached again; PI 2026-10-20)
        consent_by_cr = {norm_cr(p.maternal_uid): consent_by_sid.get(sid)
                         for sid, p in pii.items() if norm_cr(p.maternal_uid)}
        if pii:
            for fb in db.query(BirthResuscitation).filter(
                    BirthResuscitation.screening_id.in_(list(pii)),
                    BirthResuscitation.date_of_birth.isnot(None)).all():
                p = pii[fb.screening_id]
                births.append({"mother_uid": p.maternal_uid,
                               "mother_name": " ".join(x for x in [p.mother_first_name, p.mother_surname] if x),
                               "date_of_birth": fb.date_of_birth, "gestation_weeks": fb.gestation_weeks,
                               "gestation_days": fb.gestation_days, "source": "Form B"})
        for r in rows:
            entry = {"check_date": r.check_date, "gestation_weeks": r.gestation_weeks,
                     "gestation_days": r.gestation_days, "eligible": r.eligible,
                     "found_iufd": r.found_iufd, "ga_source": r.ga_source,
                     "mother_uid": r.mother_uid, "mother_name": r.mother_name,
                     # a link to a deleted Form A no longer counts
                     "has_form_a": bool(r.continued_to_screening and r.screening_id in live_sids)
                                   or (norm_cr(r.mother_uid) in form_a_crs if norm_cr(r.mother_uid) else False)}
            st = live_status(entry, births, today, trial_start())
            for k, v in st.items():
                setattr(r, k, v)
            r.has_form_a = entry["has_form_a"]
            r.form_a_consent = consent_by_cr.get(norm_cr(r.mother_uid)) if norm_cr(r.mother_uid) else None
            r.in_gap = still_eligible_gap(entry, st)
