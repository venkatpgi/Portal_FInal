"""A possible match answered 'different woman' (PI 2026-11-26)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from birth_log_matching import checked_possible_matches
from models import DataQuery


def test_checked_states_only():
    eng = create_engine("sqlite://")
    DataQuery.__table__.create(eng)
    db = sessionmaker(bind=eng)()
    for key, status in (("676", "confirmed_correct"), ("1032", "awaiting_signoff"), ("698", "resolved"),
                        ("700", "open"), ("x", "confirmed_correct")):
        db.add(DataQuery(check_id="BIRTH_POSSIBLE_MATCH", record_type="birth_log", record_key=key, title="t",
                         status=status))
    db.add(DataQuery(check_id="OTHER", record_type="birth_log", record_key="5", title="t", status="confirmed_correct"))
    db.commit()
    assert checked_possible_matches(db) == {676: "confirmed_correct", 1032: "awaiting_signoff"}
    assert checked_possible_matches(db, {1032}) == {1032: "awaiting_signoff"}
