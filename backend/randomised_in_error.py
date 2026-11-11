"""Babies randomised in error (PI 2026-11-11).

The PORTAL blender picks the next allocation the moment it is activated, so
an activation for a baby who never needed PPV uses an allocation that cannot
be given back. Form B records it: PPV not required + "Was the PORTAL blender
activated (allocation used)?" Yes, with the enrollment ID the blender showed,
the time, the reason and who activated it.

Such a baby is "randomised in error":
  - never counted as randomised (randomised is stored False), never followed:
    enrolment ends at Form B, as for any baby who did not need PPV;
  - the enrollment ID is kept for good (never replaced by NR-, never reused);
  - a data query asks the site PI to confirm, with the Global PI's sign-off
    (data_checks RANDOMISED_IN_ERROR), and an email goes the same day;
  - CONSORT shows a line under Randomised; not by arm (blinded).

Analysis plan (PI 2026-11-11): excluded from all analyses, reported in
CONSORT with reasons, a protocol deviation reported to the IEC and DSMB.
The site PI or Global PI may reclassify (PPV required = Yes) when the baby
did need PPV at activation; nobody else can undo the record.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from html import escape

logger = logging.getLogger(__name__)

REASONS = (
    "Blender activated in error",
    "Wrong baby or twin",
    "Baby breathing, PPV not needed",
    "Other",
)
LABEL = "Randomised in error (did not need PPV)"
ALERT_TABLE = "randomised_in_error_alert"
ENROLLMENT_ID_RE = re.compile(r"^\d{2}-([A-D])-\d{3}$", re.IGNORECASE)
RECLASSIFY_ROLES = ("superadmin", "site_pi")
PORTAL_URL = "https://portaltrial.in/data-queries"


class RuleError(ValueError):
    """A save the rules refuse; the caller turns it into a 422."""


def is_in_error(b) -> bool:
    """Blender activated and PPV not required (works on rows, dicts, SimpleNamespace)."""
    if b is None:
        return False
    get = b.get if isinstance(b, dict) else (lambda k: getattr(b, k, None))
    return get("blender_activated") is True and get("required_resuscitation") is False


def apply_rules(payload: dict, prior, enrollment_id: str | None, role: str | None) -> dict:
    """Check and complete one Form B save. `payload` is the incoming fields
    (None = not sent), `prior` the saved row or None. Returns the payload to
    store. Raises RuleError."""
    def now(field):
        v = payload.get(field)
        return v if v is not None else getattr(prior, field, None)

    was = is_in_error(prior)
    ppv = now("required_resuscitation")
    activated = now("blender_activated")
    may_reclassify = (role or "") in RECLASSIFY_ROLES

    if was:
        if ppv is True and not may_reclassify:
            raise RuleError(
                "This baby is recorded as randomised in error. Only the site PI or the Global PI can change "
                "\"PPV required\" to Yes (when the baby did need PPV at activation).")
        if ppv is False and activated is not True:
            raise RuleError(
                "The blender allocation for this baby was used and stays on record. If the blender was not "
                "activated, ask the Global PI to correct it.")
        if enrollment_id and prior.enrollment_id and enrollment_id.upper() != prior.enrollment_id.upper():
            raise RuleError(f"The enrollment ID {prior.enrollment_id} was used by the blender and cannot be changed.")

    out = dict(payload)
    if ppv is not False:
        # PPV required (or not answered): the ordinary randomisation path.
        if payload.get("blender_activated") is True:
            raise RuleError("\"Was the blender activated in error?\" applies only when PPV was not required.")
        if was:   # reclassified by the site PI / Global PI
            out["blender_activated"] = False
        return out

    if activated is True:
        m = ENROLLMENT_ID_RE.match((enrollment_id or "").strip())
        if not m:
            raise RuleError("Enter the enrollment ID the blender showed (e.g. 01-B-007): the allocation it "
                            "used must stay on record.")
        out["randomised"] = False
        out["blender_letter"] = m.group(1).upper()
    return out


def apply_to_model(data, prior, enrollment_id: str | None, role: str | None):
    """apply_rules on a Pydantic Form B model; changed fields count as sent."""
    sent = data.model_dump(exclude_unset=True)
    out = apply_rules(sent, prior, enrollment_id, role)
    changed = {k: v for k, v in out.items() if k not in sent or sent[k] != v}
    return data.model_copy(update=changed) if changed else data


# ------------------------------------------------------------------ alert email
def _email(eid: str, site: str, reason: str | None, when: str | None) -> tuple[str, str]:
    subject = f"PORTAL: Randomised in error — {site} — {eid}"
    html = f"""<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<h2 style="font-size:18px;color:#b45309;">Blender activated for a baby who did not need PPV</h2>
<p>Site: {escape(site)}<br>Enrollment ID: <strong>{escape(eid)}</strong><br>
Activated at: {escape(when or "not recorded")}<br>Reason: {escape(reason or "not recorded")}</p>
<p>The allocation is used and the baby is not followed. The site PI is asked to confirm in Data queries
that the baby did not need PPV at activation (Global PI signs off). Report it as a protocol deviation to the
IEC and the DSMB.</p>
<p><a href="{PORTAL_URL}">Open Data queries in the portal</a></p>
<p style="font-size:11px;color:#64748b;">IDs only. Do not reply; this mailbox is not read.</p>
</body></html>"""
    return subject, html


def send_alerts(db, now: datetime | None = None) -> int:
    """One email per baby randomised in error, to the site and all-site
    recipients (site PI, scientists, Project Scientist, Global PI). Caller commits."""
    if not (os.environ.get("SES_SENDER_EMAIL") or "").strip():
        return 0
    from sqlalchemy import text

    from audit_service import record_audit
    from daily_query_email import ALL_SITES, _site_display, recipients
    from email_service import send_email
    from models import AuditLog

    rows = db.execute(text("""
        SELECT b.enrollment_id, s.site_name, b.blender_activation_reason, b.blender_activation_reason_other,
               b.date_of_birth, b.blender_activation_time
        FROM birth_resuscitation b JOIN screenings s ON s.screening_id = b.screening_id
        WHERE b.blender_activated IS TRUE AND b.required_resuscitation IS FALSE AND s.is_deleted IS NOT TRUE
    """)).all()
    if not rows:
        return 0
    done = {r[0] for r in db.query(AuditLog.enrollment_id).filter(
        AuditLog.table_name == ALERT_TABLE, AuditLog.action == "EMAIL").all()}
    plan = None
    sent = 0
    for eid, site, reason, other, dob, at in rows:
        if eid in done:
            continue
        plan = plan if plan is not None else recipients(db)
        to = sorted(set(plan.get(site, []) + plan.get(ALL_SITES, [])))
        why = f"{reason}: {other}" if reason == "Other" and other else reason
        when = " ".join(x for x in (dob.strftime("%d-%m-%Y") if dob else None,
                                     at.strftime("%H:%M") if at else None) if x)
        subject, html = _email(eid, _site_display(site), why, when or None)
        if send_email(to, subject, html):
            record_audit(db, user_id=None, username="system", action="EMAIL", table_name=ALERT_TABLE,
                         enrollment_id=eid, new_values={"recipients": len(to)})
            sent += 1
    return sent
