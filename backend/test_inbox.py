from inbox import (AUDIENCE_NURSE, AUDIENCE_PI, AUDIENCE_SCIENTIST, audience_for,
                   death_copy, enrollment_id_of, followup_urgency, query_route)


def test_audience_by_role():
    assert audience_for("nurse") == AUDIENCE_NURSE
    assert audience_for("deo") == AUDIENCE_NURSE
    assert audience_for("site_scientist") == AUDIENCE_SCIENTIST
    assert audience_for("project_scientist") == AUDIENCE_SCIENTIST
    assert audience_for("site_pi") == AUDIENCE_PI
    assert audience_for("superadmin") == AUDIENCE_PI
    assert audience_for("tech_support") is None


def test_death_copy_is_a_verb_for_nurses():
    msg, act = death_copy(AUDIENCE_NURSE)
    assert msg.startswith("Death recorded. Complete Form Y")
    assert act == "Open Form Y"
    sci, _ = death_copy(AUDIENCE_SCIENTIST)
    assert "No Form Y report received" in sci
    pi, _ = death_copy(AUDIENCE_PI)
    assert "still outstanding" in pi


def test_followup_urgency_groups_by_when():
    assert followup_urgency(-1, "overdue") == "now"
    assert followup_urgency(0, "window") == "today"
    assert followup_urgency(2, "upcoming") == "today"
    assert followup_urgency(7, "upcoming") == "later"


def test_query_route_maps_record_types():
    assert query_route("birth_resuscitation") == "form_b1"
    assert query_route("cranial_usg") == "form_f"
    assert query_route("enrollment") == "form_h"
    assert query_route("range") == "helper_dms"
    assert query_route("ga_check") == "gestation_log"


def test_enrollment_ids_include_amc_style():
    assert enrollment_id_of("01-B-001") == "01-B-001"
    assert enrollment_id_of("06-0049") == "06-0049"
    assert enrollment_id_of("Gestation Log #12") is None


def test_items_have_no_name_fields():
    from inbox import item
    row = item(key="death:06-0124", urgency="now", kind="death_sae",
               title="06-0124", message="Death recorded. Complete Form Y within 24 hours.",
               action="Open Form Y", route="form_y", enrollment_id="06-0124", site="AMC")
    assert "name" not in row and "mother" not in row
    assert row["enrollment_id"] == "06-0124"
