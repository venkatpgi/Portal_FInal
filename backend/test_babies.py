from types import SimpleNamespace as NS

from babies import baby_label, baby_no, nr_enrollment_id, parse_nr
from birth_log_matching import _pick_baby
from participant_counts import counts


def test_nr_ids_per_baby():
    assert nr_enrollment_id("01-0118") == "NR-01-0118"
    assert nr_enrollment_id("01-0118", 1) == "NR-01-0118"
    assert nr_enrollment_id("01-0118", 2) == "NR-01-0118-2"
    assert parse_nr("NR-01-0118") == ("01-0118", 1)
    assert parse_nr("NR-01-0118-2") == ("01-0118", 2)
    assert parse_nr("01-B-004") is None


def test_baby_number_and_label():
    assert baby_no(None) == 1 and baby_no(NS(baby_number=None)) == 1 and baby_no(NS(baby_number=3)) == 3
    assert baby_label(1, 1) == "" and baby_label(None, None) == ""
    assert baby_label(2, 2) == "Twin 2 of 2" and baby_label(1, 3) == "Triplet 1 of 3"


def _b(n, rand, first):
    return NS(required_resuscitation=True, randomised=rand, baby_number=n, first=first)


def test_twins_count_mother_once_and_each_baby():
    row = NS(screening_id="01-0118", consent_given="Yes")
    items = [(row, "Eligible", "randomised", _b(1, True, True)),
             (row, "Eligible", "randomised", _b(2, False, False))]
    c = counts(items)
    assert (c["screened"], c["eligible"], c["consented"]) == (1, 1, 1)
    assert (c["delivered"], c["needed_ppv"], c["randomised"], c["not_randomised"]) == (2, 2, 1, 1)


def test_birth_log_row_links_to_the_baby_with_its_birth_order():
    ids = {("01-0118", 1): "NR-01-0118", ("01-0118", 2): "01-B-007"}
    hit = {"matched_screening_id": "01-0118", "matched_enrollment_id": "NR-01-0118"}
    assert _pick_baby(dict(hit), 2, ids)["matched_enrollment_id"] == "01-B-007"
    assert _pick_baby(dict(hit), 1, ids)["matched_enrollment_id"] == "NR-01-0118"
    assert _pick_baby(dict(hit), 3, ids)["matched_enrollment_id"] is None   # baby 3 has no Form B yet
    assert _pick_baby(dict(hit), None, ids)["matched_enrollment_id"] == "NR-01-0118"   # birth order not set
