"""Follow-up calendar on Form H (PI 2026-11-19).

When a randomised baby leaves alive (Form H outcome Discharged, Back referred,
Discharged home on request or Left Against Medical Advice), the nurse books a
date with the family for each Form I checkpoint still to come (36 / 40 / 44
weeks PMA, followup_due.py), or records why no date could be fixed. Bookings
live in followup_bookings; Form I still records what actually happened.

Per checkpoint (calendar()):
  done      Form I already has the encounter or a loss-to-follow-up reason
  ended     a death or "Consent withdrawn" ends the follow-up
  in_nicu   the window closed on or before the day the baby left: assess it
            in the NICU and record it on Form I (nothing to book)
  bookable  a date from the later of (window start, day the baby left) to the
            window end (checkpoint date + 2 days); Clinic visit or Telephone
The web form will not Submit Form H until every bookable checkpoint has a
date or a reason. The tablet has no calendar yet: query FOLLOWUP_NOT_BOOKED.

Emails to the Site PI and Site Scientists (IDs only):
  booked    once the calendar is complete, and again whenever it changes
  reminder  REMIND_DAYS (2) before a booked date, 08:00-20:00 IST
  missed    the day after a booked date with nothing on Form I, 08:00-20:00 IST
plus data queries FOLLOWUP_BOOKED_MISSED and FOLLOWUP_BOOKING_OUTSIDE_WINDOW.
A booked checkpoint no longer gets followup_due's 7-day email.
The parent slip (slip_pdf) is printed at the bedside for the family and
carries the baby's name only when the user may see that site's PII.
Training has no SES_SENDER_EMAIL and sends nothing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape

import followup_due as fd

logger = logging.getLogger(__name__)

ALIVE_OUTCOMES = ("Discharged", "Back referred", "Discharged home on request", "Left Against Medical Advice")
MODES = ("Clinic visit", "Telephone")
REASONS = (
    "Family will call to fix the date",
    "Back-referral hospital will arrange it",
    "Family lives far away: telephone follow-up later",
    "Other",
)
REMIND_DAYS = 2
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")   # date.weekday() order
NOTICE_TABLE = "followup_booking_notice"
REMIND_TABLE = "followup_booking_reminder"
MISSED_TABLE = "followup_booking_missed"


# ------------------------------------------------------------------ rows
def bookings_by_key(db, eids) -> dict:
    from models import FollowupBooking
    eids = [e for e in eids if e]
    if not eids:
        return {}
    return {(b.enrollment_id, b.checkpoint): b
            for b in db.query(FollowupBooking).filter(FollowupBooking.enrollment_id.in_(eids))}


def booking_text(b) -> str | None:
    """'Booked 03 Dec 2026 (Clinic visit)' / 'Not booked: <reason>' / None."""
    if b is None:
        return None
    if b.booked_date:
        return f"Booked {fd.fmt(b.booked_date)}" + (f" ({b.mode})" if b.mode else "")
    if b.not_booked_reason:
        why = b.not_booked_other if b.not_booked_reason == "Other" and b.not_booked_other else b.not_booked_reason
        return f"Not booked: {why}"
    return None


def parse_weekdays(text: str | None) -> list[int]:
    """'Wed,Fri' -> [2, 4]. Unknown names are ignored."""
    out = []
    for part in (text or "").replace(";", ",").split(","):
        name = part.strip()[:3].title()
        if name in WEEKDAYS and WEEKDAYS.index(name) not in out:
            out.append(WEEKDAYS.index(name))
    return sorted(out)


def clinic_days(earliest: date | None, latest: date | None, weekdays: list[int]) -> list[date]:
    """The site's clinic days from earliest to latest (inclusive)."""
    if not (earliest and latest and weekdays):
        return []
    return [earliest + timedelta(days=i) for i in range((latest - earliest).days + 1)
            if (earliest + timedelta(days=i)).weekday() in weekdays]


def _done(form_i, wk) -> bool:
    reason = (getattr(form_i, f"ltfu{wk}_reason", None) or "").strip()
    return fd._answered(getattr(form_i, f"encounter{wk}_method", None)) or (bool(reason) and reason != fd.WITHDRAWN)


def checkpoints(baby: dict, left_on: date | None, today: date, booked: dict,
                weekdays: list[int] | None = None) -> list[dict]:
    """The calendar rows for one baby (followup_due.babies() dict). weekdays:
    the site's clinic days (parse_weekdays); each bookable row then lists the
    clinic days inside its range ("clinic_days") as suggestions."""
    eid, so = baby["enrollment_id"], baby["form_i"]
    open_wks = {r["checkpoint"]: r for r in fd.pending(baby["dob"], baby["ga_days"], so, baby["died"],
                                                         baby["death_date"], today)}
    out = []
    for wk in fd.CHECKPOINTS:
        due = fd.checkpoint_date(baby["dob"], baby["ga_days"], wk)
        if due is None:
            break
        frm, to = due - timedelta(days=fd.WINDOW_DAYS), due + timedelta(days=fd.WINDOW_DAYS)
        b = booked.get((eid, wk))
        row = {"checkpoint": wk, "due": due, "window_from": frm, "window_to": to,
               "earliest": None, "latest": None,
               "booked_date": b.booked_date if b else None, "mode": b.mode if b else None,
               "not_booked_reason": b.not_booked_reason if b else None,
               "not_booked_other": b.not_booked_other if b else None, "problem": None,
               "clinic_days": [], "not_clinic_day": False}
        if _done(so, wk):
            row["state"] = "done"
        elif wk not in open_wks:
            row["state"] = "ended"
        elif left_on is None:
            row["state"] = "no_discharge_date"
        elif to <= left_on:
            row["state"] = "in_nicu"
        else:
            row["state"] = "bookable"
            row["earliest"], row["latest"] = max(frm, left_on), to
            row["clinic_days"] = clinic_days(row["earliest"], row["latest"], weekdays or [])
            # a clinic visit booked on a day the clinic does not run: a hint, not refused
            row["not_clinic_day"] = bool(weekdays and b and b.booked_date and b.mode == "Clinic visit"
                                         and b.booked_date.weekday() not in weekdays)
            if b and b.booked_date and not (row["earliest"] <= b.booked_date <= row["latest"]):
                row["problem"] = (f"booked {fd.fmt(b.booked_date)} is outside {fd.fmt(row['earliest'])} – "
                                  f"{fd.fmt(row['latest'])}: book again")
            elif not (b and (b.booked_date or b.not_booked_reason)):
                row["problem"] = "not booked"
        out.append(row)
    return out


def is_complete(rows: list[dict]) -> bool:
    return all(r["problem"] is None for r in rows if r["state"] == "bookable")


def _left_on(baby: dict) -> date | None:
    nm = baby["form_h"]
    return nm.discharge_date if nm is not None and nm.outcome in ALIVE_OUTCOMES else None


def calendar(db, enrollment_id: str, today: date) -> dict:
    """GET /followup-bookings/{eid}: the baby's calendar from the saved Form H."""
    kids = fd.babies(db, None, [enrollment_id])
    if not kids:
        return {"enrollment_id": enrollment_id, "applies": False,
                "why": "Only randomised babies have Form I follow-up.", "rows": []}
    baby = kids[0]
    nm = baby["form_h"]
    outcome = nm.outcome if nm is not None else None
    if outcome not in ALIVE_OUTCOMES:
        return {"enrollment_id": enrollment_id, "site": baby["site"], "applies": False, "outcome": outcome,
                "why": "The follow-up calendar opens once Form H is saved with the baby leaving alive.", "rows": []}
    from models import FollowupClinic
    clinic = db.get(FollowupClinic, baby["site"])
    weekdays = parse_weekdays(clinic.weekdays if clinic else None)
    rows = checkpoints(baby, _left_on(baby), today, bookings_by_key(db, [enrollment_id]), weekdays)
    return {"enrollment_id": enrollment_id, "site": baby["site"], "applies": True, "outcome": outcome,
            "left_on": _left_on(baby), "dob": baby["dob"], "rows": rows, "complete": is_complete(rows),
            "modes": list(MODES), "reasons": list(REASONS), "window_days": fd.WINDOW_DAYS,
            "clinic_weekdays": [WEEKDAYS[i] for i in weekdays]}


class BookingError(ValueError):
    pass


def save(db, enrollment_id: str, items: list[dict], username: str, today: date) -> dict:
    """PUT /followup-bookings/{eid}. Each item: checkpoint, booked_date (ISO
    or blank), mode, not_booked_reason, not_booked_other. A blank item
    clears that checkpoint. Refuses dates outside the allowed range."""
    from models import FollowupBooking
    cal = calendar(db, enrollment_id, today)
    if not cal["applies"]:
        raise BookingError(cal["why"])
    rows = {r["checkpoint"]: r for r in cal["rows"]}
    existing = bookings_by_key(db, [enrollment_id])
    for it in items:
        wk = int(it.get("checkpoint") or 0)
        r = rows.get(wk)
        if r is None or r["state"] != "bookable":
            if r is not None and not any((it.get(k) or "") for k in ("booked_date", "not_booked_reason")):
                continue   # nothing asked for a row that needs no booking
            raise BookingError(f"{wk} wk: nothing to book ({r['state'] if r else 'no such checkpoint'}).")
        when = (it.get("booked_date") or "").strip()[:10]
        mode = (it.get("mode") or "").strip() or None
        reason = (it.get("not_booked_reason") or "").strip() or None
        other = (it.get("not_booked_other") or "").strip() or None
        b = existing.get((enrollment_id, wk))
        if not when and not reason:
            if b is not None:
                db.delete(b)
            continue
        if when:
            try:
                d = date.fromisoformat(when)
            except ValueError:
                raise BookingError(f"{wk} wk: {when!r} is not a date.")
            if not (r["earliest"] <= d <= r["latest"]):
                raise BookingError(f"{wk} wk: book a date from {fd.fmt(r['earliest'])} to {fd.fmt(r['latest'])}.")
            if mode not in MODES:
                raise BookingError(f"{wk} wk: choose Clinic visit or Telephone.")
            reason = other = None
        else:
            d = mode = None
            if reason not in REASONS:
                raise BookingError(f"{wk} wk: choose a reason the date could not be booked.")
            if reason == "Other" and not other:
                raise BookingError(f"{wk} wk: type the reason (Other).")
            if reason != "Other":
                other = None
        if b is None:
            b = FollowupBooking(enrollment_id=enrollment_id, checkpoint=wk)
            db.add(b)
        b.booked_date, b.mode, b.not_booked_reason, b.not_booked_other = d, mode, reason, other
        b.booked_by = username
    db.commit()
    return calendar(db, enrollment_id, today)


# ------------------------------------------------------------------ all babies (checks, emails)
def all_calendars(db, sites, today: date) -> list[dict]:
    """[{site, enrollment_id, left_on, outcome, rows, baby}] for every randomised
    baby whose saved Form H says it left alive."""
    kids = [b for b in fd.babies(db, sites) if _left_on(b)]
    booked = bookings_by_key(db, [b["enrollment_id"] for b in kids])
    return [{"site": b["site"], "enrollment_id": b["enrollment_id"], "left_on": _left_on(b),
             "outcome": b["form_h"].outcome, "rows": checkpoints(b, _left_on(b), today, booked), "baby": b}
            for b in kids]


def _ist_now(now_utc: datetime) -> datetime:
    return now_utc + timedelta(hours=5, minutes=30)


def _signature(rows) -> str:
    key = [(r["checkpoint"], str(r["booked_date"] or ""), r["mode"] or "", r["not_booked_reason"] or "",
            r["not_booked_other"] or "") for r in rows if r["state"] == "bookable"]
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]


def _row_cells(r) -> str:
    td = '<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">'
    if r["booked_date"]:
        booked = f"<strong>{escape(fd.fmt(r['booked_date']))}</strong> ({escape(r['mode'] or '')})"
    else:
        why = r["not_booked_other"] if r["not_booked_reason"] == "Other" else r["not_booked_reason"]
        booked = f"Not booked: {escape(why or '')}"
    return (f"{td}{r['checkpoint']} wk PMA</td>{td}{escape(fd.fmt(r['due']))}</td>"
            f"{td}{escape(fd.fmt(r['window_from']))} – {escape(fd.fmt(r['window_to']))}</td>{td}{booked}</td>")


def _wrap(title: str, intro: str, table: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<h2 style="font-size:18px;color:#00132c;">{escape(title)}</h2>
<p style="font-size:13px;">{intro}</p>
{table}
<p style="font-size:11px;color:#64748b;">Form I records the visit or call. IDs only. Do not reply; this mailbox
is not read.</p>
</body></html>"""


def _th(*names) -> str:
    th = '<th style="text-align:left;padding:6px 8px;border-bottom:2px solid #e2e8f0;font-size:12px;color:#475569;">'
    return "<tr>" + "".join(f"{th}{n}</th>" for n in names) + "</tr>"


def notice_email(site_display: str, cal: dict) -> tuple[str, str]:
    eid = cal["enrollment_id"]
    rows = [r for r in cal["rows"] if r["state"] == "bookable"]
    nicu = [r for r in cal["rows"] if r["state"] == "in_nicu"]
    subject = f"PORTAL: follow-up booked — {site_display} — {eid}"
    left = f"{escape(cal['outcome'])} {escape(fd.fmt(cal['left_on']))}"
    intro = (f"Site: {escape(site_display)}. Baby <strong>{escape(eid)}</strong>: {left}. "
             f"Follow-up dates booked with the family (window: checkpoint date ± {fd.WINDOW_DAYS} days).")
    if nicu:
        intro += " Assessed in the NICU (record on Form I): " + ", ".join(f"{r['checkpoint']} wk" for r in nicu) + "."
    table = ('<table style="border-collapse:collapse;font-size:13px;">'
             + _th("Checkpoint", "Date", "Window", "Booked") + "".join(f"<tr>{_row_cells(r)}</tr>" for r in rows)
             + "</table>")
    return subject, _wrap("Follow-up booked at discharge", intro, table)


def list_email(kind: str, site_display: str, items: list[tuple[dict, dict]]) -> tuple[str, str]:
    """kind 'reminder' (in REMIND_DAYS) or 'missed' (booked date passed)."""
    n = len(items)
    babies = f"{n} bab{'y' if n == 1 else 'ies'}"
    if kind == "reminder":
        subject = f"PORTAL: follow-up visit in {REMIND_DAYS} days — {site_display} — {babies}"
        title, intro = "Booked follow-up coming up", (
            f"Site: {escape(site_display)}. These babies have a booked follow-up within {REMIND_DAYS} days. "
            "Please remind the family the day before.")
    else:
        subject = f"PORTAL: booked follow-up missed — {site_display} — {babies}"
        title, intro = "Booked follow-up date passed, nothing on Form I", (
            f"Site: {escape(site_display)}. Please contact the family, or record the visit or call on Form I "
            "if it took place. The window may still be open.")
    td = '<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;">'
    rows = "".join(f"<tr>{td}<strong>{escape(cal['enrollment_id'])}</strong></td>{_row_cells(r)}"
                   f'{td}<a href="{fd.PORTAL_URL}{escape(cal["enrollment_id"])}">Form I</a></td></tr>'
                   for cal, r in items)
    table = ('<table style="border-collapse:collapse;font-size:13px;">'
             + _th("Baby", "Checkpoint", "Date", "Window", "Booked", "") + rows + "</table>")
    return subject, _wrap(title, intro, table)


def send_emails(db, now: datetime | None = None) -> dict:
    """Booked notices (any hour), reminders and missed alerts (08-20 IST).
    Each once: audit rows. Caller commits."""
    if not (os.environ.get("SES_SENDER_EMAIL") or "").strip():
        return {}
    from audit_service import record_audit
    from daily_query_email import _site_display, recipients
    from email_service import send_email
    from models import AuditLog
    from site_summary import REPORT_SITES

    now = now or datetime.utcnow()
    ist = _ist_now(now)
    today = ist.date()
    cals = all_calendars(db, REPORT_SITES, today)
    if not cals:
        return {}
    eids = [c["enrollment_id"] for c in cals]
    sent_before = defaultdict(set)
    for a in db.query(AuditLog).filter(AuditLog.action == "EMAIL", AuditLog.enrollment_id.in_(eids),
                                       AuditLog.table_name.in_([NOTICE_TABLE, REMIND_TABLE, MISSED_TABLE])):
        v = a.new_values or {}
        sent_before[a.table_name].add((a.enrollment_id, v.get("checkpoint"), v.get("key")))
    plan = recipients(db)
    counts = defaultdict(int)

    def mail(site, subject, html, table, keys):
        to = plan.get(site, [])
        if not to:
            logger.warning("follow-up booking email: no Site PI / Scientist email for %s", site)
            return
        if send_email(to, subject, html):
            for eid, wk, key in keys:
                record_audit(db, user_id=None, username="system", action="EMAIL", table_name=table,
                             enrollment_id=eid, new_values={"checkpoint": wk, "key": key, "recipients": len(to)})
            counts[table] += 1

    # 1. booked notice: calendar complete, something still to come, signature not yet mailed
    for c in cals:
        bookable = [r for r in c["rows"] if r["state"] == "bookable"]
        if not bookable or not is_complete(c["rows"]):
            continue
        sig = _signature(c["rows"])
        if (c["enrollment_id"], None, sig) in sent_before[NOTICE_TABLE]:
            continue
        subject, html = notice_email(_site_display(c["site"]), c)
        mail(c["site"], subject, html, NOTICE_TABLE, [(c["enrollment_id"], None, sig)])

    if not (fd.EMAIL_HOURS_IST[0] <= ist.hour < fd.EMAIL_HOURS_IST[1]):
        return dict(counts)
    remind, missed = defaultdict(list), defaultdict(list)
    for c in cals:
        for r in c["rows"]:
            d = r["booked_date"]
            if r["state"] != "bookable" or not d or r["problem"]:
                continue
            key = d.isoformat()
            if 0 <= (d - today).days <= REMIND_DAYS and (c["enrollment_id"], r["checkpoint"], key) \
                    not in sent_before[REMIND_TABLE]:
                remind[c["site"]].append((c, r))
            elif today > d and (c["enrollment_id"], r["checkpoint"], key) not in sent_before[MISSED_TABLE]:
                missed[c["site"]].append((c, r))
    for kind, table, groups in (("reminder", REMIND_TABLE, remind), ("missed", MISSED_TABLE, missed)):
        for site, items in groups.items():
            subject, html = list_email(kind, _site_display(site), items)
            mail(site, subject, html, table,
                 [(c["enrollment_id"], r["checkpoint"], r["booked_date"].isoformat()) for c, r in items])
    return dict(counts)


# ------------------------------------------------------------------ parent slip
def slip_pdf(cal: dict, clinic, baby_name: str | None, site_display: str) -> bytes:
    """One A4 page for the family: booked dates, where to come, whom to call."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    navy = colors.HexColor("#00132c")
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=12, leading=16)
    bold = ParagraphStyle("bb", parent=body, fontName="Helvetica-Bold")
    head = ParagraphStyle("h", parent=bold, textColor=colors.white)
    title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=navy)
    small = ParagraphStyle("s", fontName="Helvetica", fontSize=10, leading=13, textColor=colors.HexColor("#475569"))
    blank = "______________________________"

    def line(label, value):
        return Paragraph(f"<b>{escape(label)}:</b> {escape(value) if value else blank}", body)

    story = [Paragraph("PORTAL Trial: follow-up appointments", title),
             Paragraph(escape(site_display), small), Spacer(1, 4 * mm),
             line("Baby", baby_name), line("Study number", cal["enrollment_id"]),
             line("Date of birth", fd.fmt(cal["dob"]) if cal.get("dob") else None),
             line("Went home / referred on", fd.fmt(cal["left_on"]) if cal.get("left_on") else None),
             Spacer(1, 5 * mm),
             Paragraph("Your baby's check-ups are important for the study. Please come (or take the call) on "
                       "these dates.", body), Spacer(1, 3 * mm)]
    data = [[Paragraph(x, head) for x in ("Check-up", "Date", "How", "If you cannot come that day")]]
    for r in cal["rows"]:
        if r["state"] != "bookable":
            continue
        if r["booked_date"]:
            when, how = fd.fmt(r["booked_date"]), ("Come to the clinic" if r["mode"] == "Clinic visit"
                                                    else "We will telephone you")
        else:
            when, how = "We will call you to fix the date", ""
        data.append([Paragraph(f"{r['checkpoint']} weeks", bold), Paragraph(escape(when), bold),
                     Paragraph(escape(how), body),
                     Paragraph(escape(f"any day {fd.fmt(r['earliest'])} to {fd.fmt(r['latest'])}"), body)])
    if len(data) == 1:
        data.append([Paragraph("No check-up left to book.", body), "", "", ""])
    t = Table(data, colWidths=[28 * mm, 45 * mm, 45 * mm, 62 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy),
                           ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [t, Spacer(1, 6 * mm),
              line("Where", clinic.place if clinic else None),
              line("Clinic days and times", clinic.days_times if clinic else None),
              line("Phone (to change a date or if the baby is unwell)", clinic.phone if clinic else None),
              Spacer(1, 6 * mm),
              Paragraph("Please bring this slip and the discharge summary to every visit.", small)]
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                      bottomMargin=15 * mm, title="Follow-up appointments").build(story)
    return buf.getvalue()
