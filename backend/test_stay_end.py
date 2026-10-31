from datetime import date

from stay_end import end_of_stay, refusal

DOB = date(2026, 10, 28)


def test_running_stay_has_no_end():
    assert end_of_stay(DOB, None, None, []) is None
    assert end_of_stay(DOB, None, "Died", []) is None


def test_helper_5_death_ends_the_stay_without_a_form_h_date():
    assert end_of_stay(DOB, None, None, [3]) == {"date": date(2026, 10, 30), "day": 3, "died": True}


def test_earliest_end_wins():
    assert end_of_stay(DOB, date(2026, 11, 2), "Died", [3])["day"] == 3
    assert end_of_stay(DOB, date(2026, 10, 29), "Died", [3])["day"] == 2


def test_discharge_is_an_end_but_not_a_death():
    assert end_of_stay(DOB, date(2026, 11, 2), "Discharged", []) == {"date": date(2026, 11, 2), "day": 6, "died": False}


def test_last_day_stays_open_the_next_is_refused():
    end = end_of_stay(DOB, None, "Died", [3])
    assert refusal(end, nicu_day=3) is None
    assert refusal(end, on_date="2026-10-30") is None
    assert "died on 30 Oct 2026 (Day 3)" in refusal(end, nicu_day=4)
    assert refusal(end, on_date="2026-10-31")
    assert refusal(None, nicu_day=40) is None
