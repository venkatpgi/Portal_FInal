"""Outcome matrix (outcome_matrix.py, PI 2026-11-26)."""
from datetime import date
from types import SimpleNamespace as NS

import outcome_matrix as om

TODAY = date(2026, 12, 20)


def comp(value, source="Form I", detail=""):
    return {"name": "x", "value": value, "source": source, "detail": detail}


def baby(**kw):
    b = {"site": "PGIMER", "enrollment_id": "01-B-001", "dob": date(2026, 10, 20), "ga_days": 196,
         "form_i": None, "end": None, "died": False, "death_date": None}
    b.update(kw)
    return b


def test_cell_states():
    c = om.cell("Yes", target=date(2026, 12, 15), today=TODAY, died=False, recorded=True, when=date(2026, 11, 3))
    assert c["state"] == "yes" and c["text"] == "Yes · 03 Nov 2026" and c["source"] == "recorded"
    assert om.cell("No", target=None, today=TODAY, died=False, recorded=False)["source"] == "detected"
    assert om.cell(None, target=date(2026, 12, 19), today=TODAY, died=False, recorded=False)["state"] == "pending"
    late = om.cell(None, target=date(2026, 12, 17), today=TODAY, died=False, recorded=False)
    assert late["state"] == "overdue" and late["text"] == "overdue since 17 Dec 2026"
    assert om.cell(None, target=date(2026, 12, 1), today=TODAY, died=True, recorded=False)["state"] == "na"
    assert om.cell(None, target=date(2026, 12, 1), today=TODAY, died=True, recorded=False,
                   is_death=True)["state"] == "overdue"
    assert om.cell("NA", target=None, today=TODAY, died=False, recorded=False)["state"] == "na"


def test_row_sources_dates_and_composites():
    fi = NS(**{f"{k}{wk}{s}": None for wk in (36, 40, 44)
               for k, s in (("death", ""), ("death", "_date"), ("nec", "_stage"), ("nec", "_date"),
                            ("ivh", "_grade3"), ("ivh", "_date"), ("cpvl", "_grade2"), ("cpvl", "_date"),
                            ("rop", "_treated"), ("rop", "_date"))},
           bpd36_jensen_grade="Grade 1", bpd36_jensen_date=date(2026, 12, 15))
    fi.nec36_stage, fi.nec36_date = True, date(2026, 11, 20)
    c = {"checkpoint_36": "2026-12-15", "checkpoint_44": "2027-02-09",
         "components": {"death36": comp("No"), "death44": comp(None, "", "alive to 18 Dec"),
                        "bpd": comp("Yes", "Form I", "Grade 1"), "nec": comp("Yes"),
                        "brain": comp("No", "brain injury suggestion"), "rop": comp(None, "", "no ROP data")},
         "composite_1": {"value": "Yes", "note": "Yes because BPD"},
         "composite_2": {"value": "Yes", "note": "Yes because NEC"},
         "mri_abnormality": {"value": "NA", "note": "Not in the MRI subset"}}
    visits = {36: {"status": "done", "text": "Done on Form I", "due": date(2026, 12, 15),
                   "window_to": date(2026, 12, 17)},
              40: {"status": "booked", "text": "Booked", "due": date(2027, 1, 12), "booked": date(2027, 1, 13),
                   "window_to": date(2027, 1, 14)}}
    r = om.row_for(baby(form_i=fi), c, visits, TODAY)
    cells = r["cells"]
    assert cells["bpd"]["text"] == "Yes · 15 Dec 2026" and cells["bpd"]["source"] == "recorded"
    assert cells["nec"]["text"] == "Yes · 20 Nov 2026"
    assert cells["brain"]["state"] == "no" and cells["brain"]["source"] == "detected"
    assert cells["rop"]["state"] == "pending" and cells["rop"]["text"] == "due 09 Feb 2027"
    assert cells["death"]["state"] == "pending"
    assert cells["mri"]["state"] == "na"
    assert cells["composite_1"]["state"] == "yes" and cells["composite_1"]["source"] == "recorded"
    assert cells["visit36"]["text"] == "Done" and cells["visit40"]["text"] == "booked 13 Jan 2027"
    assert cells["visit44"]["text"] == "date unknown"
    t = om.totals([r])
    assert t["nec"]["yes"] == 1 and t["rop"]["pending"] == 1
    secs = om.report_sections([r], lambda s: s)
    assert secs[1]["rows"][0][0] == "01-B-001" and "No *" in secs[1]["rows"][0]   # brain injury detected only


def test_died_baby_rest_not_applicable():
    c = {"checkpoint_36": "2026-12-15", "checkpoint_44": "2027-02-09",
         "components": {"death44": comp("Yes", "Helper 5 Day 3", "died 22-10-2026"), "bpd": comp(None),
                        "nec": comp(None), "brain": comp(None), "rop": comp(None), "death36": comp("Yes", "x")},
         "composite_1": {"value": "Yes"}, "composite_2": {"value": "Yes"},
         "mri_abnormality": {"value": None}}
    r = om.row_for(baby(died=True, death_date=date(2026, 10, 22), end={"date": date(2026, 10, 22), "died": True}),
                   c, {}, TODAY)
    assert r["cells"]["death"]["text"] == "Yes · 22 Oct 2026" and r["cells"]["death"]["source"] == "detected"
    assert r["cells"]["bpd"]["state"] == "na" and r["status"] == "Died"
    assert r["cells"]["composite_1"]["source"] == "detected"
