"""Gestation Log live status (ga_log_status.py). Identities made up."""
from datetime import date

from ga_log_status import live_status, still_eligible_gap

TODAY = date(2026, 10, 14)


def entry(**kw):
    e = {"check_date": "2026-09-28", "gestation_weeks": 29, "gestation_days": 0,
         "eligible": True, "found_iufd": False, "ga_source": "Reliable",
         "mother_uid": "2026 0000 1111", "mother_name": "Asha Devi", "has_form_a": False}
    e.update(kw)
    return e


def birth(**kw):
    b = {"mother_uid": "202600001111", "mother_name": "Asha", "date_of_birth": "2026-10-10",
         "gestation_weeks": 30, "gestation_days": 5, "source": "Log of All Births"}
    b.update(kw)
    return b


def test_delivered_by_mothers_cr():
    s = live_status(entry(), [birth()], TODAY)
    assert s["live_status"] == "delivered"
    assert s["delivered_on"] == "2026-10-10" and s["delivered_source"] == "Log of All Births"
    assert not still_eligible_gap(entry(), s)


def test_form_b_counts_as_delivered():
    s = live_status(entry(), [birth(source="Form B")], TODAY)
    assert s["live_status"] == "delivered" and s["delivered_source"] == "Form B"


def test_same_name_other_cr_is_not_delivered():
    s = live_status(entry(), [birth(mother_uid="202600009999")], TODAY)
    assert s["live_status"] is None  # still pregnant, 31w2d
    assert s["current_ga_days"] == 29 * 7 + 16


def test_earlier_pregnancy_same_cr_ignored():
    s = live_status(entry(), [birth(date_of_birth="2025-01-05", gestation_weeks=38)], TODAY)
    assert s["live_status"] is None


def test_cr_match_with_impossible_ga_needs_check():
    s = live_status(entry(), [birth(gestation_weeks=38, gestation_days=0)], TODAY)
    assert s["live_status"] == "cr_check" and "GA at birth does not fit" in s["live_note"]


def test_cr_match_with_other_name_needs_check():
    s = live_status(entry(), [birth(mother_name="Kiran Kumari")], TODAY)
    assert s["live_status"] == "cr_check" and "name differs" in s["live_note"]


def test_crossed_32_weeks():
    e = entry(check_date="2026-09-01")  # 29w0d + 43 d = 35w1d
    s = live_status(e, [], TODAY)
    assert s["live_status"] == "crossed_32"
    assert not still_eligible_gap(e, s)


def test_still_eligible_stays_in_gap():
    e = entry()
    s = live_status(e, [], TODAY)
    assert s["live_status"] is None and still_eligible_gap(e, s)
    e2 = entry(has_form_a=True)
    assert not still_eligible_gap(e2, live_status(e2, [], TODAY))


def test_now_eligible_after_25_weeks():
    e = entry(check_date="2026-09-23", gestation_weeks=23, gestation_days=0, eligible=False)
    s = live_status(e, [], TODAY)  # 23w0d + 21 d = 26w0d
    assert s["live_status"] == "now_eligible" and still_eligible_gap(e, s)
    e2 = entry(check_date="2026-09-23", gestation_weeks=23, gestation_days=0, eligible=False, has_form_a=True)
    assert live_status(e2, [], TODAY)["live_status"] is None


def test_overdue_when_no_birth_found():
    e = entry(check_date="2026-08-01", gestation_weeks=36, eligible=False)
    s = live_status(e, [], TODAY)  # 36w + 74 d = 46w4d
    assert s["live_status"] == "overdue"


def test_iufd_and_unknown_ga_have_no_live_status():
    assert live_status(entry(found_iufd=True), [birth()], TODAY)["live_status"] is None
    s = live_status(entry(gestation_weeks=None, eligible=None, ga_source="Unknown/Unreliable",
                          mother_uid=""), [], TODAY)
    assert s["live_status"] is None and s["current_ga_days"] is None


def test_birth_logged_day_before_check_counts_when_ga_fits():
    e = entry(check_date="2026-10-07", gestation_weeks=31, gestation_days=4)
    s = live_status(e, [birth(date_of_birth="2026-10-06", gestation_weeks=31, gestation_days=3)], TODAY)
    assert s["live_status"] == "delivered"


def test_spelling_variant_is_not_a_name_difference():
    s = live_status(entry(mother_name="pooonam"), [birth(mother_name="Poonam Devi")], TODAY)
    assert s["live_status"] == "delivered"
