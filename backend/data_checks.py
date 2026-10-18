"""Data-quality check catalogue and runner (Phase 1, design agreed with the
Global PI 2026-10-14/15).

Each check is a fixed rule that returns findings: one problem on one record.
run_checks() turns findings into rows of data_queries:
  new finding                      -> open
  finding gone                     -> resolved (automatically)
  resolved query found again       -> reopened
  confirmed-correct query          -> stays closed unless its facts change
Checks never change clinical data. Facts and details carry ids, numbers and
dates only (no names, CR or phone numbers): they are shown to scientists and
later sent to Bedrock.

Ages: a query turns amber 72 h and red 7 days after `due_at`. Timeliness
checks (a form not complete) are only raised once 72 h have passed.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Callable, Iterable, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

AMBER_AFTER = timedelta(hours=72)
RED_AFTER = timedelta(days=7)
OPEN_STATES = ("open", "acknowledged", "awaiting_signoff")
ENROLLMENT_RE = re.compile(r"^\d{2}-[A-D]-\d{3}$", re.IGNORECASE)
RUN_LOCK_KEY = 7342001  # pg advisory lock id for run_checks


def _dt(d) -> Optional[datetime]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime.combine(d, time(0))
    return None


def _fmt_ga(days) -> str:
    return "-" if days is None else f"{days // 7}w {days % 7}d"


class Check:
    def __init__(self, check_id: str, area: str, description: str, fn: Callable,
                 second_signoff: bool = False, raise_after: timedelta = timedelta(0), version: int = 1):
        self.check_id, self.area, self.description = check_id, area, description
        self.fn, self.second_signoff, self.raise_after, self.version = fn, second_signoff, raise_after, version


def finding(site, record_type, record_key, title, detail, facts, due_at) -> dict:
    return {"site_name": site, "record_type": record_type, "record_key": str(record_key),
            "title": title, "detail": detail, "facts": facts, "due_at": _dt(due_at)}


# ---------------------------------------------------------------- Gestation Log
def _ga_rows(db, today):
    from ga_log_status import attach_live_status
    from models import GACheckEntry
    rows = db.query(GACheckEntry).all()
    attach_live_status(db, rows, today)
    return rows


def _ga_reach(r, days):
    """Calendar date the woman reaches `days` of gestation."""
    if r.check_date is None or r.gestation_weeks is None:
        return r.check_date
    ga0 = r.gestation_weeks * 7 + (r.gestation_days or 0)
    return r.check_date + timedelta(days=days - ga0)


def check_ga_eligible_no_form_a(ctx):
    out = []
    for r in ctx["ga"]:
        if getattr(r, "in_gap", False) and getattr(r, "live_status", None) is None:
            out.append(finding(r.site_name, "ga_check", r.id, "Eligible woman with no Form A",
                               f"Gestation Log entry #{r.id} ({r.check_date}, {r.gestation_weeks}w {r.gestation_days or 0}d) "
                               f"was eligible and has no Form A; now {_fmt_ga(getattr(r, 'current_ga_days', None))}.",
                               {"entry": r.id, "check_date": str(r.check_date)}, r.check_date))
    return out


def check_ga_now_eligible(ctx):
    out = []
    for r in ctx["ga"]:
        if getattr(r, "live_status", None) == "now_eligible":
            out.append(finding(r.site_name, "ga_check", r.id, "Reached 25 weeks: Form A due",
                               f"Gestation Log entry #{r.id} was {r.gestation_weeks}w {r.gestation_days or 0}d on {r.check_date}; "
                               f"now {_fmt_ga(getattr(r, 'current_ga_days', None))}, inside the 25w0d-31w6d window, with no Form A.",
                               {"entry": r.id}, _ga_reach(r, 25 * 7)))
    return out


def check_ga_cr_mismatch(ctx):
    out = []
    for r in ctx["ga"]:
        if getattr(r, "live_status", None) == "cr_check":
            out.append(finding(r.site_name, "ga_check", r.id, "CR number matches a birth that does not fit",
                               f"Gestation Log entry #{r.id} ({r.check_date}): {getattr(r, 'live_note', '') or ''}".rstrip(": "),
                               {"entry": r.id, "note": getattr(r, "live_note", None)}, ctx["now"]))
    return out


def check_ga_delivery_not_logged(ctx):
    out = []
    for r in ctx["ga"]:
        if getattr(r, "live_status", None) == "overdue":
            out.append(finding(r.site_name, "ga_check", r.id, "Delivery not logged by 42 weeks",
                               f"Gestation Log entry #{r.id} ({r.check_date}, {r.gestation_weeks}w {r.gestation_days or 0}d) "
                               f"is now {_fmt_ga(getattr(r, 'current_ga_days', None))} and no birth with this CR number is "
                               "in the Log of All Births or a Form B.",
                               {"entry": r.id}, _ga_reach(r, 42 * 7)))
    return out


# ---------------------------------------------------------- Log of All Births
def check_birth_preterm_no_form_a(ctx):
    out = []
    for b in ctx["births"]:
        if (b.match_status == "in_range_no_match" and not ctx["pre_trial"](b)
                and not (b.reason_not_approached or "").strip()):
            out.append(finding(b.site_name, "birth_log", b.id, "Preterm birth with no Form A and no reason",
                               f"Log of All Births entry #{b.id}: born {b.date_of_birth} at "
                               f"{b.gestation_weeks}w {b.gestation_days or 0}d (inside the trial window), no Form A found "
                               "and no 'reason not approached' recorded.",
                               {"entry": b.id, "dob": str(b.date_of_birth)}, b.date_of_birth))
    return out


def check_birth_possible_match(ctx):
    out = []
    for b in ctx["births"]:
        if b.match_status == "possible_match" and not ctx["pre_trial"](b):
            out.append(finding(b.site_name, "birth_log", b.id, "Birth may belong to a Form A: CR differs",
                               f"Log of All Births entry #{b.id} (born {b.date_of_birth}) has the same mother's name as "
                               f"Form A {b.matched_screening_id} and a fitting GA, but a different CR number.",
                               {"entry": b.id, "screening": b.matched_screening_id}, ctx["now"]))
    return out


# ------------------------------------------------------- identity / eligibility
def check_formb_bad_enrollment_id(ctx):
    return [finding(r["site_name"], "enrollment", r["enrollment_id"] or f"birth#{r['id']}",
                    "Form B enrollment ID is not a complete ID",
                    f"Form B row #{r['id']} (screening {r['screening_id']}) has enrollment ID {r['enrollment_id']!r}.",
                    {"birth_row": r["id"], "eid": r["enrollment_id"]}, ctx["now"])
            for r in ctx["formb"]
            if not (r["enrollment_id"] and (ENROLLMENT_RE.match(r["enrollment_id"]) or r["enrollment_id"].upper().startswith("NR-")))]


def check_formb_split_baby(ctx):
    by_sid = defaultdict(list)
    for r in ctx["formb"]:
        if r["screening_id"]:
            by_sid[r["screening_id"]].append(r)
    return [finding(rows[0]["site_name"], "screening", sid, "One Form A has more than one Form B",
                    f"Screening {sid} has Form B rows {sorted(str(r['enrollment_id']) for r in rows)}.",
                    {"eids": sorted(str(r["enrollment_id"]) for r in rows)}, ctx["now"])
            for sid, rows in by_sid.items() if len(rows) > 1]


def check_formb_not_eligible(ctx):
    return [finding(r["site_name"], "enrollment", r["enrollment_id"], "Form B for a screening that is not Eligible",
                    f"{r['enrollment_id']} (screening {r['screening_id']}): Form A status {r['screening_status']!r}, "
                    f"consent {r['consent_given']!r}, randomised {r['randomised']}.",
                    {"status": r["screening_status"], "consent": r["consent_given"], "randomised": r["randomised"]}, ctx["now"])
            for r in ctx["formb"]
            if r["screening_id"] and r["site_name"] is not None and (r["screening_status"] or "") != "Eligible"]


def check_formb_no_form_a(ctx):
    return [finding(None, "enrollment", r["enrollment_id"] or f"birth#{r['id']}", "Form B with no matching Form A",
                    f"Form B {r['enrollment_id']} points to screening {r['screening_id']}, which does not exist.",
                    {"screening": r["screening_id"]}, ctx["now"])
            for r in ctx["formb"] if r["screening_id"] and r["site_name"] is None]


def check_formA_duplicate_identifier(ctx):
    from identifier_duplicates import normalize_identifier
    groups = defaultdict(list)
    for p in ctx["pii"]:
        for label, raw in (("CR number", p.maternal_uid), ("Hospital number", p.hospital_admission_number)):
            v = normalize_identifier(raw)
            if v:
                groups[(p.site_name, label, v)].append(p.screening_id)
    out = []
    for (site, label, _), sids in groups.items():
        if len(sids) > 1:
            for sid in sids:
                others = sorted(x for x in sids if x != sid)
                out.append(finding(site, "screening", sid, f"Same {label} on another Form A",
                                   f"Form A {sid} shares its {label} with {', '.join(others)} at {site}.",
                                   {"label": label, "others": others}, ctx["now"]))
    return out


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def check_formA_possible_same_woman(ctx):
    """Two Form A at one site whose CR numbers differ by 1-2 characters (a
    typo or an extra digit), with names that match and GAs that fit the dates:
    probably the same woman screened twice (PI 2026-10-17, after one woman got
    three Form A from three slightly different CRs). Exact CR matches are
    FORMA_DUPLICATE_ID's job."""
    from ga_log_status import names_differ
    from identifier_duplicates import normalize_identifier
    by_site = defaultdict(list)
    for p in ctx["pii"]:
        cr = normalize_identifier(p.maternal_uid)
        name = " ".join(x for x in (p.mother_first_name, p.mother_surname) if x)
        if cr and name:
            by_site[p.site_name].append((p.screening_id, cr, name))
    ga = ctx["screening_ga"]
    pairs = defaultdict(set)
    for site, rows in by_site.items():
        for i, (sa, ca, na) in enumerate(rows):
            for sb, cb, nb in rows[i + 1:]:
                if ca == cb or abs(len(ca) - len(cb)) > 2 or _edit_distance(ca, cb) > 2:
                    continue
                if names_differ(na, nb):
                    continue
                (ga_a, da), (ga_b, db_) = ga.get(sa, (None, None)), ga.get(sb, (None, None))
                if None not in (ga_a, ga_b, da, db_) and abs(ga_a + (db_ - da).days - ga_b) > 14:
                    continue
                pairs[(site, sa)].add(sb)
                pairs[(site, sb)].add(sa)
    return [finding(site, "screening", sid, "Possibly the same woman on another Form A",
                    f"Form A {sid} and {', '.join(sorted(others))} at {site}: CR numbers differ by one or two "
                    "characters, names match and the GA fits. Keep one Form A; correct or delete the other.",
                    {"others": sorted(others)}, ctx["now"])
            for (site, sid), others in sorted(pairs.items())]


def check_day1_date_mismatch(ctx):
    return [finding(ctx["site_of_eid"].get(r[0]), "enrollment", r[0], "Form E Day 1 date differs from birth date",
                    f"{r[0]}: Form E Day 1 date {r[1]} vs Form B date of birth {r[2]}; helper days and PMA dates will shift.",
                    {"day1": str(r[1]), "dob": str(r[2])}, ctx["now"])
            for r in ctx["day1_mismatch"]]


# ----------------------------------------------------------------- timeliness
def _incomplete(form_label, table, offset_days=0):
    def fn(ctx):
        done = ctx["complete"].get(table, set())
        out = []
        for r in ctx["formb"]:
            if r["randomised"] is not True or not r["date_of_birth"] or not r["enrollment_id"]:
                continue
            if r["enrollment_id"] in done:
                continue
            due = r["date_of_birth"] + timedelta(days=offset_days)
            out.append(finding(r["site_name"], "enrollment", r["enrollment_id"], f"{form_label} not complete",
                               f"{r['enrollment_id']}: {form_label} not complete; due from "
                               f"{'birth' if not offset_days else 'end of day 1 of life'} ({due}).",
                               {"form": table}, due))
        return out
    return fn


CHECKS = [
    Check("GA_ELIGIBLE_NO_FORM_A", "Gestation Log", "Eligible woman, still pregnant, with no Form A", check_ga_eligible_no_form_a),
    Check("GA_NOW_ELIGIBLE", "Gestation Log", "Logged before 25 weeks, now in the window, no Form A", check_ga_now_eligible),
    Check("GA_CR_MISMATCH", "Gestation Log", "CR number matches a birth whose GA or name does not fit", check_ga_cr_mismatch, second_signoff=True),
    Check("GA_DELIVERY_NOT_LOGGED", "Gestation Log", "No birth found by 42 weeks", check_ga_delivery_not_logged),
    Check("BIRTH_PRETERM_NO_FORM_A", "Log of All Births", "Preterm birth with no Form A and no reason not approached", check_birth_preterm_no_form_a),
    Check("BIRTH_POSSIBLE_MATCH", "Log of All Births", "Birth may belong to a Form A with a different CR", check_birth_possible_match, second_signoff=True),
    Check("FORMB_BAD_ENROLLMENT_ID", "Identity", "Form B enrollment ID incomplete or malformed", check_formb_bad_enrollment_id, second_signoff=True),
    Check("FORMB_SPLIT_BABY", "Identity", "One Form A with more than one Form B", check_formb_split_baby, second_signoff=True),
    Check("FORMB_NO_FORM_A", "Identity", "Form B pointing to a Form A that does not exist", check_formb_no_form_a, second_signoff=True),
    Check("FORMA_DUPLICATE_ID", "Identity", "Same CR or hospital number on two Form A", check_formA_duplicate_identifier, second_signoff=True),
    Check("FORMA_POSSIBLE_SAME_WOMAN", "Identity", "Two Form A with nearly the same CR, matching name and GA", check_formA_possible_same_woman, second_signoff=True),
    Check("FORMB_NOT_ELIGIBLE", "Consent / eligibility", "Form B saved for a screening that is not Eligible", check_formb_not_eligible, second_signoff=True),
    Check("DAY1_DATE_MISMATCH", "Clinical consistency", "Form E Day 1 date differs from Form B date of birth", check_day1_date_mismatch),
    Check("FORM_C_INCOMPLETE", "Form timeliness", "Form C (maternal details) not complete", _incomplete("Form C", "maternal_details"), raise_after=AMBER_AFTER),
    Check("FORM_D_INCOMPLETE", "Form timeliness", "Form D (postnatal day 1) not complete", _incomplete("Form D", "postnatal_day1", 1), raise_after=AMBER_AFTER),
    Check("FORM_E_INCOMPLETE", "Form timeliness", "Form E (NICU admission) not complete", _incomplete("Form E", "nicu_admission"), raise_after=AMBER_AFTER),
]
CHECKS_BY_ID = {c.check_id: c for c in CHECKS}


def _context(db, now: datetime, today: date) -> dict:
    from birth_log_matching import refresh_birth_log_matches
    from models import BirthLogEntry, ParticipantPII, Screening
    from trial_dates import is_pre_trial

    refresh_birth_log_matches(db)
    formb = [dict(r) for r in db.execute(text("""
        SELECT b.id, b.enrollment_id, b.screening_id, b.date_of_birth, b.randomised,
               s.consent_given, s.screening_status, s.site_name
        FROM birth_resuscitation b LEFT JOIN screenings s ON s.screening_id = b.screening_id
    """)).mappings()]
    complete = {}
    for table in ("maternal_details", "postnatal_day1", "nicu_admission"):
        complete[table] = {r[0] for r in db.execute(text(
            f"SELECT DISTINCT enrollment_id FROM {table} WHERE is_complete IS TRUE"))}
    live_screens = db.query(Screening.screening_id, Screening.gestation_weeks, Screening.gestation_days,
                            Screening.screening_datetime).filter(Screening.is_deleted.isnot(True)).all()
    live_sids = {r[0] for r in live_screens}
    screening_ga = {sid: ((w * 7 + (d or 0)) if w is not None else None, dt.date() if dt else None)
                    for sid, w, d, dt in live_screens}
    return {
        "now": now,
        "ga": _ga_rows(db, today),
        "births": db.query(BirthLogEntry).all(),
        "pre_trial": lambda b: bool(is_pre_trial(b.date_of_birth, b.created_at)),
        "formb": formb,
        "site_of_eid": {r["enrollment_id"]: r["site_name"] for r in formb},
        "pii": [p for p in db.query(ParticipantPII).all() if p.screening_id in live_sids],
        "complete": complete,
        "screening_ga": screening_ga,
        "day1_mismatch": db.execute(text("""
            SELECT n.enrollment_id, n.day1_date, b.date_of_birth
            FROM nicu_admission n JOIN birth_resuscitation b ON b.enrollment_id = n.enrollment_id
            WHERE n.day1_date IS NOT NULL AND b.date_of_birth IS NOT NULL AND n.day1_date <> b.date_of_birth
        """)).all(),
    }


def run_checks(db, now: Optional[datetime] = None, today: Optional[date] = None,
               only: Optional[Iterable[str]] = None) -> dict:
    """Run the catalogue and reconcile data_queries; commits. Returns counts."""
    from clinical_time import clinical_today
    from models import DataQuery

    now = now or datetime.utcnow()
    today = today or clinical_today()
    ctx = _context(db, now, today)  # may commit (birth-log match refresh)
    # One reconcile at a time across workers and the hourly timer: a
    # transaction-level advisory lock, released by the commit below.
    if db.get_bind().dialect.name == "postgresql":
        if not db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": RUN_LOCK_KEY}).scalar():
            db.rollback()
            return {"skipped": "another run in progress"}
    counts = defaultdict(int)
    checks = [c for c in CHECKS if not only or c.check_id in set(only)]
    existing = defaultdict(dict)
    for q in db.query(DataQuery).filter(DataQuery.check_id.in_([c.check_id for c in checks])).all():
        existing[q.check_id][(q.record_type, q.record_key)] = q

    for c in checks:
        try:
            found = c.fn(ctx)
        except Exception:  # one broken check must not stop the others
            logger.exception("data check %s failed", c.check_id)
            counts["failed_checks"] += 1
            continue
        seen = set()
        for f in found:
            if f["due_at"] and now < f["due_at"] + c.raise_after:
                continue  # not yet late enough to raise
            key = (f["record_type"], f["record_key"])
            if key in seen:
                continue  # one query per record per check (e.g. CR and hospital number both shared)
            seen.add(key)
            q = existing[c.check_id].get(key)
            if q is None:
                db.add(DataQuery(check_id=c.check_id, rule_version=c.version, site_name=f["site_name"],
                                 record_type=f["record_type"], record_key=f["record_key"], title=f["title"],
                                 detail=f["detail"], facts=f["facts"], needs_second_signoff=c.second_signoff,
                                 status="open", due_at=f["due_at"] or now, first_seen_at=now, last_seen_at=now))
                counts["opened"] += 1
                continue
            facts_changed = (q.facts or {}) != (f["facts"] or {})
            q.title, q.detail, q.last_seen_at, q.site_name = f["title"], f["detail"], now, f["site_name"]
            q.rule_version, q.needs_second_signoff = c.version, c.second_signoff
            if q.status == "resolved" or (q.status == "confirmed_correct" and facts_changed):
                q.status, q.resolved_at = "open", None
                q.acknowledged_by = q.acknowledged_at = None
                q.confirmed_by = q.confirmed_at = q.confirmed_reason = None
                q.signoff_by = q.signoff_at = None
                q.reopened_count = (q.reopened_count or 0) + 1
                counts["reopened"] += 1
            q.facts = f["facts"]
        for key, q in existing[c.check_id].items():
            if key not in seen and q.status in OPEN_STATES:
                q.status, q.resolved_at = "resolved", now
                counts["resolved"] += 1
    db.commit()
    counts["open_total"] = db.query(DataQuery).filter(DataQuery.status.in_(OPEN_STATES)).count()
    return dict(counts)


def colour(q, now: Optional[datetime] = None) -> str:
    """'red' / 'amber' / 'new' by time since due (open states only)."""
    now = now or datetime.utcnow()
    if q.status not in OPEN_STATES or q.due_at is None:
        return ""
    age = now - q.due_at
    return "red" if age >= RED_AFTER else "amber" if age >= AMBER_AFTER else "new"
