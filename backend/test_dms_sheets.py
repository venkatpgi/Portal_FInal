import json
from datetime import date, datetime


from dms_sheets import new_readings, open_dates, sheet_mode

DOB = date(2026, 10, 28)
MORNING = datetime(2026, 11, 3, 7, 30)
NOON = datetime(2026, 11, 3, 12, 0)


def test_open_dates_unchanged():
    assert open_dates(MORNING) == [date(2026, 11, 2), date(2026, 11, 3)]
    assert open_dates(NOON) == [date(2026, 11, 3)]


def test_earlier_sheet_is_for_corrections():
    assert sheet_mode(date(2026, 11, 2), NOON, DOB, None, [])["mode"] == "correction"
    assert sheet_mode(DOB, NOON, DOB, None, [])["mode"] == "correction"


def test_closed_sheets_give_a_reason():
    assert sheet_mode(date(2026, 10, 27), NOON, DOB, None, [])["mode"] == "closed"
    assert sheet_mode(date(2026, 11, 4), NOON, DOB, None, [])["mode"] == "closed"
    assert sheet_mode(date(2026, 11, 1), NOON, DOB, date(2026, 10, 31), [])["mode"] == "closed"
    locked = sheet_mode(date(2026, 11, 1), NOON, DOB, None, ["Helper 2"])
    assert locked["mode"] == "closed" and "Helper 2 for this day is locked" in locked["reason"]


def test_open_sheet_stays_open_even_if_a_helper_is_locked():
    assert sheet_mode(date(2026, 11, 3), NOON, DOB, None, ["Helper 5"])["mode"] == "open"


STORED = json.dumps({"cv_b": [{"id": "a", "date": "2026-11-01", "time": "10:00", "fluid_bolus_given": "Yes"}],
                     "resp_c": [{"date": "2026-11-01", "time": "09:00", "apnea_episodes": 2}]})


def test_edit_and_blank_rows_are_not_new():
    incoming = {"cv_b": [{"id": "a", "date": "2026-11-01", "time": "11:00", "fluid_bolus_given": "No"},
                         {"id": "b", "date": "2026-11-01", "time": "12:00"}],
                "resp_c": [{"date": "2026-11-01", "time": "09:00", "apnea_episodes": 2}]}
    assert new_readings(STORED, json.dumps(incoming)) == []


def test_added_reading_is_new():
    incoming = {"cv_b": [{"id": "c", "date": "2026-11-01", "time": "14:00", "fluid_bolus_given": "Yes"}]}
    assert new_readings(STORED, json.dumps(incoming)) == ["cv_b 14:00"]
    assert new_readings(None, json.dumps(incoming)) == ["cv_b 14:00"]
