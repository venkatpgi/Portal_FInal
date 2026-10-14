"""Cross-checks a Log of All Births entry (backend/models.py::BirthLogEntry)
against existing Form A screenings, so a GA-eligible (25w0d-31w6d) delivery
with no matching screening can be surfaced as a completeness alert on the
dashboard -- the digital equivalent of the paper "Log of All Births" CRF's
own "Screening form filled (Y/N), If Y, screening ID" column, computed
automatically instead of hand-typed so it can't go stale.

Matching runs against ParticipantPII (the single canonical identity store
across Form A/B/C, per the 2026-08-18 PII-dedup fix) rather than Screening
itself, since Screening's own mother_name/maternal_uid columns are stripped
blank by pii_service.split_and_store_pii on every save. maternal_uid is
encrypted at rest, so this can't be a SQL WHERE -- candidates are narrowed
by site_name (plain, indexed) and matched in Python after decrypting.

A second cross-check (2026-09-24) also matches against GACheckEntry (the
Gestation (Inclusion Criteria) Screening Log -- ga_check.py/GACheckLog.jsx).

**Restructured 2026-09-24 (PI-directed) from one combined `match_status`
enum into two INDEPENDENT facts, each surfaced as its own badge on
LogOfAllBirths.jsx, both shown together whenever both apply:**
- `match_status` -- purely about Form A: "matched" | "in_range_no_match"
  | "out_of_range" | "ga_unknown".
  **2026-10-14 (PI):** "matched" now means a CR-number match ONLY. A
  same-name Form A is "possible_match" (shown for staff to verify), and
  only when the GA is consistent -- see ga_consistent(); a same-name woman
  whose GA cannot fit is not linked at all. Matches are refreshed on read
  (refresh_birth_log_matches), not only when the birth is saved. ("never_checked" no longer exists as
  a match_status value -- see below.)
- `ga_log_missing` -- purely about the Gestation Log: True if no
  Gestation Log entry exists for this woman at all, regardless of
  whether Form A was also found. A woman CAN have `match_status=
  "matched"` (Form A exists) AND `ga_log_missing=True` at the same time
  -- a direct/orphan Form A entry that bypassed the log entirely. The PI
  explicitly wants this shown even when Form A is fine, since it's real
  data-quality information (is staff actually using the intended triage
  workflow?) independent of whether Form A itself is missing.

Only computed (True/False, never left at the SQL-NULL default) when
`match_status` is "matched" or "in_range_no_match" -- left NULL for
out_of_range/ga_unknown, since this log is preterm-triage-only and
asking "was her GA ever checked" makes no sense for a term birth.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from models import BirthLogEntry, GACheckEntry, ParticipantPII, Screening

# Same inclusion window used by the CONSORT dashboard's _GA_IN_WINDOW_SQL
# (backend/routers/dashboard.py) -- kept in sync manually, not imported,
# since routers/dashboard.py builds this as a raw SQL fragment rather than
# a reusable Python constant.
GA_MIN_DAYS = 25 * 7
GA_MAX_DAYS = 31 * 7 + 6


def _normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _normalize_uid(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-]+", "", str(value).strip().upper())


def classify_ga_range(gestation_weeks: Optional[int], gestation_days: Optional[int]) -> str:
    """Returns 'ga_unknown' | 'in_range' | 'out_of_range'."""
    if gestation_weeks is None:
        return "ga_unknown"
    total_days = int(gestation_weeks) * 7 + int(gestation_days or 0)
    if GA_MIN_DAYS <= total_days <= GA_MAX_DAYS:
        return "in_range"
    return "out_of_range"


# A name-only link is accepted (as "possible_match", never "matched") only
# when the GA adds up: Form A's GA plus the days from Form A to the birth
# must be within this many days of the GA recorded at birth (PI 2026-10-14,
# after several same-name women were linked to the wrong Form A).
GA_PLAUSIBLE_TOLERANCE_DAYS = 14


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


def ga_consistent(form_ga_weeks, form_ga_days, form_date, birth_ga_weeks, birth_ga_days,
                  date_of_birth, tolerance_days: int = GA_PLAUSIBLE_TOLERANCE_DAYS) -> Optional[bool]:
    """Could the woman on this Form A have given birth at this GA on this date?
    None when any input is missing (cannot tell)."""
    form_date, date_of_birth = _as_date(form_date), _as_date(date_of_birth)
    if form_ga_weeks is None or birth_ga_weeks is None or not form_date or not date_of_birth:
        return None
    expected = int(form_ga_weeks) * 7 + int(form_ga_days or 0) + (date_of_birth - form_date).days
    actual = int(birth_ga_weeks) * 7 + int(birth_ga_days or 0)
    return abs(expected - actual) <= tolerance_days


def _site_candidates(db: Session, site_name: Optional[str]) -> list[dict]:
    """Form A identity + GA for one site (PII is encrypted, so matched in Python)."""
    query = db.query(
        ParticipantPII.screening_id, ParticipantPII.enrollment_id,
        ParticipantPII.maternal_uid, ParticipantPII.mother_first_name,
        ParticipantPII.mother_surname,
        Screening.gestation_weeks, Screening.gestation_days, Screening.created_at,
    ).outerjoin(Screening, Screening.screening_id == ParticipantPII.screening_id)
    if site_name:
        query = query.filter(ParticipantPII.site_name == site_name)
    out = []
    for r in query.all():
        out.append({
            "screening_id": r.screening_id,
            "enrollment_id": r.enrollment_id,
            "uid": _normalize_uid(r.maternal_uid),
            "name": _normalize(" ".join(filter(None, [r.mother_first_name, r.mother_surname]))),
            "ga_weeks": r.gestation_weeks,
            "ga_days": r.gestation_days,
            "form_date": r.created_at,
        })
    return out


def match_against(candidates: Iterable[dict], mother_uid, mother_name, gestation_weeks,
                  gestation_days, date_of_birth, ga_rows: Optional[Iterable] = None) -> dict:
    """Pure matching core. `candidates` as from _site_candidates(); `ga_rows`
    are the site's Gestation Log rows (objects with mother_uid/mother_name)."""
    candidates = list(candidates)
    ga_range = classify_ga_range(gestation_weeks, gestation_days)
    target_uid = _normalize_uid(mother_uid)
    target_name = _normalize(mother_name)

    hit, status = None, None
    # Pass 1: exact CR match -- the only thing that counts as "matched".
    if target_uid:
        hit = next((c for c in candidates if c["uid"] and c["uid"] == target_uid), None)
        if hit:
            status = "matched"
    # Pass 2: same full name -- only ever a "possible_match", and only when
    # the GA is consistent (or cannot be checked). A same-name woman whose
    # GA cannot fit is a different woman and is not linked at all.
    if not hit and target_name:
        same_name = [c for c in candidates if c["name"] and c["name"] == target_name]
        fits = [(ga_consistent(c["ga_weeks"], c["ga_days"], c["form_date"],
                               gestation_weeks, gestation_days, date_of_birth), c) for c in same_name]
        hit = next((c for ok, c in fits if ok is True), None) or next((c for ok, c in fits if ok is None), None)
        if hit:
            status = "possible_match"

    if not status:
        status = {"ga_unknown": "ga_unknown", "in_range": "in_range_no_match"}.get(ga_range, "out_of_range")

    ga_log_missing: Optional[bool] = None
    if status in ("matched", "possible_match", "in_range_no_match"):
        rows = list(ga_rows or [])
        found = (target_uid and any(_normalize_uid(g.mother_uid) == target_uid for g in rows)) or \
                (target_name and any(_normalize(g.mother_name) == target_name for g in rows))
        ga_log_missing = not found

    return {
        "matched_screening_id": hit["screening_id"] if hit else None,
        "matched_enrollment_id": hit["enrollment_id"] if hit else None,
        "match_status": status,
        "ga_log_missing": ga_log_missing,
    }


def _site_ga_rows(db: Session, site_name: Optional[str]) -> list:
    query = db.query(GACheckEntry.mother_uid, GACheckEntry.mother_name)
    if site_name:
        query = query.filter(GACheckEntry.site_name == site_name)
    return query.all()


def match_birth_log_entry(
    db: Session,
    site_name: Optional[str],
    mother_uid: Optional[str],
    mother_name: Optional[str],
    gestation_weeks: Optional[int],
    gestation_days: Optional[int],
    date_of_birth=None,
) -> dict:
    """Returns {"matched_screening_id", "matched_enrollment_id", "match_status", "ga_log_missing"}."""
    return match_against(_site_candidates(db, site_name), mother_uid, mother_name,
                         gestation_weeks, gestation_days, date_of_birth,
                         ga_rows=_site_ga_rows(db, site_name))


_MATCH_FIELDS = ("matched_screening_id", "matched_enrollment_id", "match_status", "ga_log_missing")


def refresh_birth_log_matches(db: Session, site_names: Optional[Iterable[str]] = None) -> int:
    """Re-match every Log of All Births entry of the given sites (all when
    None) against the current Form A and Gestation Log data, and save the
    rows whose result changed. A match used to be computed only when the
    birth was saved, so a Form A created afterwards (or deleted) left it
    stale. Called from the read paths that rely on it. Returns rows changed."""
    query = db.query(BirthLogEntry)
    if site_names is not None:
        site_names = [s for s in site_names if s]
        if not site_names:
            return 0
        query = query.filter(BirthLogEntry.site_name.in_(site_names))
    entries = query.all()
    by_site: dict = {}
    for e in entries:
        by_site.setdefault(e.site_name, []).append(e)
    changed = 0
    for site, rows in by_site.items():
        cands, ga_rows = _site_candidates(db, site), _site_ga_rows(db, site)
        for e in rows:
            m = match_against(cands, e.mother_uid, e.mother_name, e.gestation_weeks,
                              e.gestation_days, e.date_of_birth, ga_rows=ga_rows)
            if any(getattr(e, f) != m[f] for f in _MATCH_FIELDS):
                for f in _MATCH_FIELDS:
                    setattr(e, f, m[f])
                changed += 1
    if changed:
        db.commit()
    return changed
