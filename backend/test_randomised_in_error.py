from datetime import datetime, time
from types import SimpleNamespace as NS

import pytest

import data_checks
import randomised_in_error as rie
from participant_counts import _form_b_keys
from patient_stage import patient_stage


def saved(eid="01-B-007", ppv=False, activated=True):
    return NS(enrollment_id=eid, required_resuscitation=ppv, blender_activated=activated, randomisation_date=None)


def test_new_record_in_error_keeps_blender_id_and_is_not_randomised():
    out = rie.apply_rules({"required_resuscitation": False, "blender_activated": True, "randomised": None},
                          None, "01-b-007", "nurse")
    assert out["randomised"] is False and out["blender_letter"] == "B"


def test_in_error_needs_the_blenders_complete_id():
    for eid in ("NR-01-0140", "01-B-", None):
        with pytest.raises(rie.RuleError, match="enrollment ID the blender showed"):
            rie.apply_rules({"required_resuscitation": False, "blender_activated": True}, None, eid, "nurse")


def test_activation_flag_only_without_ppv():
    with pytest.raises(rie.RuleError, match="only when PPV was not required"):
        rie.apply_rules({"required_resuscitation": True, "blender_activated": True}, None, "01-A-001", "nurse")


def test_ordinary_no_ppv_and_randomised_saves_untouched():
    p = {"required_resuscitation": False, "blender_activated": False}
    assert rie.apply_rules(p, None, "NR-01-0140", "nurse") == p
    p = {"required_resuscitation": True, "blender_activated": False, "randomised": True}
    assert rie.apply_rules(p, None, "01-A-003", "nurse") == p


def test_nurse_cannot_reclassify_or_undo():
    with pytest.raises(rie.RuleError, match="Only the site PI or the Global PI"):
        rie.apply_rules({"required_resuscitation": True}, saved(), "01-B-007", "nurse")
    with pytest.raises(rie.RuleError, match="stays on record"):
        rie.apply_rules({"blender_activated": False}, saved(), "01-B-007", "site_pi")
    with pytest.raises(rie.RuleError, match="cannot be changed"):
        rie.apply_rules({"blender_activated": True}, saved(), "01-B-008", "superadmin")


def test_site_pi_reclassifies_to_ppv_yes():
    out = rie.apply_rules({"required_resuscitation": True, "randomised": True}, saved(), "01-B-007", "site_pi")
    assert out["blender_activated"] is False and out["randomised"] is True


def test_autosave_without_the_flag_keeps_record():
    # autosave sends blender_activated null: the saved answer stands
    out = rie.apply_rules({"required_resuscitation": False, "blender_activated": None}, saved(), "01-B-007", "nurse")
    assert out["randomised"] is False


def test_schema_round_trip_marks_fields_as_set():
    from schemas import BirthResuscitationCreate
    data = BirthResuscitationCreate(screening_id="01-0140", enrollment_id="01-B-007",
                                    required_resuscitation=False, blender_activated=True,
                                    blender_activation_time="14:05", blender_activation_reason="Wrong baby or twin")
    out = rie.apply_to_model(data, None, "01-B-007", "nurse").model_dump(exclude_unset=True)
    assert out["randomised"] is False and out["blender_letter"] == "B"
    assert out["blender_activation_time"] == time(14, 5)


def test_stage_and_tiles():
    assert patient_stage("Eligible", "Yes", 28, 0, True, False, False, True) == "randomised_in_error"
    assert patient_stage("Eligible", "Yes", 28, 0, True, False, None, None) == "no_ppv"
    b = NS(randomised=False, required_resuscitation=False, blender_activated=True)
    assert _form_b_keys(b) == ["delivered", "randomised_in_error"]
    assert "randomised" not in _form_b_keys(b)


def test_is_in_error_on_rows_and_dicts():
    assert rie.is_in_error(saved()) and rie.is_in_error({"blender_activated": True, "required_resuscitation": False})
    assert not rie.is_in_error(saved(ppv=True)) and not rie.is_in_error(None)


def test_data_check_raises_query_for_site_pi():
    ctx = {"now": datetime(2026, 11, 11, 10, 0), "formb": [
        {"id": 1, "enrollment_id": "01-B-007", "screening_id": "01-0140", "site_name": "PGIMER",
         "blender_activated": True, "required_resuscitation": False, "blender_activation_reason": "Other",
         "blender_activation_reason_other": "pressed by mistake", "blender_activation_time": time(14, 5)},
        {"id": 2, "enrollment_id": "NR-01-0141", "screening_id": "01-0141", "site_name": "PGIMER",
         "blender_activated": False, "required_resuscitation": False},
    ]}
    found = data_checks.check_randomised_in_error(ctx)
    assert [f["record_key"] for f in found] == ["01-B-007"]
    assert "14:05" in found[0]["detail"] and "pressed by mistake" in found[0]["detail"]
    assert data_checks.CHECKS_BY_ID["RANDOMISED_IN_ERROR"].second_signoff is True


def test_email_ids_only():
    subject, html = rie._email("01-B-007", "PGIMER, Chandigarh", "Wrong baby or twin", "11-11-2026 14:05")
    assert "01-B-007" in subject and "Data queries" in html
