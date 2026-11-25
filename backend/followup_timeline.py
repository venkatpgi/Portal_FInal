"""Follow-up list, baby by baby (PI 2026-11-26: "should be shown patient wise,
outcomes / events to be documented at different time points based on the
gestation and PMA, with dates").

For every randomised baby: its time points worked out from date of birth,
gestation at birth and PMA, what has to be documented at each, the date or
window, and whether it is done.

  Day 3 (72 h)     DOL 3              Form I: resp support 0.5-72 h, early-onset sepsis
  Day 7 ± 1        DOL 6-8            Form F: cranial USG 1 · Form I: death ≤ 7 days
  Day 28 ± 2       DOL 26-30          Form F: cranial USG 2 · Form I: death ≤ 28 days
  DOL 30           by DOL 30          Form G: first ROP screen (RBSK / NPCB)
  36 wk PMA ± 2 d  checkpoint         Form I visit: death, BPD, NEC, IVH / cPVL, ROP
  Discharge        when it happens    Form H; Form I overall; final cranial USG if before
                                      the 40 wk window; follow-up booked (Form H calendar)
  40 wk PMA (TEA)  ± 2 d (scan ± 7 d) Form I visit: NEC, IVH / cPVL, ROP · Form K MRI
                                      (subset) · final cranial USG if still admitted
  44 wk PMA ± 2 d  checkpoint         Form I visit: NEC, IVH / cPVL, ROP, death after discharge
Rows are ordered by date; the discharge row sits where it happens (or before
the next checkpoint while the baby is admitted). After a death the later
items are not applicable.

Item status: done, booked, due (later), due_now (window open), overdue,
at_discharge, na. Rules reuse followup_due / followup_list / followup_booking
/ site_summary cranial windows. IDs only here; the router adds names.
"""
from __future__ import annotations

from datetime import date, timedelta

import followup_booking as fbk
import followup_due as fd
import followup_list as fl

GRACE = 2
SOON_DAYS = 14
ROP_DOL = 30


def fmt(d: date | None) -> str:
    return d.strftime("%d %b %y") if d else ""


def _dol_date(dob: date, dol: int) -> date:
    return dob + timedelta(days=dol - 1)


def _answered(v) -> bool:
    return v is not None and not (isinstance(v, str) and v.strip() == "")


def item(form: str, text: str, status: str, status_text: str, route: str, when: date | None = None) -> dict:
    return {"form": form, "text": text, "status": status, "status_text": status_text, "route": route,
            "date": when.isoformat() if when else None}


def timed(done: bool, start: date | None, end: date | None, today: date, *, done_text="Done",
          missing_text="Overdue") -> tuple[str, str]:
    """Status of a dated item from its window."""
    if done:
        return "done", done_text
    if start is None:
        return "due", "date unknown"
    if today < start:
        n = (start - today).days
        return "due", f"due in {n} day{'s' if n != 1 else ''}"
    if end is not None and today > end + timedelta(days=GRACE):
        return "overdue", missing_text
    return "due_now", "due now" + (f" (to {fmt(end)})" if end and end != start else "")


def scan_done(scan_dols: list[int], first: int, last: int) -> bool:
    """Same tolerance as site_summary M2: DOL first-1 ... last+2."""
    return any(first - 1 <= d <= last + 2 for d in scan_dols)


def timeline(baby: dict, today: date, *, scan_dates: list, rop, mri, booked: dict, calendar_complete: bool | None,
             form_h_done: bool, location: str | None) -> dict:
    """One baby's card: header facts + rows [{key, label, date, window, items}]."""
    eid, dob, ga, so = baby["enrollment_id"], baby["dob"], baby["ga_days"], baby["form_i"]
    end = baby["end"]["date"] if baby.get("end") else None
    died, death_date = baby["died"], baby.get("death_date") or (end if baby.get("died") else None)
    g = (lambda k: getattr(so, k, None)) if so is not None else (lambda k: None)
    scan_dols = sorted((d - dob).days + 1 for d in scan_dates if d and dob)
    fi, ff, fg, fh, fk = (f"/form-i/{eid}", f"/form-f/{eid}", f"/form-g/{eid}", f"/form-h/{eid}", f"/form-k/{eid}")
    rows = []

    def add(key, label, when, window, items):
        rows.append({"key": key, "label": label, "date": when.isoformat() if when else None,
                     "date_text": fmt(when), "window": window, "items": items})

    def after_death(when: date | None) -> bool:
        return bool(died and death_date and when and when > death_date)

    def na(form, text, route):
        return item(form, text, "na", f"not applicable (died {fmt(death_date)})", route)

    if dob is None:
        return {"enrollment_id": eid, "rows": [], "next": None, "counts": {}}

    # Day 3 (72 h)
    d3 = _dol_date(dob, 3)
    done = _answered(g("resp_support_72h")) and _answered(g("sepsis_eos"))
    st, tx = timed(done, d3, d3, today, missing_text="Not entered")
    add("d3", "Day 3 (72 h)", d3, "", [
        item("Form I", "Respiratory support 0.5–72 h, early-onset sepsis", st, tx, fi, d3)
        if not after_death(d3) else na("Form I", "Respiratory support 0.5–72 h, early-onset sepsis", fi)])

    # Day 7 ± 1 and Day 28 ± 2
    for key, label, first, last, scan_no, mort, mort_text in (
            ("d7", "Day 7 ± 1", 6, 8, 1, "mortality_7_days", "Death ≤ 7 days"),
            ("d28", "Day 28 ± 2", 26, 30, 2, "mortality_28_days", "Death ≤ 28 days")):
        a, b, mid = _dol_date(dob, first), _dol_date(dob, last), _dol_date(dob, (first + last) // 2)
        items = []
        stayed = not (end and end < a) or scan_done(scan_dols, first, last)
        if after_death(a):
            items.append(na("Form F", f"Cranial USG {scan_no}", ff))
        elif not stayed:
            items.append(item("Form F", f"Cranial USG {scan_no}", "na", f"left before day {first}", ff))
        else:
            st, tx = timed(scan_done(scan_dols, first, last), a, b, today, missing_text="Scan missing")
            items.append(item("Form F", f"Cranial USG {scan_no}", st, tx, ff, a))
        # the death questions stay asked after a death (the answer is Yes)
        st, tx = timed(_answered(g(mort)), b, b, today, missing_text="Not entered")
        items.append(item("Form I", mort_text, st, tx, fi, b))
        add(key, label, mid, f"{fmt(a)} – {fmt(b)}", items)

    # DOL 30: first ROP screen
    r30 = _dol_date(dob, ROP_DOL)
    if after_death(r30):
        rop_item = na("Form G", "First ROP screen", fg)
    else:
        st, tx = timed(fl._rop_screened(rop), r30 - timedelta(days=ROP_DOL - 1), r30, today,
                       missing_text="No screen yet")
        if st == "due_now":
            tx = f"by {fmt(r30)}"
        rop_item = item("Form G", "First ROP screen", st, tx, fg, r30)
    add("rop", f"DOL {ROP_DOL}", r30, f"by {fmt(r30)}", [rop_item])

    # Form I checkpoints
    visit_rows = {r["checkpoint"]: r for r in fl.rows_for(baby, today, booked, rop) if r["kind"] == "form_i"}
    what = {36: "Form I visit: death, BPD, NEC, IVH / cPVL, ROP",
            40: "Form I visit: NEC, IVH / cPVL, ROP",
            44: "Form I visit: NEC, IVH / cPVL, ROP, death after discharge"}
    cps = {}
    for wk in (36, 40, 44):
        due = fd.checkpoint_date(dob, ga, wk)
        if due is None:
            continue
        cps[wk] = due
        r = visit_rows.get(wk)
        if after_death(due - timedelta(days=fd.WINDOW_DAYS)) or (r and r["status"] == "ended"):
            it = na("Form I", what[wk], fi)
        elif r is None:
            it = item("Form I", what[wk], "due", "date unknown", fi, due)
        else:
            s = r["status"]
            m = {"done": ("done", "Done"), "booked": ("booked", f"Booked {fmt(r.get('booked'))}"),
                 "overdue": ("overdue", f"Overdue (window closed {fmt(r['window_to'])})"),
                 "window": ("due_now", f"due now (to {fmt(r['window_to'])})"),
                 "in_nicu": ("due" if today < r["window_from"] else "due_now",
                             ("assess on the ward, " + fl._when("upcoming", due, r["window_to"], today))
                             if today < r["window_from"] else f"assess on the ward now (to {fmt(r['window_to'])})"),
                 "upcoming": ("due", fl._when("upcoming", due, r["window_to"], today))}
            st, tx = m.get(s, ("due", r["text"]))
            it = item("Form I", what[wk], st, tx, fi, due)
        items = [it]
        if wk == 40:
            # MRI at term (Form K, subset) and the final cranial USG if still admitted
            if after_death(due):
                items.append(na("Form K", "MRI at TEA (subset)", fk))
            elif mri is None:
                items.append(item("Form K", "MRI at TEA (subset): select or not", *timed(False, due, due + timedelta(days=14), today, missing_text="Form K not filled"), fk, due))
            elif mri.selected_for_mri is False:
                items.append(item("Form K", "MRI at TEA", "na", "not in the MRI subset", fk))
            else:
                items.append(item("Form K", "MRI at TEA", *timed(bool(mri.overall_mri), due, due + timedelta(days=14), today, missing_text="Result not entered"), fk, due))
            tea_first = 40 * 7 - ga + 1 - 7 if ga is not None else None
            if ga is not None and not (end and end < _dol_date(dob, tea_first)) and not after_death(due):
                a, b = _dol_date(dob, tea_first), _dol_date(dob, tea_first + 14)
                items.append(item("Form F", "Final cranial USG (40 ± 1 wk)",
                                  *timed(scan_done(scan_dols, tea_first, tea_first + 14), a, b, today,
                                         missing_text="Scan missing"), ff, a))
        label = {36: "36 wk PMA", 40: "40 wk PMA (TEA)", 44: "44 wk PMA"}[wk]
        add(f"cp{wk}", label, due, f"{fmt(due - timedelta(days=2))} – {fmt(due + timedelta(days=2))}", items)

    # Discharge (or death) row
    if died and death_date:
        add("end", "Death", death_date, "", [
            item("Form H", "Form H: outcome Died, date and time; Form Y / SAE", "done" if form_h_done else "overdue",
                 "Done" if form_h_done else "Form H not complete", fh, death_date)])
    else:
        items = [item("Form H", "Form H complete (hospital course, outcome)",
                      ("done" if form_h_done else ("at_discharge" if end is None else "overdue")),
                      ("Done" if form_h_done else ("at discharge" if end is None else "Form H not complete")), fh, end),
                 item("Form I", "Form I overall: support days, sepsis, death in hospital",
                      ("done" if _answered(g("mortality_in_hospital")) and _answered(g("sepsis_overall"))
                       else ("at_discharge" if end is None else "overdue")),
                      ("Done" if _answered(g("mortality_in_hospital")) and _answered(g("sepsis_overall"))
                       else ("at discharge" if end is None else "Not entered")), fi, end)]
        if ga is not None:
            tea_first = 40 * 7 - ga + 1 - 7
            if end is not None and end < _dol_date(dob, tea_first):
                ed = (end - dob).days + 1
                items.append(item("Form F", "Final cranial USG (before discharge)",
                                  *timed(scan_done(scan_dols, ed - 2, ed), end - timedelta(days=2), end, today,
                                         missing_text="Scan missing"), ff, end))
            elif end is None:
                items.append(item("Form F", "Final cranial USG if leaving before 40 wk", "at_discharge",
                                  "at discharge", ff))
        if calendar_complete is not None:
            items.append(item("Form H", "Follow-up dates booked (Form H calendar)",
                              "done" if calendar_complete else ("at_discharge" if end is None else "overdue"),
                              "Done" if calendar_complete else ("at discharge" if end is None else "Not booked"),
                              fh, end))
        add("end", "Discharge", end, "" if end else "when it happens", items)

    # order by date; the discharge row of an admitted baby goes before the next checkpoint not yet reached
    def sort_key(r):
        if r["date"]:
            return (date.fromisoformat(r["date"]), 0 if r["key"] != "end" else 1)
        nxt = min((d for d in cps.values() if d >= today), default=today + timedelta(days=3650))
        return (nxt - timedelta(days=1), 1)
    rows.sort(key=sort_key)

    open_items = [(r, it) for r in rows for it in r["items"] if it["status"] in ("overdue", "due_now", "due", "booked")]
    overdue = sum(1 for _, it in open_items if it["status"] == "overdue")
    soon = [(r, it) for r, it in open_items if it["status"] != "overdue" and it["date"]
            and date.fromisoformat(it["date"]) <= today + timedelta(days=SOON_DAYS)]
    upcoming = sorted(((date.fromisoformat(it["date"]), r, it) for r, it in open_items
                       if it["status"] != "overdue" and it["date"]), key=lambda x: x[0])
    nxt = None
    if upcoming:
        d, r, it = upcoming[0]
        n = (d - today).days
        nxt = {"label": r["label"], "date": d.isoformat(),
               "text": f"{r['label']} on {fmt(d)}" + ("" if n < 0 else (" (today)" if n == 0 else f" (in {n} day{'s' if n != 1 else ''})"))}
    dol = (today - dob).days + 1
    pma = ga + dol - 1 if ga is not None else None
    return {
        "site": baby["site"], "enrollment_id": eid, "dob": dob.isoformat(), "dob_text": fmt(dob),
        "ga": f"{ga // 7}+{ga % 7}" if ga is not None else "",
        "now": (f"Died {fmt(death_date)}" if died else
                f"DOL {dol} · PMA {pma // 7}+{pma % 7}" if pma is not None else f"DOL {dol}"),
        "status": ("Died" if died else (f"Admitted ({location})" if end is None and location else
                                        "Admitted" if end is None else f"Discharged {fmt(end)}")),
        "rows": rows, "next": nxt,
        "counts": {"overdue": overdue, "soon": len(soon)},
        "sort": (0 if overdue else 1, upcoming[0][0].isoformat() if upcoming else "9999-12-31", eid),
    }


# ------------------------------------------------------------------ data
def build(db, sites, today: date) -> list[dict]:
    """Every randomised baby's card for these sites, most urgent first."""
    from collections import defaultdict

    from form_completion import form_h_complete
    from infection_windows import _compute_infection_windows
    from models import (CranialUSGRecord, InfectGIHemaDayLog, MetabRenalVascEyeDayLog, MRIBrainAssessment,
                        NICUAdmission, ROPScreening)
    from shift_report import area_of, NOT_RECORDED

    kids = fd.babies(db, sites)
    eids = [b["enrollment_id"] for b in kids]
    if not eids:
        return []

    def latest(model):
        out = {}
        for r in db.query(model).filter(model.enrollment_id.in_(eids)).order_by(model.id):
            out[r.enrollment_id] = r
        return out

    usg, rop, mri, nicu = latest(CranialUSGRecord), latest(ROPScreening), latest(MRIBrainAssessment), latest(NICUAdmission)
    inf, metab = defaultdict(list), defaultdict(list)
    for r in db.query(InfectGIHemaDayLog).filter(InfectGIHemaDayLog.enrollment_id.in_(eids)).order_by(
            InfectGIHemaDayLog.nicu_day):
        inf[r.enrollment_id].append(r)
    for r in db.query(MetabRenalVascEyeDayLog).filter(MetabRenalVascEyeDayLog.enrollment_id.in_(eids)):
        metab[r.enrollment_id].append(r)
    booked = fbk.bookings_by_key(db, eids)
    cal = {c["enrollment_id"]: c for c in fbk.all_calendars(db, sites, today)}

    def scans(eid):
        out = []
        for e in ((usg[eid].scan_entries if eid in usg else None) or []):
            v = (e or {}).get("scanDate")
            try:
                out.append(date.fromisoformat(str(v)[:10])) if v else None
            except ValueError:
                pass
        return out

    cards = []
    for b in kids:
        eid = b["enrollment_id"]
        sigs = [w["signature"] for w in _compute_infection_windows(inf[eid], nicu.get(eid))] if inf[eid] else []
        area, _ = area_of(metab[eid])
        c = cal.get(eid)
        cards.append(timeline(
            b, today, scan_dates=scans(eid), rop=rop.get(eid), mri=mri.get(eid), booked=booked,
            calendar_complete=(fbk.is_complete(c["rows"]) if c else (None if b["died"] else False)),
            form_h_done=form_h_complete(b["form_h"], sigs),
            location=None if area == NOT_RECORDED else area))
    return sorted(cards, key=lambda x: x["sort"])
