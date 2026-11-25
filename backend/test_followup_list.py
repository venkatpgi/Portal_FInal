"""Follow-up list (followup_list.py, PI 2026-11-25)."""
from datetime import date
from types import SimpleNamespace as NS

import followup_list as fl
import followup_due as fd

DOB = date(2026, 10, 20)
GA = 28 * 7          # 36 wk 15 Dec 2026, 40 wk 12 Jan 2027, 44 wk 9 Feb 2027


def fi(**kw):
    base = {}
    for wk in fd.CHECKPOINTS:
        base.update({f"encounter{wk}_method": None, f"death{wk}": None, f"ltfu{wk}_reason": None})
    base.update(kw)
    return NS(**base)


def kid(end=None, died=False, so=None):
    return {"site": "PGIMER", "enrollment_id": "01-B-001", "dob": DOB, "ga_days": GA, "form_h": None,
            "form_i": so or fi(), "end": end, "died": died, "death_date": None, "home": bool(end and not died),
            "where": "Discharged" if end else "In NICU"}


def test_statuses():
    today = date(2026, 12, 14)
    booked = {("01-B-001", 40): NS(booked_date=date(2027, 1, 13), mode="Clinic visit", not_booked_reason=None,
                                   not_booked_other=None)}
    rows = fl.rows_for(kid(end={"date": date(2026, 11, 30), "died": False}, so=fi(encounter44_method=None)),
                       today, booked, NS(screenings=[{"date": "2026-11-15", "method": "Indirect"}]))
    st = {r["assessment"]: (r["status"], r["text"]) for r in rows}
    assert st["Form I 36 wk PMA"][0] == "window" and "window open" in st["Form I 36 wk PMA"][1]
    assert st["Form I 40 wk PMA"][0] == "booked" and "Booked 13 Jan 2027 (Clinic visit)" in st["Form I 40 wk PMA"][1]
    assert st["Form I 44 wk PMA"][0] == "upcoming"
    assert "ROP screen (outpatient)" not in st                         # Form G has a screen
    done = fl.rows_for(kid(so=fi(encounter36_method="Direct")), today, {}, None)
    assert done[0]["status"] == "done"
    admitted = fl.rows_for(kid(), today, {}, None)
    assert admitted[0]["status"] == "in_nicu" and "assess on the ward" in admitted[0]["text"]
    late = fl.rows_for(kid(), date(2026, 12, 20), {}, None)
    assert late[0]["status"] == "overdue"                              # overdue even while admitted


def test_outpatient_rop_screen():
    left = kid(end={"date": date(2026, 11, 7), "died": False})          # DOL 19
    rows = fl.rows_for(left, date(2026, 11, 25), {}, None)
    rop = [r for r in rows if r["kind"] == "rop"][0]
    assert rop["due"] == date(2026, 11, 18) and rop["status"] == "overdue"     # DOL 30
    assert [r for r in fl.rows_for(left, date(2026, 11, 25), {}, NS(screenings=[{"date": "2026-11-20",
                                                                                 "signature": "x"}]))
            if r["kind"] == "rop"] == []
    stayed = kid(end={"date": date(2026, 12, 1), "died": False})        # DOL 43: screened in the NICU (M4)
    assert [r for r in fl.rows_for(stayed, date(2026, 12, 2), {}, None) if r["kind"] == "rop"] == []
    died = kid(end={"date": date(2026, 11, 7), "died": True}, )
    died["died"] = True
    assert [r for r in fl.rows_for(died, date(2026, 11, 25), {}, None) if r["kind"] == "rop"] == []
