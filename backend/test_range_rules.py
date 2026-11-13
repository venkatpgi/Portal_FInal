import json
from datetime import datetime

import pytest

import data_checks
import range_rules as rr
from models import BirthResuscitation, MinimalMonitoringDayLog, NeonatalMorbidities, PostnatalDay1
from value_ranges import RangeError

RULE = {r.key: r for r in rr.RULES}


def test_pi_decisions_are_in_the_table():
    # changed by the PI on 12 Nov
    assert (RULE["birth_weight"].confirm_lo, RULE["birth_weight"].confirm_hi) == (400, 3000)
    assert RULE["tpiece_peep"].refuse_lo == 3 and RULE["dms_glucose"].refuse_hi == 600
    assert RULE["e_temp_axillary"].refuse_lo == 25 and RULE["dms_temp"].refuse_lo == 24
    assert RULE["h5_calcium"].confirm_lo == 0.6 and RULE["h_discharge_weight"].confirm_lo == 1000
    # dropped
    assert not any("sib" in r.key or r.column == "sib_peep_cmh2o" for r in rr.RULES)
    assert len({r.key for r in rr.RULES}) == len(rr.RULES)


def test_levels():
    r = RULE["dms_glucose"]
    assert rr.level(r, 650) == "impossible" and rr.level(r, 250) == "high"
    assert rr.level(r, 15) == "low" and rr.level(r, 90) is None and rr.level(r, None) is None
    assert rr.level(RULE["d_fio2"], 15) == "impossible" and rr.level(RULE["d_fio2"], 60) is None


def test_text_numbers():
    assert rr.text_numbers("45-60") == [45, 60]
    assert rr.text_numbers("45 – 60") == [45, 60]
    assert rr.text_numbers("7.05") == [7.05]
    assert rr.text_numbers("Result Awaited") == []
    assert rr.text_numbers("-12") == [-12]


def test_save_refuses_impossible_new_value():
    with pytest.raises(RangeError, match="Birth weight of 9750 g is not possible"):
        rr.check_object(None, BirthResuscitation(birth_weight=9750))
    rr.check_object(None, BirthResuscitation(birth_weight=975, cord_ph=6.7))   # low pH: warn, not refuse
    with pytest.raises(RangeError) as e:
        rr.check_object(None, NeonatalMorbidities(total_los_days=400))
    assert e.value.status_code == 422


def test_dms_new_reading_checked_old_reading_left_alone():
    old = {"met_a": [{"date": "2026-11-10", "time": "08:00", "glucose": 900}]}
    row = MinimalMonitoringDayLog(entries_json=json.dumps(old))
    with pytest.raises(RangeError, match="Glucose of 900"):
        rr.check_object(None, row)
    # a saved row whose old wrong reading stays, and a good one is added
    from sqlalchemy.orm.attributes import set_committed_value
    row = MinimalMonitoringDayLog()
    set_committed_value(row, "entries_json", json.dumps(old))
    row.entries_json = json.dumps({"met_a": old["met_a"] + [{"date": "2026-11-10", "time": "09:00", "glucose": 80}]})
    rr.check_object(None, row)


def test_dms_diastolic_must_be_below_systolic():
    row = MinimalMonitoringDayLog(entries_json=json.dumps({"cv_a": [{"time": "10:00", "sbp": 40, "dbp": 45}]}))
    with pytest.raises(RangeError, match="diastolic 45 mmHg is not below systolic 40"):
        rr.check_object(None, row)


def test_caffeine_is_checked_per_kg():
    with pytest.raises(RangeError, match="Caffeine loading dose of 60 mg/kg"):
        rr.check_object(None, PostnatalDay1(birth_weight=1000, caffeine_loading_abs=60))
    rr.check_object(None, PostnatalDay1(birth_weight=1000, caffeine_loading_abs=20))


def _ctx(**rows):
    return {"now": datetime(2026, 11, 12, 10, 0), "ranged_rows": rows, "weight_kg": {"01-B-006": 0.975}}


def test_value_out_of_range_query():
    ctx = _ctx(minimal_monitoring_day_logs=[{
        "enrollment_id": "01-B-006", "site_name": "PGIMER", "record_date": "2026-11-10",
        "entries_json": json.dumps({"met_a": [{"date": "2026-11-10", "time": "08:00", "glucose": 250},
                                              {"date": "2026-11-10", "time": "12:00", "glucose": 90},
                                              {"date": "2026-11-10", "time": "16:00", "glucose": 260}]})}],
        infect_gi_hema_day_logs=[{"enrollment_id": "01-B-006", "site_name": "PGIMER", "nicu_day": 5,
                                  "feed_volume": None, "hb_value": 6.5, "peak_tsb": None}])
    found = {f["record_key"]: f for f in data_checks.check_value_out_of_range(ctx)}
    g = found["01-B-006/dms_glucose/2026-11-10"]
    assert "250 mg/dL at 08:00, 260 mg/dL at 16:00" in g["detail"] and "Expected 20-200" in g["detail"]
    assert "01-B-006/h4_hb/day 5" in found


def test_cross_checks():
    ctx = _ctx(neonatal_morbidities=[{
        "enrollment_id": "01-B-006", "site_name": "PGIMER", "total_los_days": 40, "discharge_weight": 900,
        "vent_days": 45, "cpap_days": 10, "oxygen_days": None, "pn_days": 12}],
        minimal_monitoring_day_logs=[{
            "enrollment_id": "01-B-006", "site_name": "PGIMER", "record_date": "2026-11-10",
            "entries_json": json.dumps({"cv_a": [{"time": "10:00", "sbp": 50, "dbp": 30, "map_value": 60}],
                                        "growth_a": [{"date": "2026-11-09", "weight_g": 1000},
                                                     {"date": "2026-11-10", "weight_g": 1150}]})}])
    assert "ventilation 45" in data_checks.check_stay_days(ctx)[0]["detail"]
    assert "900 g after 40 days" in data_checks.check_discharge_weight(ctx)[0]["detail"]
    assert "mean 60 outside 30-50" in data_checks.check_dms_bp_order(ctx)[0]["detail"]
    assert "1000 g to 2026-11-10" in data_checks.check_dms_weight_jump(ctx)[0]["detail"]


def test_frontend_table_matches_backend():
    """frontend-app/src/utils/valueRanges.js must carry the same limits."""
    import os
    import re
    path = os.path.join(os.path.dirname(__file__), "..", "frontend-app", "src", "utils", "valueRanges.js")
    js = open(path, encoding="utf-8").read()
    conv = lambda x: None if x.strip() == "null" else float(x)
    fe = {k: tuple(conv(x) for x in lim) for k, *lim in
          re.findall(r'R\("(\w+)", "[^"]*", "[^"]*", ([^,]+), ([^,]+), ([^,]+), ([^,\)]+)', js)}
    be = {tuple(None if v is None else float(v) for v in (r.confirm_lo, r.confirm_hi, r.refuse_lo, r.refuse_hi))
          for r in rr.RULES}
    assert len(fe) >= 35
    assert [k for k, lim in fe.items() if lim not in be] == []
    for k in fe:   # same key means the same limits
        if k in RULE:
            r = RULE[k]
            assert fe[k] == tuple(None if v is None else float(v)
                                  for v in (r.confirm_lo, r.confirm_hi, r.refuse_lo, r.refuse_hi)), k
