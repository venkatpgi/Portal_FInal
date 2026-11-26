"""Follow-up list: every outcome assessment still to come or done, per baby
(PI 2026-11-25). For all site staff (left panel "Follow-up"), IDs plus the
baby's name only for users who may see that site's PII.

Rows (randomised babies born since the trial start, followup_due.babies):
  Form I 36 / 40 / 44 wk PMA   checkpoint date = DOB + weeks - GA, window
                               +/- 2 days (followup_due.py); booked date from
                               the Form H calendar (followup_booking.py)
  ROP screen (outpatient)      a baby who left alive by DOL 30 with no Form G
                               visit: due by DOL 30 (ROP_FIRST_SCREEN_DOL),
                               until Form G records a screen (here or
                               elsewhere). Replaces the repeating M4 item.

Status keys: done, booked, ended (death / consent withdrawn), in_nicu (the
baby is still admitted: assess on the ward), upcoming, window, overdue.
"""
from __future__ import annotations

from datetime import date, timedelta

import followup_booking as fbk
import followup_due as fd

ROP_FIRST_SCREEN_DOL = 30
SOON_DAYS = 14


def _rop_screened(rop) -> bool:
    from form_completion import ROP_VISIT_DETAIL_FIELDS, answered
    return any(answered((s or {}).get("date"))
               and (answered((s or {}).get("signature"))
                    or any(answered((s or {}).get(f)) for f in ROP_VISIT_DETAIL_FIELDS))
               for s in ((rop.screenings if rop else None) or []) if isinstance(s, dict))


def _stage(due: date, frm: date, to: date, today: date) -> str:
    return "overdue" if today > to else "window" if today >= frm else "upcoming"


def _when(stage: str, due: date, to: date, today: date) -> str:
    n = (due - today).days
    if stage == "overdue":
        return f"window closed {fd.fmt(to)}"
    if stage == "window":
        return "today" if n == 0 else (f"in {n} day{'s' if n != 1 else ''}, window open" if n > 0
                                       else f"{-n} day{'s' if n != -1 else ''} ago, window open")
    return f"in {n} day{'s' if n != 1 else ''}"


def rows_for(baby: dict, today: date, booked: dict, rop) -> list[dict]:
    eid, so = baby["enrollment_id"], baby["form_i"]
    admitted = baby["end"] is None
    open_wks = {r["checkpoint"]: r for r in fd.pending(baby["dob"], baby["ga_days"], so, baby["died"],
                                                         baby["death_date"], today)}
    out = []
    for wk in fd.CHECKPOINTS:
        due = fd.checkpoint_date(baby["dob"], baby["ga_days"], wk)
        if due is None:
            break
        frm, to = due - timedelta(days=fd.WINDOW_DAYS), due + timedelta(days=fd.WINDOW_DAYS)
        row = {"assessment": f"Form I {wk} wk PMA", "kind": "form_i", "checkpoint": wk, "due": due,
               "window_from": frm, "window_to": to, "booking": None, "booked": None}
        b = booked.get((eid, wk))
        if fbk._done(so, wk):
            row.update(status="done", text="Done on Form I")
        elif wk not in open_wks:
            row.update(status="ended", text="Follow-up ended (death or consent withdrawn)")
        else:
            st = _stage(due, frm, to, today)
            row["booking"] = fbk.booking_text(b)
            if st != "overdue" and b is not None and b.booked_date:
                row["booked"] = b.booked_date
                row.update(status="booked", text=f"{fbk.booking_text(b)}; {_when(st, due, to, today)}")
            elif admitted and st != "overdue":
                row.update(status="in_nicu", text=f"Baby admitted: assess on the ward, {_when(st, due, to, today)}")
            else:
                row.update(status=st, text=_when(st, due, to, today)
                           + (f"; {fbk.booking_text(b)}" if b is not None and fbk.booking_text(b) else ""))
        out.append(row)
    # outpatient ROP screen: left alive by DOL 30 with no Form G visit
    end = baby["end"]
    if end and not baby["died"] and baby["dob"] and not _rop_screened(rop):
        end_dol = (end["date"] - baby["dob"]).days + 1
        if end_dol <= ROP_FIRST_SCREEN_DOL:
            due = baby["dob"] + timedelta(days=ROP_FIRST_SCREEN_DOL - 1)
            st = "overdue" if today > due else "window" if (due - today).days <= 7 else "upcoming"
            n = (due - today).days
            out.append({"assessment": "ROP screen (outpatient)", "kind": "rop", "checkpoint": None, "due": due,
                        "window_from": None, "window_to": due, "booking": None, "status": st,
                        "text": (f"by DOL {ROP_FIRST_SCREEN_DOL}, {-n} days late: record on Form G when done"
                                 if st == "overdue" else f"by DOL {ROP_FIRST_SCREEN_DOL}, in {n} days")})
    return out


def build(db, sites, today: date) -> list[dict]:
    from models import ROPScreening
    kids = fd.babies(db, sites)
    eids = [b["enrollment_id"] for b in kids]
    booked = fbk.bookings_by_key(db, eids)
    rops = {}
    if eids:
        for r in db.query(ROPScreening).filter(ROPScreening.enrollment_id.in_(eids)).order_by(ROPScreening.id):
            rops[r.enrollment_id] = r        # newest wins
    out = []
    for b in kids:
        where = ("Admitted" if b["end"] is None else b["where"])
        for r in rows_for(b, today, booked, rops.get(b["enrollment_id"])):
            out.append({"site": b["site"], "enrollment_id": b["enrollment_id"], "screening_id": None,
                        "where": where, **r,
                        "days_to_due": (r["due"] - today).days})
    order = {"overdue": 0, "window": 1, "booked": 2, "upcoming": 2, "in_nicu": 3, "done": 4, "ended": 5}
    return sorted(out, key=lambda r: (order.get(r["status"], 9), r["due"], r["enrollment_id"]))
