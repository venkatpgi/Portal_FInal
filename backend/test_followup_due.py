from datetime import date, datetime
from types import SimpleNamespace as NS

import followup_due as fd

DOB = date(2026, 10, 20)
GA = 28 * 7          # 36 wk PMA on 15 Dec, 40 wk on 12 Jan, 44 wk on 9 Feb


def form_i(**kw):
    base = {f"{k}{wk}": None for wk in fd.CHECKPOINTS
            for k in ("encounter", "death", "ltfu")}
    base = {(k + "_method" if k.startswith("encounter") else k + "_reason" if k.startswith("ltfu") else k): v
            for k, v in base.items()}
    base.update(kw)
    return NS(**base)


def test_dates_and_window():
    rows = fd.pending(DOB, GA, None, False, None, date(2026, 12, 1))
    assert [(r["checkpoint"], r["due"]) for r in rows] == [
        (36, date(2026, 12, 15)), (40, date(2027, 1, 12)), (44, date(2027, 2, 9))]
    r = rows[0]
    assert (r["window_from"], r["window_to"], r["stage"], r["days_to_due"]) == (
        date(2026, 12, 13), date(2026, 12, 17), "upcoming", 14)
    assert fd.pending(DOB, GA, None, False, None, date(2026, 12, 13))[0]["stage"] == "window"
    assert fd.pending(DOB, GA, None, False, None, date(2026, 12, 17))[0]["stage"] == "window"
    assert fd.pending(DOB, GA, None, False, None, date(2026, 12, 18))[0]["stage"] == "overdue"


def test_done_died_lost_withdrawn():
    today = date(2026, 12, 20)
    assert [r["checkpoint"] for r in fd.pending(DOB, GA, form_i(encounter36_method="Telephonic"), False, None, today)] \
        == [40, 44]
    assert [r["checkpoint"] for r in fd.pending(DOB, GA, form_i(ltfu36_reason="Family relocated / moved away"),
                                                 False, None, today)] == [40, 44]
    assert fd.pending(DOB, GA, form_i(ltfu36_reason=fd.WITHDRAWN), False, None, today) == []
    assert fd.pending(DOB, GA, form_i(death36=True), False, None, today) == []
    # died at home after 36 wk: 36 still to enter, nothing after
    assert [r["checkpoint"] for r in fd.pending(DOB, GA, None, True, date(2026, 12, 25), today)] == [36]
    assert fd.pending(DOB, None, None, False, None, today) == []


def test_lead_time_home_14_nicu_7():
    row = fd.pending(DOB, GA, None, False, None, date(2026, 12, 1))[0]      # 14 days to go
    assert fd.is_coming_up(row, home=True) and not fd.is_coming_up(row, home=False)
    row = fd.pending(DOB, GA, None, False, None, date(2026, 12, 8))[0]      # 7 days to go
    assert fd.is_coming_up(row, home=False)
    row = fd.pending(DOB, GA, None, False, None, date(2026, 11, 30))[0]     # 15 days
    assert not fd.is_coming_up(row, home=True)
    assert fd.when_text(fd.pending(DOB, GA, None, False, None, date(2026, 12, 16))[0]) == "1 day ago, window open"


def _row(eid, wk, days, home=True, site="PGIMER"):
    due = date(2026, 12, 15)
    today = date.fromordinal(due.toordinal() - days)
    r = fd.pending(DOB, GA, None, False, None, today)[0]
    return {"site": site, "enrollment_id": eid, "home": home, "ended_on": date(2026, 11, 30),
            "where": "Discharged 30 Nov 2026", **dict(r, checkpoint=wk)}


def test_email_once_per_checkpoint_home_only(monkeypatch):
    import audit_service
    import daily_query_email
    import email_service
    monkeypatch.setenv("SES_SENDER_EMAIL", "x@example.org")
    rows = [_row("01-B-001", 36, 7), _row("01-B-002", 36, 10), _row("01-B-003", 36, 3, home=False),
            _row("01-B-004", 36, 5)]
    monkeypatch.setattr(fd, "collect", lambda db, sites, today: rows)
    monkeypatch.setattr(daily_query_email, "recipients", lambda db: {"PGIMER": ["pi@example.org"]})
    sent, audits = [], []
    monkeypatch.setattr(email_service, "send_email", lambda to, subj, html: sent.append((to, subj, html)) or True)
    monkeypatch.setattr(audit_service, "record_audit", lambda db, **kw: audits.append(kw))
    already = [NS(enrollment_id="01-B-004", new_values={"checkpoint": 36})]

    class Q:
        def filter(self, *a):
            return self

        def __iter__(self):
            return iter(already)

    db = NS(query=lambda *a: Q())
    assert fd.send_reminders(db, now=datetime(2026, 12, 8, 4, 0)) == 1          # 09:30 IST
    (to, subject, html), = sent
    assert to == ["pi@example.org"] and "1 baby at home" in subject
    assert "01-B-001" in html and "01-B-002" not in html and "01-B-003" not in html and "01-B-004" not in html
    assert [a["enrollment_id"] for a in audits] == ["01-B-001"]
    assert audits[0]["new_values"]["checkpoint"] == 36
    sent.clear()
    assert fd.send_reminders(db, now=datetime(2026, 12, 8, 16, 0)) == 0         # 21:30 IST: wait
    assert sent == []


def test_no_email_on_training(monkeypatch):
    monkeypatch.delenv("SES_SENDER_EMAIL", raising=False)
    assert fd.send_reminders(None, now=datetime(2026, 12, 8, 4, 0)) == 0


def test_ready_report_sections(monkeypatch):
    import ready_reports
    rows = [_row("01-B-001", 36, 7), _row("01-B-002", 36, 20), _row("01-B-003", 36, -5, home=False)]
    monkeypatch.setattr(fd, "collect", lambda db, sites, today: rows)
    up, late = ready_reports.followup_due_report(None, ["PGIMER"], today=date(2026, 12, 8))
    assert [r[0] for r in up["rows"]] == ["01-B-001"] and up["title"] == "Coming up (1)"
    assert [r[0] for r in late["rows"]] == ["01-B-003"] and late["rows"][0][3] == "15-12-2026"
    assert "followup_due" in ready_reports.REPORT_KEYS
