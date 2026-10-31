from datetime import date

import json

from stay_end import end_of_stay, entries_after_death, is_blank_helper_day, refusal

DOB = date(2026, 10, 28)


def test_running_stay_has_no_end():
    assert end_of_stay(DOB, None, None, []) is None
    assert end_of_stay(DOB, None, "Died", []) is None


def test_helper_5_death_ends_the_stay_without_a_form_h_date():
    assert end_of_stay(DOB, None, None, [3]) == {"date": date(2026, 10, 30), "day": 3, "died": True, "time": None}


def test_earliest_end_wins():
    assert end_of_stay(DOB, date(2026, 11, 2), "Died", [3])["day"] == 3
    assert end_of_stay(DOB, date(2026, 10, 29), "Died", [3])["day"] == 2


def test_discharge_is_an_end_but_not_a_death():
    assert end_of_stay(DOB, date(2026, 11, 2), "Discharged", []) == {"date": date(2026, 11, 2), "day": 6, "died": False, "time": None}


def test_last_day_stays_open_the_next_is_refused():
    end = end_of_stay(DOB, None, "Died", [3])
    assert refusal(end, nicu_day=3) is None
    assert refusal(end, on_date="2026-10-30") is None
    assert "died on 30 Oct 2026 (Day 3)" in refusal(end, nicu_day=4)
    assert refusal(end, on_date="2026-10-31")
    assert refusal(None, nicu_day=40) is None


def test_time_of_death_is_kept_only_with_its_date():
    assert end_of_stay(DOB, date(2026, 10, 30), "Died", [], "14:00")["time"] == "14:00"
    assert end_of_stay(DOB, date(2026, 11, 2), "Died", [3], "14:00")["time"] is None


END = end_of_stay(DOB, date(2026, 10, 30), "Died", [], "14:00")


def sheet(*rows):
    return json.dumps({"cv_a": list(rows)})


def test_new_reading_after_death_is_refused_blank_rows_and_old_readings_are_not():
    late = {"id": "a", "time": "15:30", "sbp": 40}
    assert entries_after_death(END, "2026-10-30", sheet(late)) == ["15:30"]
    assert entries_after_death(END, "2026-10-30", sheet({"id": "a", "time": "13:59", "sbp": 40})) == []
    assert entries_after_death(END, "2026-10-30", sheet({"id": "b", "time": "15:30", "sbp": ""})) == []
    assert entries_after_death(END, "2026-10-30", sheet(late), sheet(late)) == []
    assert entries_after_death(END, "2026-10-29", sheet(late)) == []


def test_blank_helper_day():
    assert is_blank_helper_day({"enrollment_id": "x", "nicu_day": 4, "submission_status": "draft", "weight": None})
    assert is_blank_helper_day({"ph_readings_json": '[{"id":"1","date":"d","time":"t","ph":""}]'})
    assert not is_blank_helper_day({"survived_the_day": False})
    assert not is_blank_helper_day({"ph_readings_json": '[{"id":"1","ph":"7.3"}]'})
    assert not is_blank_helper_day({"map_cpap": 8})
