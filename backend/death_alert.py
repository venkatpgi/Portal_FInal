"""After a randomised baby's death (PI 2026-10-31).

Every death is an SAE. Staff write the report; the portal prepares it and
presses for it: Form Y, the AE form and the SAE list open pre-filled (drafts, nothing saved),
a banner shows the 24-hour deadline, and an email goes to the Site PI, Site
Scientists, Project Scientist and Global PI, with a reminder 12 hours later if
there is still no report. A death counts from Form H, Helper 5 or Form I,
wherever it was entered first.

The email goes from data_checks.run_checks, so it leaves about a minute after
the save, and the hourly run sends the reminder. Training has no
SES_SENDER_EMAIL and sends nothing. IDs only.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from html import escape

from sae_rules import event_title, is_fatal, on_list
from stay_end import stay_end

logger = logging.getLogger(__name__)

ALERT_TABLE = "death_alert"
REPORT_HOURS = 24
REMINDER_HOURS = 12
FORM_I_DEATHS = (("mortality_7_days", "mortality_7d"), ("mortality_28_days", "mortality_28d"), ("death36", "death36"),
                 ("death40", "death40"), ("death44", "death44"), ("mortality_in_hospital", "mortality_hospital"),
                 ("mortality_after_discharge", "mortality_after_discharge"))
PORTAL_URL = "https://portaltrial.in/form-y-sae/"


def form_i_death(so) -> tuple[bool, date | None, str | None]:
    """(died, date, time) from a Form I row."""
    for answer, prefix in FORM_I_DEATHS:
        if getattr(so, answer, None) is True:
            when = getattr(so, f"{prefix}_date", None)
            if when:
                return True, when, getattr(so, f"{prefix}_time", None)
    died = so is not None and any(getattr(so, a, None) is True for a, _ in FORM_I_DEATHS)
    return died, None, None


def report_due(when: date | None, at: str | None) -> datetime | None:
    if not when:
        return None
    clock = (at or "23:59")[:5]
    return datetime.fromisoformat(f"{when.isoformat()}T{clock}") + timedelta(hours=REPORT_HOURS)


def grade_5_on_form(events) -> bool:
    for e in events or []:
        if isinstance(e, dict) and (str(e.get("grade") or "").strip() == "5"
                                    or "death" in str(e.get("description") or "").lower()):
            return True
    return False


def has_death_report(reports) -> bool:
    return any((r.diagnosis or "").strip() and is_fatal(r) for r in reports)


def status(db, enrollment_id: str) -> dict:
    """{died, date, time, due, needs_report, needs_ae}. Only randomised babies."""
    from models import AdverseEvents, BirthResuscitation, SAEList, SAEReport, StudyOutcomes
    br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
    none = {"died": False, "date": None, "time": None, "due": None, "needs_report": False, "needs_ae": False,
            "needs_list": False, "list_term": None}
    if not br or br.randomised is not True:
        return none
    end = stay_end(db, enrollment_id)
    so = (db.query(StudyOutcomes).filter(StudyOutcomes.enrollment_id == enrollment_id)
          .order_by(StudyOutcomes.id.desc()).first())
    died, when, at = form_i_death(so)
    if end and end["died"]:
        died, when, at = True, end["date"], end["time"] or at
    if not died:
        return none
    ae = db.query(AdverseEvents).filter(AdverseEvents.enrollment_id == enrollment_id).first()
    reports = db.query(SAEReport).filter(SAEReport.enrollment_id == enrollment_id).all()
    listing = db.query(SAEList).filter(SAEList.enrollment_id == enrollment_id).first()
    fatal = [r for r in reports if (r.diagnosis or "").strip() and is_fatal(r)]
    term = event_title(fatal[-1].diagnosis, True) if fatal else "Death"
    due = report_due(when, at)
    return {"died": True, "date": when.isoformat() if when else None, "time": at,
            "due": due.isoformat(timespec="minutes") if due else None,
            "needs_report": not has_death_report(reports),
            "needs_ae": not grade_5_on_form(ae.events if ae else None),
            "needs_list": not on_list(listing.rows if listing else None, {"sae": term}), "list_term": term}


def _email(eid: str, site: str, s: dict, reminder: bool) -> tuple[str, str]:
    when = " ".join(x for x in (s["date"], s["time"]) if x) or "date not recorded"
    due = s["due"].replace("T", " ") if s["due"] else "24 hours after the death"
    title = "Reminder: SAE report still not filed" if reminder else "Death recorded: SAE report due"
    subject = f"PORTAL: {title} — {site} — {eid}"
    html = f"""<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<h2 style="font-size:18px;color:#b91c1c;">{escape(title)}</h2>
<p>Site: {escape(site)}<br>Enrolment ID: <strong>{escape(eid)}</strong><br>Death recorded: {escape(when)}<br>
SAE report due by: <strong>{escape(due)} IST</strong></p>
<p><a href="{PORTAL_URL}{escape(eid)}">Open Form Y in the portal</a></p>
<p style="font-size:11px;color:#64748b;">IDs only. Do not reply; this mailbox is not read.</p>
</body></html>"""
    return subject, html


def send_alerts(db, now: datetime | None = None) -> int:
    """First alert and the 12-hour reminder, once each. Caller commits."""
    if not (os.environ.get("SES_SENDER_EMAIL") or "").strip():
        return 0
    from sqlalchemy import text

    from audit_service import record_audit
    from daily_query_email import ALL_SITES, _site_display, recipients
    from email_service import send_email
    from models import AuditLog
    now = now or datetime.utcnow()
    candidates = db.execute(text("""
        SELECT b.enrollment_id, s.site_name FROM birth_resuscitation b
        JOIN screenings s ON s.screening_id = b.screening_id
        WHERE b.randomised IS TRUE AND s.is_deleted IS NOT TRUE AND (
          b.enrollment_id IN (SELECT enrollment_id FROM neonatal_morbidities WHERE outcome = 'Died')
          OR b.enrollment_id IN (SELECT enrollment_id FROM metab_renal_vasc_eye_day_logs WHERE survived_the_day IS FALSE)
          OR b.enrollment_id IN (SELECT enrollment_id FROM study_outcomes WHERE death36 IS TRUE OR death40 IS TRUE
              OR death44 IS TRUE OR mortality_7_days IS TRUE OR mortality_28_days IS TRUE
              OR mortality_in_hospital IS TRUE OR mortality_after_discharge IS TRUE))
    """)).all()
    if not candidates:
        return 0
    plan = recipients(db)
    sent = 0
    for eid, site in candidates:
        s = status(db, eid)
        if not s["needs_report"]:
            continue
        rows = (db.query(AuditLog).filter(AuditLog.table_name == ALERT_TABLE, AuditLog.enrollment_id == eid,
                                          AuditLog.action == "EMAIL").order_by(AuditLog.created_at).all())
        if len(rows) >= 2 or (rows and now - rows[0].created_at < timedelta(hours=REMINDER_HOURS)):
            continue
        reminder = bool(rows)
        to = sorted(set(plan.get(site, []) + plan.get(ALL_SITES, [])))
        subject, html = _email(eid, _site_display(site), s, reminder)
        if send_email(to, subject, html):
            record_audit(db, user_id=None, username="system", action="EMAIL", table_name=ALERT_TABLE,
                         enrollment_id=eid, new_values={"reminder": reminder, "recipients": len(to)})
            sent += 1
    return sent
