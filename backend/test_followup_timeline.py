"""Baby-by-baby follow-up (followup_timeline.py, PI 2026-11-26)."""
from datetime import date, timedelta
from types import SimpleNamespace as NS

import followup_due as fd
import followup_timeline as ft

DOB = date(2026, 10, 23)          # GA 29+6 -> 36 wk on 2026-12-05
GA = 29 * 7 + 6


def fi(**kw):
    base = {"resp_support_72h": None, "sepsis_eos": None, "mortality_7_days": None, "mortality_28_days": None,
            "mortality_in_hospital": None, "sepsis_overall": None}
    for wk in fd.CHECKPOINTS:
        base.update({f"encounter{wk}_method": None, f"death{wk}": None, f"ltfu{wk}_reason": None})
    base.update(kw)
    return NS(**base)


def baby(**kw):
    b = {"site": "PGIMER", "enrollment_id": "01-B-003", "dob": DOB, "ga_days": GA, "form_h": None,
         "form_i": fi(), "end": None, "died": False, "death_date": None, "home": False, "where": "In NICU"}
    b.update(kw)
    return b


def card(b, today, **kw):
    args = dict(scan_dates=[], rop=None, mri=None, booked={}, calendar_complete=False, form_h_done=False,
                location="Nursery")
    args.update(kw)
    return ft.timeline(b, today, **args)


def by_key(c):
    return {r["key"]: r for r in c["rows"]}


def test_time_points_dates_and_order():
    today = date(2026, 11, 26)                                       # DOL 35, PMA 34+5
    c = card(baby(form_i=fi(resp_support_72h=True, sepsis_eos=False, mortality_7_days=False,
                            mortality_28_days=False)),
             today, scan_dates=[DOB + timedelta(days=26)], rop=NS(screenings=[{"date": "2026-11-20", "method": "x"}]))
    keys = [r["key"] for r in c["rows"]]
    assert keys == ["d3", "d7", "d28", "rop", "end", "cp36", "cp40", "cp44"]  # discharge before next checkpoint
    r = by_key(c)
    assert r["d3"]["date"] == "2026-10-25" and r["d3"]["items"][0]["status"] == "done"
    assert r["d7"]["window"] == "28 Oct 26 – 30 Oct 26"
    assert r["d7"]["items"][0]["status_text"] == "Scan missing"       # no scan on DOL 5-10
    assert r["d28"]["items"][0]["status"] == "done"                   # scan on DOL 27
    assert r["rop"]["items"][0]["status"] == "done"
    assert r["cp36"]["date"] == "2026-12-05" and r["cp36"]["items"][0]["status"] == "due"
    assert "assess on the ward" in r["cp36"]["items"][0]["status_text"]
    assert [i["form"] for i in r["cp40"]["items"]] == ["Form I", "Form K", "Form F"]
    assert r["end"]["items"][0]["status_text"] == "at discharge"
    assert c["status"] == "Admitted (Nursery)" and c["now"] == "DOL 35 · PMA 34+5"
    assert c["next"]["label"] == "36 wk PMA" and c["next"]["text"].endswith("(in 9 days)")
    assert c["counts"]["overdue"] == 1                                # the missing day-7 scan


def test_discharged_and_died():
    today = date(2026, 12, 2)
    end = {"date": date(2026, 11, 20), "died": False}               # left on DOL 29, before the 40 wk window
    c = card(baby(end=end, home=True), today, calendar_complete=True, form_h_done=True,
             mri=NS(selected_for_mri=False, overall_mri=None))
    r = by_key(c)
    assert r["end"]["date"] == "2026-11-20" and r["end"]["label"] == "Discharge"
    forms = {i["text"]: i for i in r["end"]["items"]}
    assert forms["Follow-up dates booked (Form H calendar)"]["status"] == "done"
    assert forms["Final cranial USG (before discharge)"]["status"] == "overdue"
    assert len(r["cp40"]["items"]) == 2 and r["cp40"]["items"][1]["status_text"] == "not in the MRI subset"
    assert c["status"] == "Discharged 20 Nov 26"
    dead = card(baby(died=True, death_date=date(2026, 10, 25), end={"date": date(2026, 10, 25), "died": True}),
                today)
    r = by_key(dead)
    assert r["end"]["label"] == "Death"
    assert r["cp36"]["items"][0]["status"] == "na" and r["d28"]["items"][0]["status"] == "na"
    assert r["d7"]["items"][1]["text"] == "Death ≤ 7 days" and r["d7"]["items"][1]["status"] == "overdue"
