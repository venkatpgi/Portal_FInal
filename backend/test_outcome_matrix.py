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
    assert c["state"] == "yes" and c["text"] == "Yes · 03 Nov 26" and c["source"] == "recorded"
    assert om.cell("No", target=None, today=TODAY, died=False, recorded=False)["source"] == "detected"
    assert om.cell(None, target=date(2026, 12, 19), today=TODAY, died=False, recorded=False)["state"] == "pending"
    late = om.cell(None, target=date(2026, 12, 17), today=TODAY, died=False, recorded=False)
    assert late["state"] == "overdue" and late["text"] == "overdue · 17 Dec 26"
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
    assert cells["k_bpd"]["text"] == "Yes · 15 Dec 26" and cells["k_bpd"]["source"] == "recorded"
    assert cells["k_nec"]["text"] == "Yes · 20 Nov 26"
    assert cells["k_brain"]["state"] == "no" and cells["k_brain"]["source"] == "detected"
    assert cells["k_rop"]["state"] == "pending" and cells["k_rop"]["text"] == "due 09 Feb 27"
    assert cells["k_death"]["state"] == "pending"
    assert cells["k_mri"]["state"] == "na"
    assert cells["composite_1"]["state"] == "yes" and cells["composite_1"]["source"] == "recorded"
    assert cells["visit36"]["text"] == "Done" and cells["visit40"]["text"] == "booked 13 Jan 27"
    assert cells["visit44"]["text"] == "date unknown"
    t = om.totals([r])
    assert t["k_nec"]["yes"] == 1 and t["k_rop"]["pending"] == 1
    assert om.total_text(t["k_nec"]).startswith("Yes 1")
    secs = om.report_sections([r], lambda s: s)
    assert all(x["title"].startswith(label) for x, (_, label) in zip(secs, om.SECTIONS)) and len(secs) == len(om.SECTIONS)
    key = secs[0]
    assert key["rows"][0][0] == "Totals" and key["rows"][1][0] == "01-B-001" and "No *" in key["rows"][1]


def test_died_baby_rest_not_applicable():
    c = {"checkpoint_36": "2026-12-15", "checkpoint_44": "2027-02-09",
         "components": {"death44": comp("Yes", "Helper 5 Day 3", "died 22-10-2026"), "bpd": comp(None),
                        "nec": comp(None), "brain": comp(None), "rop": comp(None), "death36": comp("Yes", "x")},
         "composite_1": {"value": "Yes"}, "composite_2": {"value": "Yes"},
         "mri_abnormality": {"value": None}}
    r = om.row_for(baby(died=True, death_date=date(2026, 10, 22), end={"date": date(2026, 10, 22), "died": True}),
                   c, {}, TODAY)
    assert r["cells"]["k_death"]["text"] == "Yes · 22 Oct 26" and r["cells"]["k_death"]["source"] == "detected"
    assert r["cells"]["k_bpd"]["state"] == "na" and r["status"] == "Died"
    # Form I items due after the death are not applicable; birth items still asked
    assert r["cells"]["bpd36_jensen_grade"]["state"] == "na"
    assert r["cells"]["ventilation_required"]["text"] == "not entered"
    assert r["cells"]["composite_1"]["source"] == "detected"



def test_form_i_items_in_time_order_with_suggestions():
    cols = om.columns()
    secs = [c["section"] for c in cols]
    order = [k for k, _ in om.SECTIONS]
    assert secs == sorted(secs, key=order.index)                     # never goes back in time
    assert [c["key"] for c in cols if c["section"] == "birth"][0] == "ventilation_required"
    fi = NS(ventilation_required=True, hie_grade="None", bpd36_jensen_grade=None, mv_days=None)
    sugg = {"resp_support_72h": "Yes", "mv_days": 5, "bpd36_jensen_grade": "Grade 2",
            "mortality_7_days": "No", "time_to_spontaneous_breathing": 45}
    b = baby(form_i=fi, end={"date": date(2026, 12, 1), "died": False})
    r = om.row_for(b, {"checkpoint_36": "2026-12-15", "checkpoint_44": "2027-02-09", "components": {},
                       "mri_abnormality": {}}, {}, TODAY, None, sugg)
    c = r["cells"]
    assert c["ventilation_required"] == {"state": "yes", "text": "Yes", "source": "recorded", "note": ""}
    assert c["hie_grade"]["state"] == "no" and c["hie_grade"]["text"] == "None"
    assert c["resp_support_72h"]["state"] == "yes" and c["resp_support_72h"]["source"] == "detected"
    assert c["mv_days"]["text"] == "5" and c["mv_days"]["state"] == "val"
    assert c["time_to_spontaneous_breathing"]["text"] == "45"
    assert c["bpd36_jensen_grade"]["text"] == "Grade 2" and c["bpd36_jensen_grade"]["source"] == "detected"
    assert c["switched_100_o2"]["text"] == "not entered"                 # birth item, nothing anywhere
    assert c["death40"]["text"] == "due 12 Jan 27"
    assert c["sepsis_los"]["state"] == "overdue"                        # stay ended 1 Dec, nothing known
    admitted = om.row_for(baby(form_i=None), {"components": {}, "mri_abnormality": {}}, {}, TODAY, None, {})
    assert admitted["cells"]["sepsis_los"]["text"] == "at discharge"



def test_number_columns_median_and_range():
    def r(n):
        return {"cells": {"mv_days": {"state": "val", "text": str(n), "source": "recorded"},
                          "cpap_days": {"state": "pending", "text": "at discharge", "source": ""}}}
    rows = [r(0), r(5), r(21), {"cells": {"mv_days": {"state": "pending", "text": "at discharge", "source": ""}}}]
    t = om.summary_texts(rows)
    assert t["mv_days"] == "Median 5 d (0–21) · 3 babies · Due 1"
    assert t["cpap_days"] == "Due 3"                                      # no numbers yet: counts as before
    assert om.summary_texts([r(4), r(7)])["mv_days"].startswith("Median 5.5 d (4–7) · 2 babies")
