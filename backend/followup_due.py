"""Form I follow-up checkpoints coming up (PI 2026-11-17).

Each randomised baby is assessed at 36, 40 and 44 weeks PMA (Form I). The
checkpoint date is the day the baby reaches that PMA (date of birth + the
weeks minus the gestation at birth, Form B), and the allowed window is that
date +/- WINDOW_DAYS (2 days, PI 2026-11-17).

  coming up   the window is open, or the date is within LEAD_DISCHARGED days
              (14) for a baby who has gone home, LEAD_IN_NICU days (7) for a
              baby still admitted
  overdue     the window closed with nothing entered (site summary
              "missed data", M5)

A checkpoint is done when Form I records the encounter (Direct /
Telephonic), a death at that checkpoint, or a reason for loss to follow-up.
A death on Form H / Helper 5 / Form I on or before a checkpoint ends the
list (as routers/dashboard.followup_states, CONSORT Boxes 9-11); "Consent
withdrawn" as the loss reason ends it too.

Shown in the site summary (page + Monday/Thursday email), the twice-daily
shift report and the ready-made report "Follow-up due". For a baby who has
gone home, an email goes to the Site PI and Site Scientists once per
checkpoint, EMAIL_DAYS (7) before the date (or at once if the baby is
already closer than that), between 08:00 and 20:00 IST, from the hourly
data-check run. IDs only. Training has no SES_SENDER_EMAIL and sends nothing.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape

logger = logging.getLogger(__name__)

CHECKPOINTS = (36, 40, 44)
WINDOW_DAYS = 2
LEAD_DISCHARGED = 14
LEAD_IN_NICU = 7
EMAIL_DAYS = 7
EMAIL_HOURS_IST = (8, 20)
ALERT_TABLE = "followup_reminder"
WITHDRAWN = "Consent withdrawn"
PORTAL_URL = "https://portaltrial.in/form-i/"


def checkpoint_date(dob: date | None, ga_days: int | None, wk: int) -> date | None:
    if dob is None or ga_days is None:
        return None
    return dob + timedelta(days=wk * 7 - ga_days)


def _answered(v) -> bool:
    return v is not None and str(v).strip() != ""


def pending(dob, ga_days, form_i, known_death: bool, death_date: date | None, today: date) -> list[dict]:
    """Checkpoints not yet entered on Form I, in order, with their window and
    stage ("upcoming" / "window" / "overdue")."""
    out = []
    for wk in CHECKPOINTS:
        due = checkpoint_date(dob, ga_days, wk)
        if due is None:
            break
        if getattr(form_i, f"death{wk}", None) is True or (
                known_death and (death_date is None or death_date <= due)):
            break
        reason = (getattr(form_i, f"ltfu{wk}_reason", None) or "").strip()
        if reason == WITHDRAWN:
            break
        if _answered(getattr(form_i, f"encounter{wk}_method", None)) or reason:
            continue
        frm, to = due - timedelta(days=WINDOW_DAYS), due + timedelta(days=WINDOW_DAYS)
        stage = "overdue" if today > to else "window" if today >= frm else "upcoming"
        out.append({"checkpoint": wk, "due": due, "window_from": frm, "window_to": to, "stage": stage,
                    "days_to_due": (due - today).days})
    return out


def is_coming_up(row: dict, home: bool) -> bool:
    if row["stage"] == "window":
        return True
    return row["stage"] == "upcoming" and row["days_to_due"] <= (LEAD_DISCHARGED if home else LEAD_IN_NICU)


def fmt(d: date) -> str:
    return d.strftime("%d %b %Y")


def when_text(row: dict) -> str:
    n = row["days_to_due"]
    if row["stage"] == "overdue":
        return f"window closed {fmt(row['window_to'])}"
    if n > 0:
        return f"in {n} day{'s' if n != 1 else ''}"
    return "today" if n == 0 else f"{-n} day{'s' if n != -1 else ''} ago, window open"


# ------------------------------------------------------------------ data
def collect(db, sites, today: date) -> list[dict]:
    """Every pending checkpoint of randomised babies born since the trial
    start at these sites: [{site, enrollment_id, home, ended_on, where, ...}]."""
    from models import BirthResuscitation, MetabRenalVascEyeDayLog, NeonatalMorbidities, Screening, StudyOutcomes
    from stay_end import end_of_stay
    from trial_dates import trial_start

    rows = (db.query(BirthResuscitation, Screening.site_name)
            .join(Screening, Screening.screening_id == BirthResuscitation.screening_id)
            .filter(Screening.is_deleted.isnot(True), Screening.site_name.in_(list(sites)),
                    BirthResuscitation.randomised.is_(True), BirthResuscitation.enrollment_id.isnot(None),
                    BirthResuscitation.date_of_birth >= trial_start())
            .order_by(Screening.site_name, BirthResuscitation.enrollment_id).all())
    if not rows:
        return []
    eids = [br.enrollment_id for br, _ in rows]
    form_i = {r.enrollment_id: r for r in db.query(StudyOutcomes).filter(StudyOutcomes.enrollment_id.in_(eids))
              .order_by(StudyOutcomes.id)}
    form_h = {r.enrollment_id: r for r in db.query(NeonatalMorbidities)
              .filter(NeonatalMorbidities.enrollment_id.in_(eids)).order_by(NeonatalMorbidities.id)}
    death_days = defaultdict(list)
    for eid, day in (db.query(MetabRenalVascEyeDayLog.enrollment_id, MetabRenalVascEyeDayLog.nicu_day)
                     .filter(MetabRenalVascEyeDayLog.enrollment_id.in_(eids),
                             MetabRenalVascEyeDayLog.survived_the_day.is_(False))):
        if day:
            death_days[eid].append(day)
    out = []
    for br, site in rows:
        eid, dob = br.enrollment_id, br.date_of_birth
        ga = br.gestation_weeks * 7 + (br.gestation_days or 0) if br.gestation_weeks is not None else None
        nm = form_h.get(eid)
        end = end_of_stay(dob, nm.discharge_date if nm else None, nm.outcome if nm else None, death_days[eid])
        died = bool(end and end["died"]) or (nm is not None and nm.outcome == "Died")
        so = form_i.get(eid)
        from death_alert import form_i_death
        fi_died, fi_date, _ = form_i_death(so) if so is not None else (False, None, None)
        death_date = (end["date"] if end and end["died"] else None) or fi_date
        home = bool(end and not end["died"] and not fi_died)
        where = (f"Discharged {fmt(end['date'])}" if home else "Died" if (died or fi_died) else "In NICU")
        for r in pending(dob, ga, so, died or fi_died, death_date, today):
            out.append({"site": site, "enrollment_id": eid, "home": home,
                        "ended_on": end["date"] if home else None, "where": where, **r})
    return out


def coming_up(rows: list[dict]) -> list[dict]:
    return sorted((r for r in rows if is_coming_up(r, r["home"])), key=lambda r: (r["due"], r["enrollment_id"]))


# ------------------------------------------------------------------ email
def _email(site_display: str, items: list[dict]) -> tuple[str, str]:
    n = len(items)
    subject = f"PORTAL: Form I follow-up due — {site_display} — {n} bab{'y' if n == 1 else 'ies'} at home"
    rows = "".join(
        f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eef2f7;"><strong>{escape(r["enrollment_id"])}</strong></td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">{r["checkpoint"]} wk PMA</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">{escape(fmt(r["due"]))} '
        f'({escape(when_text(r))})</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">{escape(fmt(r["window_from"]))} – '
        f'{escape(fmt(r["window_to"]))}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">{escape(r["where"])}</td>'
        f'<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;"><a href="{PORTAL_URL}{escape(r["enrollment_id"])}">'
        f'Form I</a></td></tr>' for r in items)
    th = '<th style="text-align:left;padding:6px 8px;border-bottom:2px solid #e2e8f0;font-size:12px;color:#475569;">'
    html = f"""<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<h2 style="font-size:18px;color:#00132c;">Form I follow-up due: babies at home</h2>
<p style="font-size:13px;">Site: {escape(site_display)}. Please arrange the visit or telephone call within the window
(checkpoint date ± {WINDOW_DAYS} days) and record it on Form I.</p>
<table style="border-collapse:collapse;font-size:13px;"><tr>{th}Baby</th>{th}Checkpoint</th>{th}Date</th>
{th}Window</th>{th}Status</th>{th}</th></tr>{rows}</table>
<p style="font-size:11px;color:#64748b;">One email per checkpoint, {EMAIL_DAYS} days before the date. The full
list (babies in the NICU too) is in the site summary and the shift report. IDs only. Do not reply; this mailbox
is not read.</p>
</body></html>"""
    return subject, html


def _ist_now(now_utc: datetime) -> datetime:
    return now_utc + timedelta(hours=5, minutes=30)


def send_reminders(db, now: datetime | None = None) -> int:
    """Email the site once per checkpoint for babies at home. Caller commits."""
    if not (os.environ.get("SES_SENDER_EMAIL") or "").strip():
        return 0
    now = now or datetime.utcnow()
    ist = _ist_now(now)
    if not (EMAIL_HOURS_IST[0] <= ist.hour < EMAIL_HOURS_IST[1]):
        return 0
    from audit_service import record_audit
    from daily_query_email import _site_display, recipients
    from email_service import send_email
    from models import AuditLog
    from site_summary import REPORT_SITES

    today = ist.date()
    due = [r for r in collect(db, REPORT_SITES, today)
           if r["home"] and r["stage"] in ("upcoming", "window") and r["days_to_due"] <= EMAIL_DAYS]
    if not due:
        return 0
    sent_keys = {(a.enrollment_id, (a.new_values or {}).get("checkpoint"))
                 for a in db.query(AuditLog).filter(AuditLog.table_name == ALERT_TABLE, AuditLog.action == "EMAIL",
                                                    AuditLog.enrollment_id.in_([r["enrollment_id"] for r in due]))}
    by_site = defaultdict(list)
    for r in due:
        if (r["enrollment_id"], r["checkpoint"]) not in sent_keys:
            by_site[r["site"]].append(r)
    plan = recipients(db)
    sent = 0
    for site, items in by_site.items():
        to = plan.get(site, [])
        if not to:
            logger.warning("follow-up reminder: no Site PI / Scientist email for %s", site)
            continue
        subject, html = _email(_site_display(site), items)
        if send_email(to, subject, html):
            for r in items:
                record_audit(db, user_id=None, username="system", action="EMAIL", table_name=ALERT_TABLE,
                             enrollment_id=r["enrollment_id"],
                             new_values={"checkpoint": r["checkpoint"], "due": r["due"].isoformat(),
                                         "recipients": len(to)})
            sent += 1
    return sent
