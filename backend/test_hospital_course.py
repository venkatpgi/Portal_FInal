"""Form H H12 Hospital Course from the daily logs (hospital_course.py)."""
from datetime import date, datetime

import data_checks as dc
import hospital_course as hc

DOB = date(2026, 10, 23)
END = date(2026, 12, 2)           # 40 days after birth


def test_needs_a_discharge_date():
    out = hc.build(DOB, None, [], [], [], {}, {})
    assert out["has_data"] is False and "discharge date" in out["why"]


def test_counts():
    helper5 = [(1, "DR,NICU"), (2, "NICU"), (3, "AMCC-4A (NICU)"), (4, "Nursery"), (5, ""), (6, None),
               (41, "NICU"), (42, "NICU")]                   # day 41 = discharge day counts; day 42 is after
    helper4 = [(10, 120.0), (14, 150.0), (12, 149.9), (20, 180.0), (3, None)]
    weights = [("2026-11-20", "08:00", 1500.0), ("2026-11-29", "08:00", 1800.0),
               ("2026-11-29", "20:00", 1810.0), ("2026-12-03", "08:00", 1900.0)]
    out = hc.build(DOB, END, helper5, helper4, weights,
                   {"oxygen_days": 12, "imv_days": 3, "cpap_days": 10}, {"pn_days": 7})
    assert out["total_los"] == 40                          # discharge - birth, not +1 (PI)
    assert out["nicu_days"] == 4                           # days 1, 2, 3 (old label), 41
    assert (out["o2_days"], out["vent_days"], out["cpap_days"], out["pn_days_summary"]) == (12, 3, 10, 7)
    assert out["age_full_feeds_summary"] == 13             # day 14 first >= 150 -> age 13
    assert out["discharge_weight"] == 1810.0 and out["discharge_weight_date"] == "2026-11-29"


def test_blank_when_not_in_logs():
    out = hc.build(DOB, END, [(1, None)], [(5, 100.0)], [("2026-11-01", "", 1200.0)], {}, {})
    assert out["nicu_days"] is None and out["age_full_feeds_summary"] is None
    assert out["discharge_weight"] is None                 # older than 7 days before discharge
    assert out["o2_days"] is None


def test_query_outcome_without_date():
    ctx = {"now": datetime(2026, 11, 24, 6), "site_of_eid": {"01-B-003": "PGIMER"},
           "formh_no_date": [{"enrollment_id": "01-B-003", "outcome": "Discharged",
                              "last_dms": "2026-11-24", "last_h5": 33}]}
    (q,) = dc.check_form_h_outcome_no_date(ctx)
    assert q["site_name"] == "PGIMER" and q["record_key"] == "01-B-003"
    assert "no discharge date" in q["detail"] and "DMS to 2026-11-24" in q["detail"]
    assert "Helper 5 to day 33" in q["detail"]
    ctx["formh_no_date"] = [{"enrollment_id": "01-B-009", "outcome": "Died", "last_dms": None, "last_h5": None}]
    (q,) = dc.check_form_h_outcome_no_date(ctx)
    assert "no date of death" in q["detail"] and "Daily logs" not in q["detail"]
