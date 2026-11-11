from datetime import date, datetime
from types import SimpleNamespace as NS

import pytest

import data_checks
import value_ranges as vr


def test_rates_from_live_examples():
    # 01-B-006 day 12, 975 g: 130.6 ml in 6 h is 22.3 ml/kg/hr
    assert vr.rate(130.6, 0.975, 6) == 22.32 and vr.level(22.32) == "impossible"
    assert vr.level(vr.rate(65.5, 1.02, 6)) == "high"      # 10.7
    assert vr.level(vr.rate(1, 1.555, 6)) == "low"         # 0.11
    assert vr.level(vr.rate(26, 0.975, 6)) is None         # 4.4


def test_effective_weight_follows_the_screen():
    assert vr.effective_weight_kg(1020, None) == 1.02
    assert vr.effective_weight_kg(1020, 0.95) == 1.02       # DMS still below birth weight
    assert vr.effective_weight_kg(1020, 1.3) == 1.3
    assert vr.effective_weight_kg(None, None) is None


def test_total_over_recorded_windows_only():
    v = {"urine_output_8am_2pm": 12, "urine_output_2pm_8pm": None, "urine_output_8pm_8am": 24,
         "urine_output_2pm_8pm_status": None}
    assert vr.fmt(vr.total_rate(v, 1.0)) == "2"             # 36 ml over 18 h
    v["urine_output_8am_2pm_status"] = "Not Recorded / Not Done"
    assert vr.fmt(vr.total_rate(v, 1.0)) == "2"             # 24 ml over 12 h


def test_dms_weight_latest_on_or_before():
    rows = [("2026-11-01", '{"growth_a": [{"date": "2026-11-01", "time": "08:00", "weight_g": "1000"}]}'),
            ("2026-11-05", '{"growth_a": [{"weight_g": "1100", "time": "08:00"}]}'),
            ("2026-11-06", "not json")]
    w = vr.dms_weights(rows)
    assert vr.dms_weight_on(w, "2026-11-04") == 1.0 and vr.dms_weight_on(w, "2026-11-09") == 1.1
    assert vr.dms_weight_on(w, "2026-10-30") is None


@pytest.fixture
def one_kg(monkeypatch):
    monkeypatch.setattr(vr, "weight_for_day", lambda db, e, d: 1.0)


def test_save_refuses_impossible_value_being_typed(one_kg):
    with pytest.raises(vr.RangeError, match="more than 15 ml/kg/hr"):
        vr.check_urine_save(None, "01-B-006", 12, {"urine_output_8am_2pm": 130.6}, None)


def test_save_allows_high_and_stores_server_total(one_kg):
    out = vr.check_urine_save(None, "01-B-006", 12, {"urine_output_8am_2pm": 48, "urine_output_8pm_8am": 24}, None)
    assert out["urine_output_total"] == "4"                 # 72 ml / 18 h
    assert out["urine_output_8am_2pm"] == 48


def test_old_wrong_value_does_not_block_other_edits(one_kg):
    prior = NS(urine_output_8am_2pm=130.6, urine_output_8am_2pm_status=None, urine_output_2pm_8pm=None,
               urine_output_2pm_8pm_status=None, urine_output_8pm_8am=None, urine_output_8pm_8am_status=None)
    out = vr.check_urine_save(None, "01-B-006", 12, {"urine_output_2pm_8pm": 26, "urine_output_8am_2pm": 130.6}, prior)
    assert out["urine_output_2pm_8pm"] == 26
    # unrelated saves pass straight through
    assert vr.check_urine_save(None, "01-B-006", 12, {"dialysis_crrt": False}, prior) == {"dialysis_crrt": False}


def _day(nicu_day, am=None, pm=None, night=None, **status):
    return {"enrollment_id": "01-B-006", "nicu_day": nicu_day, "birth_weight": 975.0,
            "date_of_birth": date(2026, 10, 30), "site_name": "PGIMER",
            "urine_output_8am_2pm": am, "urine_output_2pm_8pm": pm, "urine_output_8pm_8am": night,
            "urine_output_8am_2pm_status": status.get("am_s"), "urine_output_2pm_8pm_status": status.get("pm_s"),
            "urine_output_8pm_8am_status": status.get("night_s")}


def test_out_of_range_query_per_window_with_ml_facts():
    ctx = {"now": datetime(2026, 11, 11, 12, 0), "dms_weights": {},
           "urine_days": [_day(12, 130.6, 26, 29.3), _day(3, 42)]}
    found = data_checks.check_urine_out_of_range(ctx)
    keys = sorted(f["record_key"] for f in found)
    assert keys == ["01-B-006/D12/8am-2pm", "01-B-006/D3/8am-2pm"]
    f = next(f for f in found if "D12" in f["record_key"])
    assert "22.32 ml/kg/hr" in f["detail"] and f["facts"] == {"ml": 130.6, "level": "impossible"}


def test_missing_windows_only_after_the_day_is_over():
    # born 30 Oct: day 12 = 10 Nov, last window ends 11 Nov 08:00 IST, raised from 12 Nov 08:00 IST
    days = [_day(12, 130.6, None, 29.3), _day(11, None, None, None, am_s="Not Recorded / Not Done")]
    ctx = {"now": datetime(2026, 11, 11, 12, 0), "urine_days": days}
    assert [f["facts"] for f in data_checks.check_urine_window_missing(ctx)] == [{"missing": [[11, ["2pm-8pm", "8pm-8am"]]]}]
    ctx["now"] = datetime(2026, 11, 12, 3, 0)
    f = data_checks.check_urine_window_missing(ctx)[0]
    assert f["facts"] == {"missing": [[11, ["2pm-8pm", "8pm-8am"]], [12, ["2pm-8pm"]]]}
    assert "day 11 (2pm-8pm, 8pm-8am); day 12 (2pm-8pm)" in f["detail"]


def test_checks_registered():
    assert {"URINE_OUT_OF_RANGE", "URINE_WINDOW_MISSING"} <= set(data_checks.CHECKS_BY_ID)
