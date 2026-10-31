from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers.shift_report import _site
from shift_report import area_of, build, file_name, morbidities_of, morbidity_text, render_pdf, row_of

TODAY = date(2026, 11, 20)


def log(day, location):
    return SimpleNamespace(nicu_day=day, location=location)


def test_area_is_latest_day_with_a_location():
    assert area_of([log(3, "NICU"), log(9, "NICU, KMC-N"), log(10, "")]) == ("NICU, KMC-N", 9)
    assert area_of([log(3, None)]) == ("Not recorded", None)


def test_morbidities_merge_form_and_detector_keep_worst_grade():
    b = {"ae_events": [{"definition_no": "ivh", "grade": "2"}, {"description": "Sclerema", "grade": None}],
         "candidates": [{"definition_no": "ivh", "grade": 3}, {"definition_no": "hyponatremia", "grade": 2}]}
    assert [morbidity_text(m) for m in morbidities_of(b)] == [
        "Neonatal Intraventricular Hemorrhage (IVH) grade 3",
        "Hyponatremia grade 2 (auto-detected)",
        "Sclerema",
    ]


def test_severe_scan_not_in_form_h_is_listed():
    b = {"pending_usg": [{"side": "Left", "finding": "IVH", "grade": "Grade III"}]}
    assert morbidity_text(morbidities_of(b)[0]) == "Form F: Left IVH grade Grade III (auto-detected)"


def test_stay_ended_shows_status_then_drops_after_seven_days():
    b = {"enrollment_id": "01-B-1", "metab_logs": [log(3, "NICU")], "died": False}
    assert row_of({**b, "end_date": None}, TODAY)["area"] == "NICU"
    assert row_of({**b, "end_date": date(2026, 11, 13)}, TODAY)["area"] == "Discharged 13 Nov"
    assert row_of({**b, "end_date": date(2026, 11, 13), "died": True}, TODAY)["area"] == "Died 13 Nov"
    assert row_of({**b, "end_date": date(2026, 11, 12)}, TODAY) is None


def test_row_never_carries_a_name_or_arm():
    b = {"enrollment_id": "01-B-1", "end_date": None, "baby_name": "X", "arm": "A", "metab_logs": []}
    assert set(row_of(b, TODAY)) == {"enrollment_id", "area", "area_day", "morbidities"}


def report(babies):
    return {"site": "PGIMER", "site_name": "PGIMER", "generated_at": "2026-11-20T08:15", "training": False,
            "babies": babies}


def test_pdf_with_rows_nil_and_markup_in_free_text():
    row = {"enrollment_id": "01-B-1", "area": "NICU", "area_day": 9, "morbidity_text": "A <b & c"}
    for r in (report([row]), report([]), {**report([]), "training": True}):
        assert render_pdf(r).startswith(b"%PDF")
    assert file_name(report([])) == "PORTAL_PGIMER_report_2026-11-20_0815.pdf"


def user(role, site=None):
    return SimpleNamespace(role=role, site_name=site)


def test_who_may_generate_for_which_site():
    assert _site(user("nurse", "GMCH"), "PGIMER") == "GMCH"
    assert _site(user("site_pi", "AMC"), None) == "AMC"
    assert _site(user("superadmin"), "IOG") == "IOG"
    with pytest.raises(HTTPException) as no_site:
        _site(user("superadmin"), None)
    assert no_site.value.status_code == 422
    with pytest.raises(HTTPException) as pts3:
        _site(user("tech_support", "PGIMER"), "PGIMER")
    assert pts3.value.status_code == 403
