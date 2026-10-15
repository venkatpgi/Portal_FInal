"""run_checks lifecycle: open -> resolved -> reopened; confirmed correct stays
closed unless its facts change; timeliness raised only once late enough.
Uses an in-memory SQLite table and fake checks (no live data)."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import data_checks as d
from models import DataQuery

NOW = datetime(2026, 10, 15, 12, 0)


def make_db():
    eng = create_engine("sqlite://")
    DataQuery.__table__.create(eng)
    return sessionmaker(bind=eng)()


def run(db, findings, monkeypatch, raise_after=timedelta(0), now=NOW):
    check = d.Check("FAKE", "Test", "fake", lambda ctx: list(findings), raise_after=raise_after)
    monkeypatch.setattr(d, "CHECKS", [check])
    monkeypatch.setattr(d, "_context", lambda db, now, today: {})
    return d.run_checks(db, now=now, today=now.date())


def f(key, facts=None, due=NOW):
    return d.finding("PGIMER", "enrollment", key, "t", "detail", facts or {"x": 1}, due)


def test_lifecycle(monkeypatch):
    db = make_db()
    assert run(db, [f("A")], monkeypatch)["opened"] == 1
    assert run(db, [], monkeypatch)["resolved"] == 1
    assert db.query(DataQuery).one().status == "resolved"
    assert run(db, [f("A")], monkeypatch)["reopened"] == 1
    q = db.query(DataQuery).one()
    assert q.status == "open" and q.reopened_count == 1


def test_confirmed_correct_stays_closed_until_facts_change(monkeypatch):
    db = make_db()
    run(db, [f("A", {"x": 1})], monkeypatch)
    q = db.query(DataQuery).one()
    q.status = "confirmed_correct"; db.commit()
    run(db, [f("A", {"x": 1})], monkeypatch)
    assert db.query(DataQuery).one().status == "confirmed_correct"
    run(db, [f("A", {"x": 2})], monkeypatch)
    assert db.query(DataQuery).one().status == "open"


def test_duplicate_findings_one_query(monkeypatch):
    db = make_db()
    run(db, [f("A"), f("A")], monkeypatch)
    assert db.query(DataQuery).count() == 1


def test_timeliness_waits_72h_and_colour(monkeypatch):
    db = make_db()
    due = NOW - timedelta(hours=10)
    assert run(db, [f("B", due=due)], monkeypatch, raise_after=d.AMBER_AFTER).get("opened", 0) == 0
    late = NOW - timedelta(days=4)
    run(db, [f("B", due=late)], monkeypatch, raise_after=d.AMBER_AFTER)
    q = db.query(DataQuery).one()
    assert d.colour(q, NOW) == "amber"
    assert d.colour(q, NOW + timedelta(days=4)) == "red"
