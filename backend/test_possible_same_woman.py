"""FORMA_POSSIBLE_SAME_WOMAN (data_checks.py). Identities made up."""
from datetime import date, datetime
from types import SimpleNamespace

from data_checks import check_formA_possible_same_woman


def pii(sid, cr, first="Kavita", last="Kumari", site="PGIMER"):
    return SimpleNamespace(screening_id=sid, maternal_uid=cr, mother_first_name=first,
                           mother_surname=last, site_name=site)


def ctx(rows, ga=None):
    return {"pii": rows, "now": datetime(2026, 10, 17), "screening_ga": ga or {}}


def keys(found):
    return sorted(f["record_key"] for f in found)


def test_three_near_crs_all_flagged():
    rows = [pii("01-0050", "202604584608"), pii("01-0096", "202604585608"), pii("01-0101", "2026024585608")]
    ga = {"01-0050": (205, date(2026, 10, 1)), "01-0096": (206, date(2026, 10, 2)),
          "01-0101": (220, date(2026, 10, 16))}
    found = check_formA_possible_same_woman(ctx(rows, ga))
    assert keys(found) == ["01-0050", "01-0096", "01-0101"]


def test_exact_same_cr_left_to_duplicate_check():
    assert check_formA_possible_same_woman(ctx([pii("a", "202604585608"), pii("b", "202604585608")])) == []


def test_different_names_or_far_crs_or_misfit_ga_not_flagged():
    assert check_formA_possible_same_woman(ctx([pii("a", "202604585608"),
                                                pii("b", "202604585609", "Sunita", "Rani")])) == []
    assert check_formA_possible_same_woman(ctx([pii("a", "202604585608"), pii("b", "202611185600")])) == []
    ga = {"a": (205, date(2026, 10, 1)), "b": (260, date(2026, 10, 2))}
    assert check_formA_possible_same_woman(ctx([pii("a", "202604585608"), pii("b", "202604585609")], ga)) == []


def test_other_site_not_flagged():
    assert check_formA_possible_same_woman(ctx([pii("a", "202604585608"),
                                                pii("b", "202604585609", site="GMCH")])) == []
