from datetime import date

from ga_log_link import orphan_counts, pick_log_entry, pick_screening

CR = "2026 0000 0717"
LOG = [
    {"id": 370, "site_name": "PGIMER", "mother_uid": "202600005601", "screening_id": None, "check_date": date(2026, 10, 20)},
    {"id": 374, "site_name": "PGIMER", "mother_uid": "202600000717", "screening_id": None, "check_date": date(2026, 10, 20)},
    {"id": 300, "site_name": "PGIMER", "mother_uid": "2026-0000-0717", "screening_id": None, "check_date": date(2026, 10, 15)},
    {"id": 375, "site_name": "AMC", "mother_uid": "202600000717", "screening_id": None, "check_date": date(2026, 10, 21)},
]


def test_log_entry_same_site_same_cr_most_recent():
    assert pick_log_entry(LOG, "PGIMER", CR) == 374


def test_log_entry_ignores_linked_other_site_and_blank_cr():
    linked = [dict(e, screening_id="01-0001") if e["id"] in (374, 300) else e for e in LOG]
    assert pick_log_entry(linked, "PGIMER", CR) is None
    assert pick_log_entry(LOG, "PGIMER", "") is None
    assert pick_log_entry(LOG, "GMCH", CR) is None


SCR = [
    {"screening_id": "01-0104", "site_name": "PGIMER", "maternal_uid": "202600000717", "created_at": "2026-10-20T03:32"},
    {"screening_id": "01-0090", "site_name": "PGIMER", "maternal_uid": "202600000717", "created_at": "2026-10-10T03:32"},
    {"screening_id": "06-0001", "site_name": "AMC", "maternal_uid": "202600000717", "created_at": "2026-10-21T03:32"},
]


def test_screening_most_recent_unlinked_same_site():
    assert pick_screening(SCR, "PGIMER", CR, set()) == "01-0104"
    assert pick_screening(SCR, "PGIMER", CR, {"01-0104"}) == "01-0090"
    assert pick_screening(SCR, "PGIMER", CR, {"01-0104", "01-0090"}) is None
    assert pick_screening(SCR, "PGIMER", None, set()) is None


def test_orphans_cr_match_covers_once():
    screenings = [{"screening_id": "01-0104", "site_name": "PGIMER", "maternal_uid": "202600000717"},
                  {"screening_id": "01-0103", "site_name": "PGIMER", "maternal_uid": "202600009999"},
                  {"screening_id": "01-0072", "site_name": "PGIMER", "maternal_uid": "202600001111"},
                  {"screening_id": "01-0093", "site_name": "PGIMER", "maternal_uid": "202600001111"}]
    entries = [{"id": 374, "site_name": "PGIMER", "mother_uid": "202600000717", "screening_id": None},
               {"id": 287, "site_name": "PGIMER", "mother_uid": "202600001111", "screening_id": "01-0072"}]
    # 0104 covered by #374 (CR); 0072 linked; 0103 no entry; 0093 shares a CR
    # with #287, which already covers 0072 -> orphan, so Box 1 >= Box 3.
    assert orphan_counts(screenings, entries) == {"PGIMER": 2}


def test_orphans_entry_linked_to_deleted_form_a_can_cover():
    screenings = [{"screening_id": "01-0025", "site_name": "PGIMER", "maternal_uid": "X1"}]
    entries = [{"id": 59, "site_name": "PGIMER", "mother_uid": "X1", "screening_id": "01-0029"}]
    assert orphan_counts(screenings, entries) == {}
