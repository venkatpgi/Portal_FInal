from datetime import datetime

from enrolment_status import message_of, window_of


def test_window_is_the_last_finished_eight_to_eight():
    night = (datetime(2026, 10, 30, 20), datetime(2026, 10, 31, 8))
    day = (datetime(2026, 10, 31, 8), datetime(2026, 10, 31, 20))
    assert window_of(datetime(2026, 10, 31, 8, 15)) == night
    assert window_of(datetime(2026, 10, 31, 8, 0)) == night
    assert window_of(datetime(2026, 10, 31, 19, 59)) == night
    assert window_of(datetime(2026, 10, 31, 20, 5)) == day
    assert window_of(datetime(2026, 11, 1, 7, 59)) == day


def test_message_follows_the_nurses_template():
    counts = dict(screened=3, eligible=2, consented=1, refused=0, not_approached=1, randomised=12)
    text = message_of("PGIMER", datetime(2026, 10, 30, 20), counts)
    assert text.splitlines()[:3] == ["Good morning", "PORTAL Trial: PGIMER", "Data from 30/10/26 (8pm-8am)"]
    assert "1. No. of files screened, 25 weeks and above - 03" in text
    assert text.endswith("6. No. randomised (babies) - 12")
    assert message_of("PGIMER", datetime(2026, 10, 31, 8), counts, True).startswith("TRAINING SITE")
    assert "(8am-8pm)" in message_of("PGIMER", datetime(2026, 10, 31, 8), counts)
