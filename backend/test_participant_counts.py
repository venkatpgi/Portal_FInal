from types import SimpleNamespace as NS

from participant_counts import COUNT_KEYS, counts, members, tile_keys


def b(ppv, rand):
    return NS(required_resuscitation=ppv, randomised=rand)


def row(sid, consent="Yes"):
    return NS(screening_id=sid, consent_given=consent)


ITEMS = [
    (row("01-0001"), "Eligible", "randomised", b(True, True)),
    (row("01-0002"), "Eligible", "not_randomised", b(True, False)),
    (row("01-0003"), "Eligible", "no_ppv", b(False, None)),
    (row("01-0004"), "Eligible", "awaiting_delivery", None),
    (row("01-0005"), "Eligible", "discharged_undelivered", None),
    (row("01-0006", "No"), "Not Eligible", "consent_refused", None),
    (row("01-0007", None), "Screen Failure", "excluded", None),
    (row("01-0008", None), "Pending", "consent_pending", None),
]


def test_screening_tiles_add_up_to_screened():
    c = counts(ITEMS)
    assert c["screened"] == 8
    assert c["eligible"] + c["not_eligible"] + c["screen_failures"] + c["pending"] == c["screened"]
    assert c["consented"] == 5


def test_delivery_and_randomisation_tiles():
    c = counts(ITEMS)
    assert (c["delivered"], c["needed_ppv"], c["randomised"], c["not_randomised"], c["no_ppv"]) == (3, 2, 1, 1, 1)
    assert c["awaiting_delivery"] == 2


def test_randomised_counts_as_needed_ppv_even_if_ppv_blank():
    assert "needed_ppv" in tile_keys("Eligible", "Yes", "randomised", b(None, True))


def test_members_match_counts():
    m = members(ITEMS)
    assert set(m) == set(COUNT_KEYS)
    assert m["randomised"] == ["01-0001"]
