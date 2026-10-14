"""Log of All Births -> Form A matching (birth_log_matching.match_against).

Cases mirror the false name-only links found in live data on 2026-10-14
(identities made up)."""
from datetime import date, datetime
from types import SimpleNamespace

from birth_log_matching import ga_consistent, match_against


def cand(sid, uid, name, ga_w, ga_d, form_date, eid=None):
    return {"screening_id": sid, "enrollment_id": eid, "uid": uid, "name": name,
            "ga_weeks": ga_w, "ga_days": ga_d, "form_date": datetime.fromisoformat(form_date)}


def ga(uid, name):
    return SimpleNamespace(mother_uid=uid, mother_name=name)


def test_cr_match_is_matched():
    m = match_against([cand("01-0001", "202600000001", "asha devi", 30, 0, "2026-10-01")],
                      "2026-0000-0001", "Someone Else", 31, 0, date(2026, 10, 8))
    assert m["match_status"] == "matched"
    assert m["matched_screening_id"] == "01-0001"


def test_same_name_consistent_ga_is_only_possible():
    # 29w3d on 25 Sep -> about 31w4d on 10 Oct; born at 32w3d: fits.
    m = match_against([cand("01-0022", "202600000815", "mandeep kaur", 29, 3, "2026-09-25")],
                      "202600005217", "Mandeep Kaur", 32, 3, date(2026, 10, 10))
    assert m["match_status"] == "possible_match"
    assert m["matched_screening_id"] == "01-0022"


def test_same_name_impossible_ga_is_not_linked():
    # 27w1d on 29 Sep -> about 29w1d on 13 Oct; born at 36w: a different woman.
    m = match_against([cand("01-0041", "202600008996", "rimpy", 27, 1, "2026-09-29")],
                      "202600004964", "Rimpy", 36, 0, date(2026, 10, 13))
    assert m["match_status"] == "out_of_range"
    assert m["matched_screening_id"] is None


def test_birth_before_form_a_at_term_is_not_linked():
    # Form A 30w3d on 29 Sep; a same-name birth on 27 Sep at 38w3d cannot be her.
    m = match_against([cand("01-0039", "202100000001", "sunita", 30, 3, "2026-09-29")],
                      "202600009999", "Sunita", 38, 3, date(2026, 9, 27))
    assert m["matched_screening_id"] is None


def test_in_range_birth_with_no_plausible_form_a_is_alert():
    m = match_against([cand("01-0063", "202600005013", "meenakshi", 25, 3, "2026-10-05")],
                      "202600005626", "Meenakshi", 29, 1, date(2026, 10, 5))
    assert m["match_status"] == "in_range_no_match"
    assert m["matched_screening_id"] is None


def test_picks_the_consistent_one_among_same_names():
    cands = [cand("01-0056", "1", "neha", 30, 4, "2026-10-02"),
             cand("01-0062", "2", "neha", 25, 2, "2026-10-04")]
    # born 20 Oct at 27w3d: fits 01-0062 (25w2d + 16d = 27w4d), not 01-0056.
    m = match_against(cands, "3", "Neha", 27, 3, date(2026, 10, 20))
    assert m["match_status"] == "possible_match"
    assert m["matched_screening_id"] == "01-0062"


def test_unknown_ga_still_offers_possible():
    m = match_against([cand("01-0005", "1", "kiran", None, None, "2026-10-01")],
                      "2", "Kiran", 30, 0, date(2026, 10, 9))
    assert m["match_status"] == "possible_match"


def test_ga_log_missing_flag():
    c = [cand("01-0001", "202600000001", "asha", 30, 0, "2026-10-01")]
    hit = match_against(c, "202600000001", "Asha", 31, 0, date(2026, 10, 8),
                        ga_rows=[ga("2026 0000 0001", "x")])
    miss = match_against(c, "202600000001", "Asha", 31, 0, date(2026, 10, 8), ga_rows=[])
    assert hit["ga_log_missing"] is False
    assert miss["ga_log_missing"] is True
    term = match_against([], "9", "Nobody", 39, 0, date(2026, 10, 8), ga_rows=[])
    assert term["match_status"] == "out_of_range" and term["ga_log_missing"] is None


def test_ga_consistent_edges():
    assert ga_consistent(30, 0, "2026-10-01", 32, 0, "2026-10-15") is True
    assert ga_consistent(30, 0, "2026-10-01", 34, 1, "2026-10-01") is False
    assert ga_consistent(None, 0, "2026-10-01", 32, 0, "2026-10-15") is None
    assert ga_consistent(30, 0, None, 32, 0, "2026-10-15") is None
