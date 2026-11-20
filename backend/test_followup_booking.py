"""Follow-up calendar on Form H (followup_booking.py). In-memory SQLite for the
bookings; babies are faked (no live data). Emails are mocked."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import data_checks as dc
import followup_booking as fb
import followup_due as fd
from models import FollowupBooking

DOB = date(2026, 10, 20)
GA = 28 * 7          # 36 wk PMA 15 Dec 2026, 40 wk 12 Jan 2027, 44 wk 9 Feb 2027
EID = "01-B-001"


def form_i(**kw):
    base = {}
    for wk in fd.CHECKPOINTS:
        base.update({f"encounter{wk}_method": None, f"death{wk}": None, f"ltfu{wk}_reason": None})
    base.update(kw)
    return NS(**base)


def baby(outcome="Discharged", left=date(2026, 12, 14), so=None, died=False):
    return {"site": "PGIMER", "enrollment_id": EID, "dob": DOB, "ga_days": GA,
            "form_h": NS(outcome=outcome, discharge_date=left), "form_i": so or form_i(), "end": None,
            "died": died, "death_date": None, "home": not died, "where": "Discharged"}


@pytest.fixture
def db(monkeypatch):
    eng = create_engine("sqlite://")
    FollowupBooking.__table__.create(eng)
    s = sessionmaker(bind=eng)()
    state = {"baby": baby()}
    monkeypatch.setattr(fd, "babies", lambda db, sites, eids=None: [state["baby"]])
    s.info["state"] = state
    return s


TODAY = date(2026, 12, 14)


def test_states_and_allowed_dates(db):
    cal = fb.calendar(db, EID, TODAY)
    assert cal["applies"] and [r["state"] for r in cal["rows"]] == ["bookable"] * 3
    r36 = cal["rows"][0]
    # left 14 Dec, inside the 36 wk window 13-17 Dec: from the day it left
    assert (r36["earliest"], r36["latest"]) == (date(2026, 12, 14), date(2026, 12, 17))
    assert cal["rows"][1]["earliest"] == date(2027, 1, 10) and cal["complete"] is False

    db.info["state"]["baby"] = baby(left=date(2026, 12, 17), so=form_i(encounter40_method="Direct"))
    states = [r["state"] for r in fb.calendar(db, EID, TODAY)["rows"]]
    assert states == ["in_nicu", "done", "bookable"]   # window closed the day it left: assess in the NICU


def test_not_shown_for_death_or_no_form_h(db):
    db.info["state"]["baby"] = baby(outcome="Died")
    cal = fb.calendar(db, EID, TODAY)
    assert cal["applies"] is False and cal["rows"] == []
    db.info["state"]["baby"] = dict(baby(), form_h=None)
    assert fb.calendar(db, EID, TODAY)["applies"] is False
    for outcome in fb.ALIVE_OUTCOMES:
        db.info["state"]["baby"] = baby(outcome=outcome)
        assert fb.calendar(db, EID, TODAY)["applies"] is True


def test_withdrawn_or_died_after_discharge_ends_list(db):
    db.info["state"]["baby"] = baby(so=form_i(ltfu36_reason=fd.WITHDRAWN))
    assert {r["state"] for r in fb.calendar(db, EID, TODAY)["rows"]} == {"ended"}


def test_save_refuses_bad_entries(db):
    bad = [
        ({"checkpoint": 36, "booked_date": "2026-12-13", "mode": "Clinic visit"}, "book a date from 14 Dec"),
        ({"checkpoint": 36, "booked_date": "2026-12-18", "mode": "Clinic visit"}, "to 17 Dec"),
        ({"checkpoint": 36, "booked_date": "2026-12-15"}, "Clinic visit or Telephone"),
        ({"checkpoint": 36, "not_booked_reason": "Because"}, "choose a reason"),
        ({"checkpoint": 36, "not_booked_reason": "Other"}, "type the reason"),
        ({"checkpoint": 32, "booked_date": "2026-12-15", "mode": "Telephone"}, "nothing to book"),
    ]
    for item, msg in bad:
        with pytest.raises(fb.BookingError, match=msg):
            fb.save(db, EID, [item], "nurse1", TODAY)
    assert db.query(FollowupBooking).count() == 0


def test_save_complete_and_clear(db):
    cal = fb.save(db, EID, [
        {"checkpoint": 36, "booked_date": "2026-12-16", "mode": "Clinic visit", "not_booked_reason": "Other"},
        {"checkpoint": 40, "booked_date": "2027-01-12", "mode": "Telephone"},
        {"checkpoint": 44, "not_booked_reason": "Other", "not_booked_other": "Mother to call after travel"},
    ], "nurse1", TODAY)
    assert cal["complete"] is True
    r36, _, r44 = cal["rows"]
    assert r36["booked_date"] == date(2026, 12, 16) and r36["not_booked_reason"] is None   # date wins
    assert fb.booking_text(db.query(FollowupBooking).filter_by(checkpoint=44).one()) == \
        "Not booked: Mother to call after travel"
    cal = fb.save(db, EID, [{"checkpoint": 44}], "nurse1", TODAY)       # blank clears
    assert cal["complete"] is False and db.query(FollowupBooking).count() == 2
    assert db.query(FollowupBooking).filter_by(checkpoint=36).one().booked_by == "nurse1"


def test_corrected_discharge_date_flags_booking(db):
    fb.save(db, EID, [{"checkpoint": 36, "booked_date": "2026-12-14", "mode": "Clinic visit"}], "n", TODAY)
    db.info["state"]["baby"] = baby(left=date(2026, 12, 15))
    r36 = fb.calendar(db, EID, TODAY)["rows"][0]
    assert r36["problem"].startswith("booked 14 Dec 2026 is outside 15 Dec 2026")


# ------------------------------------------------------------------ data queries
def _cal(db, today):
    c = fb.calendar(db, EID, today)
    return {"site": "PGIMER", "enrollment_id": EID, "left_on": c["left_on"], "outcome": c["outcome"],
            "rows": c["rows"]}


def test_queries(db):
    ctx = {"now": datetime(2026, 12, 15, 6), "today": TODAY, "followup_cal": [_cal(db, TODAY)]}
    (q,) = dc.check_followup_not_booked(ctx)
    assert q["record_key"] == EID and q["facts"] == {"checkpoints": [36, 40, 44]}
    assert "Discharged 14 Dec 2026" in q["detail"]
    assert dc.CHECKS_BY_ID["FOLLOWUP_NOT_BOOKED"].raise_after == timedelta(hours=24)

    fb.save(db, EID, [{"checkpoint": 36, "booked_date": "2026-12-15", "mode": "Clinic visit"},
                      {"checkpoint": 40, "not_booked_reason": fb.REASONS[0]},
                      {"checkpoint": 44, "not_booked_reason": fb.REASONS[0]}], "n", TODAY)
    later = date(2026, 12, 16)
    ctx = {"now": datetime(2026, 12, 16, 6), "today": later, "followup_cal": [_cal(db, later)]}
    assert dc.check_followup_not_booked(ctx) == []
    (m,) = dc.check_followup_booked_missed(ctx)
    assert m["record_key"] == f"{EID}/followup/36" and "Window to 17 Dec 2026" in m["detail"]
    ctx["today"] = date(2026, 12, 15)
    ctx["followup_cal"] = [_cal(db, ctx["today"])]
    assert dc.check_followup_booked_missed(ctx) == []                    # booked day itself: not yet missed

    db.info["state"]["baby"] = baby(left=date(2026, 12, 16), so=form_i())
    ctx["followup_cal"] = [_cal(db, later)]
    (o,) = dc.check_followup_booking_outside(ctx)
    assert o["record_key"] == f"{EID}/followup-window/36"


# ------------------------------------------------------------------ emails
class FakeAudit:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *a):
        return self

    def __iter__(self):
        return iter(self.rows)


def _mail_setup(monkeypatch, db, today, already=()):
    import audit_service
    import daily_query_email
    import email_service
    monkeypatch.setenv("SES_SENDER_EMAIL", "x@example.org")
    cals = [_cal(db, today)]
    monkeypatch.setattr(fb, "all_calendars", lambda db_, sites, t: cals)
    monkeypatch.setattr(daily_query_email, "recipients", lambda db_: {"PGIMER": ["pi@example.org", "sci@example.org"]})
    sent, audits = [], []
    monkeypatch.setattr(email_service, "send_email", lambda to, subj, html: sent.append((to, subj, html)) or True)
    monkeypatch.setattr(audit_service, "record_audit", lambda db_, **kw: audits.append(kw))
    fake_db = NS(query=lambda *a: FakeAudit(list(already)))
    return fake_db, sent, audits


def _book_all(db):
    fb.save(db, EID, [{"checkpoint": 36, "booked_date": "2026-12-16", "mode": "Clinic visit"},
                      {"checkpoint": 40, "booked_date": "2027-01-12", "mode": "Telephone"},
                      {"checkpoint": 44, "not_booked_reason": fb.REASONS[1]}], "n", TODAY)


def test_booked_notice_once_per_version(monkeypatch, db):
    fake, sent, audits = _mail_setup(monkeypatch, db, TODAY)
    assert fb.send_emails(fake, now=datetime(2026, 12, 14, 20, 0)) == {}          # not complete: nothing
    _book_all(db)
    fake, sent, audits = _mail_setup(monkeypatch, db, TODAY)
    counts = fb.send_emails(fake, now=datetime(2026, 12, 14, 20, 0))              # 01:30 IST: notice still goes
    assert counts == {fb.NOTICE_TABLE: 1}
    (to, subject, html), = sent
    assert to == ["pi@example.org", "sci@example.org"] and EID in subject
    assert "16 Dec 2026" in html and "Telephone" in html and "Back-referral hospital" in html
    sig = audits[0]["new_values"]["key"]
    fake, sent, _ = _mail_setup(monkeypatch, db, TODAY,
                                already=[NS(table_name=fb.NOTICE_TABLE, enrollment_id=EID,
                                            new_values={"checkpoint": None, "key": sig})])
    assert fb.send_emails(fake, now=datetime(2026, 12, 14, 20, 0)) == {} and sent == []
    fb.save(db, EID, [{"checkpoint": 40, "booked_date": "2027-01-11", "mode": "Telephone"}], "n", TODAY)
    fake, sent, _ = _mail_setup(monkeypatch, db, TODAY,
                                already=[NS(table_name=fb.NOTICE_TABLE, enrollment_id=EID,
                                            new_values={"checkpoint": None, "key": sig})])
    assert fb.send_emails(fake, now=datetime(2026, 12, 14, 20, 0)) == {fb.NOTICE_TABLE: 1}   # changed: again


def test_reminder_two_days_before_and_missed(monkeypatch, db):
    _book_all(db)
    seen = NS(table_name=fb.NOTICE_TABLE, enrollment_id=EID,
              new_values={"checkpoint": None, "key": fb._signature(_cal(db, TODAY)["rows"])})
    fake, sent, audits = _mail_setup(monkeypatch, db, TODAY, already=[seen])
    assert fb.send_emails(fake, now=datetime(2026, 12, 14, 4, 0)) == {fb.REMIND_TABLE: 1}  # 16 Dec in 2 days
    assert "in 2 days" in sent[0][1] and audits[0]["new_values"] == {
        "checkpoint": 36, "key": "2026-12-16", "recipients": 2}
    done = NS(table_name=fb.REMIND_TABLE, enrollment_id=EID, new_values={"checkpoint": 36, "key": "2026-12-16"})
    fake, sent, _ = _mail_setup(monkeypatch, db, TODAY, already=[seen, done])
    assert fb.send_emails(fake, now=datetime(2026, 12, 15, 4, 0)) == {}
    day_after = date(2026, 12, 17)
    fake, sent, _ = _mail_setup(monkeypatch, db, day_after, already=[seen, done])
    assert fb.send_emails(fake, now=datetime(2026, 12, 17, 16, 0)) == {}                   # 21:30 IST: wait
    assert fb.send_emails(fake, now=datetime(2026, 12, 17, 4, 0)) == {fb.MISSED_TABLE: 1}
    assert "missed" in sent[0][1]


def test_no_email_on_training(monkeypatch):
    monkeypatch.delenv("SES_SENDER_EMAIL", raising=False)
    assert fb.send_emails(None, now=datetime(2026, 12, 14, 4, 0)) == {}


def test_seven_day_reminder_skips_booked(monkeypatch):
    import audit_service
    import daily_query_email
    import email_service
    monkeypatch.setenv("SES_SENDER_EMAIL", "x@example.org")
    r = fd.pending(DOB, GA, None, False, None, date(2026, 12, 8))[0]
    rows = [{"site": "PGIMER", "enrollment_id": e, "home": True, "ended_on": None, "where": "Discharged",
             "booked_date": b, **r} for e, b in (("01-B-001", None), ("01-B-002", date(2026, 12, 15)))]
    monkeypatch.setattr(fd, "collect", lambda db, sites, today: rows)
    monkeypatch.setattr(daily_query_email, "recipients", lambda db: {"PGIMER": ["pi@example.org"]})
    sent = []
    monkeypatch.setattr(email_service, "send_email", lambda to, subj, html: sent.append(html) or True)
    monkeypatch.setattr(audit_service, "record_audit", lambda db, **kw: None)
    assert fd.send_reminders(NS(query=lambda *a: FakeAudit([])), now=datetime(2026, 12, 8, 4, 0)) == 1
    assert "01-B-001" in sent[0] and "01-B-002" not in sent[0]


def test_parent_slip_pdf(db):
    _book_all(db)
    cal = fb.calendar(db, EID, TODAY)
    pdf = fb.slip_pdf(cal, NS(place="Follow-up clinic, Level 2", days_times="Mon 9-1", phone="0172 000000"),
                      "Baby of Test", "PGIMER Chandigarh")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert fb.slip_pdf(cal, None, None, "PGIMER").startswith(b"%PDF")        # no clinic details, no name
