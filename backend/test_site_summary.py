from datetime import date, datetime, timedelta
from types import SimpleNamespace

from site_summary import cranial_windows, evaluate

TODAY = date(2026, 11, 20)
NOW = datetime(2026, 11, 20, 8, 0)
DOB = date(2026, 11, 1)          # DOL 20 today


def resp(day, **kw):
    base = dict(nicu_day=day, support_modes="", endotracheal_intubation=None, vasoactive_support=None,
                respiratory_support=None, pda_medical_rx=None, hs_pda=None, pneumothorax=None,
                pulm_hemorrhage=None, shock=None, clinical_seizures=None, eeg_seizures=None)
    base.update(kw)
    return SimpleNamespace(**base)


def inf(day, **kw):
    base = dict(nicu_day=day, antibiotics=None, nec_suspected=None, nec_confirmed_stage=None, phototherapy=None,
                exchange_transfusion=None, prbc_transfusion=None, platelet_transfusion=None)
    base.update(kw)
    return SimpleNamespace(**base)


def metab(day, **kw):
    base = dict(nicu_day=day, sodium_value=None, potassium_value=None, lowest_glucose=None, aki_stage=None,
                aki_kdigo_stage=None)
    base.update(kw)
    return SimpleNamespace(**base)


def baby(**kw):
    b = {"enrollment_id": "01-0001", "site": "PGIMER", "dob": DOB, "ga_days": 28 * 7, "birth_weight": 1100,
         "end_date": None, "died": False, "candidates": [], "pending_usg": [], "ae_events": [], "sae_rows": [],
         "has_sae_report": False, "resp_logs": [], "inf_logs": [], "metab_logs": [], "nec_stage": None,
         "rop": None, "scan_entries": [{"scanDate": (DOB + timedelta(days=d - 1)).isoformat()} for d in (5, 12)],
         "helper2_brain_flag": False, "study_outcomes": None, "form_h_complete": False,
         "form_i_complete": False, "tasks": []}
    b.update(kw)
    return b


def codes(r, part):
    return [c for c, _ in r[part]]


def test_quiet_baby_has_nothing_on_watch():
    r = evaluate(baby(), TODAY, NOW, None)
    assert r["watch"] == [] and r["active"] == []


def test_w1_grade3_ae_without_sae_decision():
    ev = {"definition_no": "nec", "description": "NEC", "start_date": "2026-11-10", "grade": "3",
          "converted_to_sae": ""}
    assert codes(evaluate(baby(ae_events=[ev]), TODAY, NOW, None), "watch") == ["W1"]
    assert evaluate(baby(ae_events=[dict(ev, converted_to_sae="No")]), TODAY, NOW, None)["watch"] == []


def test_w1_auto_detected_grade3_not_on_ae_form_also_m9():
    c = {"definition_no": "ivh", "description": "IVH", "start_date": "2026-11-03", "grade": "3"}
    r = evaluate(baby(candidates=[c]), TODAY, NOW, None)
    assert "W1" in codes(r, "watch") and "M9" in codes(r, "missed")


def test_w2_grade_up_since_last_summary_only():
    c = {"definition_no": "ivh", "description": "IVH", "start_date": "2026-11-03", "grade": "3"}
    ae = [dict(c, converted_to_sae="No")]
    assert "W2" in codes(evaluate(baby(candidates=[c], ae_events=ae), TODAY, NOW, {"ivh": 2}), "watch")
    assert "W2" not in codes(evaluate(baby(candidates=[c], ae_events=ae), TODAY, NOW, {"ivh": 3}), "watch")
    assert "W2" not in codes(evaluate(baby(candidates=[c], ae_events=ae), TODAY, NOW, {}), "watch")


def test_w4_proven_infection_last_7_days():
    c = {"definition_no": "sepsis_culture_positive", "description": "Culture-positive sepsis", "grade": "2",
         "start_date": "2026-11-16"}
    assert "W4" in codes(evaluate(baby(candidates=[c]), TODAY, NOW, None), "watch")
    old = dict(c, start_date="2026-11-05")
    assert "W4" not in codes(evaluate(baby(candidates=[old]), TODAY, NOW, None), "watch")


def test_w5_suspected_nec_unless_stage_2a():
    logs = [inf(18, nec_suspected=True)]
    assert "W5" in codes(evaluate(baby(inf_logs=logs), TODAY, NOW, None), "watch")
    assert "W5" not in codes(evaluate(baby(inf_logs=logs, nec_stage="IIA"), TODAY, NOW, None), "watch")


def test_w6_bands():
    r = evaluate(baby(metab_logs=[metab(19, sodium_value="125", potassium_value="7.0", aki_kdigo_stage="2")]),
                 TODAY, NOW, None)
    assert codes(r, "watch") == ["W6", "W6", "W6"]
    assert evaluate(baby(metab_logs=[metab(19, sodium_value="135")]), TODAY, NOW, None)["watch"] == []
    two_lows = [metab(15, lowest_glucose="35"), metab(17, lowest_glucose="38")]
    assert codes(evaluate(baby(metab_logs=two_lows), TODAY, NOW, None), "watch") == ["W6"]
    assert evaluate(baby(metab_logs=two_lows[:1]), TODAY, NOW, None)["watch"] == []


def test_w7_new_invasive_ventilation_or_inotropes():
    logs = [resp(18, support_modes="CPAP"), resp(19, support_modes="SIMV", vasoactive_support=True)]
    assert codes(evaluate(baby(resp_logs=logs), TODAY, NOW, None), "watch") == ["W7", "W7"]
    steady = [resp(18, support_modes="SIMV"), resp(19, support_modes="SIMV")]
    assert evaluate(baby(resp_logs=steady), TODAY, NOW, None)["watch"] == []


def test_w8_acute_event():
    assert codes(evaluate(baby(resp_logs=[resp(17, pneumothorax=True)]), TODAY, NOW, None), "watch") == ["W8"]


def test_w9_death_without_sae_report():
    b = baby(died=True, end_date=date(2026, 11, 15))
    assert "W9" in codes(evaluate(b, TODAY, NOW, None), "watch")
    assert "W9" not in codes(evaluate(dict(b, has_sae_report=True), TODAY, NOW, None), "watch")


def test_w10_sae_deadlines():
    row = {"sae": "Death", "start_date": "2026-11-08", "notification_24h": "", "notify_initial": ""}
    r = evaluate(baby(sae_rows=[row]), TODAY, NOW, None)
    assert [t for c, t in r["watch"] if c == "W10"] == [
        "Death from 08 Nov: 24-hour notification not recorded", "Death: 14-day report due 22 Nov"]
    done = dict(row, notification_24h="2026-11-08", notify_initial="2026-11-12")
    assert evaluate(baby(sae_rows=[done]), TODAY, NOW, None)["watch"] == []


def test_active_morbidities():
    b = baby(inf_logs=[inf(19, antibiotics=True, phototherapy=True)],
             resp_logs=[resp(19, respiratory_support=True, support_modes="CPAP")])
    act = evaluate(b, TODAY, NOW, None)["active"]
    assert act == ["Sepsis / infection: on antibiotics (DOL 19)", "Respiratory support (CPAP)",
                   "Jaundice on phototherapy / exchange"]


def test_cranial_schedule():
    assert [w[0] for w in cranial_windows(27 * 7, 900)] == ["Day 1-3", "Day 4-7", "Day 10-14", "Day 28",
                                                           "36 wk PMA", "40 wk PMA"]
    assert [w[0] for w in cranial_windows(30 * 7, 1300)] == ["Day 4-7", "Day 10-14", "Day 28", "40 wk PMA"]
    # 28 wk / 1100 g baby at DOL 20 scanned DOL 5 and 12: nothing missed yet
    assert "M2" not in codes(evaluate(baby(), TODAY, NOW, None), "missed")
    r = evaluate(baby(scan_entries=[]), TODAY, NOW, None)
    assert [t for c, t in r["missed"] if c == "M2"] == ["Cranial USG Day 4-7 not done",
                                                       "Cranial USG Day 10-14 not done"]


def test_m4_rop_by_dol_30():
    late = TODAY + timedelta(days=11)          # DOL 31
    assert "M4" in codes(evaluate(baby(), late, NOW, None), "missed")
    assert "M4" not in codes(evaluate(baby(), TODAY, NOW, None), "missed")
    seen = SimpleNamespace(screenings=[{"date": "2026-11-25", "method": "Indirect"}], worst_stage=None,
                           treatment_required=None, outcome=None)
    assert "M4" not in codes(evaluate(baby(rop=seen), late, NOW, None), "missed")


def test_m5_checkpoint_and_m6_48_hours():
    old = baby(dob=date(2026, 10, 14), ga_days=27 * 7)        # 36 wk PMA on 2026-12-16
    assert "M5" not in codes(evaluate(old, TODAY, NOW, None), "missed")
    assert "M5" in codes(evaluate(old, date(2026, 12, 17), NOW, None), "missed")
    ended = baby(end_date=date(2026, 11, 18))
    assert "M6" not in codes(evaluate(ended, TODAY, datetime(2026, 11, 19, 23, 0), None), "missed")
    assert "M6" in codes(evaluate(ended, TODAY, datetime(2026, 11, 20, 1, 0), None), "missed")
    assert "M6" not in codes(evaluate(dict(ended, form_h_complete=True, form_i_complete=True), TODAY, NOW, None),
                             "missed")


def test_ae_form_term_by_key_code_or_name():
    from site_summary import term_of
    assert term_of({"definition_no": "ivh"}) == "ivh"
    assert term_of({"definition_no": "C154928 | 10082059"}) == "sepsis_culture_negative"
    assert term_of({"definition_no": "NA", "description": "Hyperbilirubinemia"}) == "hyperbilirubinemia"
    assert term_of({"definition_no": "NA", "description": "something else"}) is None
    # a saved AE of the same term (other start date) is not raised again as auto-detected
    ev = {"definition_no": "NA", "description": "Hyperbilirubinemia", "start_date": "2026-11-04", "grade": "3",
          "converted_to_sae": "No"}
    c = {"definition_no": "hyperbilirubinemia", "description": "Hyperbilirubinemia", "start_date": "2026-11-05",
         "grade": "3"}
    r = evaluate(baby(ae_events=[ev], candidates=[c]), TODAY, NOW, None)
    assert r["watch"] == [] and "M9" not in codes(r, "missed")
