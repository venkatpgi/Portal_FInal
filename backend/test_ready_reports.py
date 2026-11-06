from datetime import datetime
from types import SimpleNamespace as NS

import ready_reports as rr


def woman(sid, site="PGIMER", consent=None, by=None, reason=None, rel="Mother", ga=(28, 0), excl=None):
    return NS(screening_id=sid, site_name=site, consent_given=consent, consent_taken_by=by,
              reason_for_consent_refusal=reason, reason_for_consent_refusal_other=None,
              relationship_to_participant=rel, relationship_other=None,
              consent_datetime=datetime(2026, 11, 1, 10, 0), screening_datetime=datetime(2026, 11, 1, 9, 0),
              created_at=datetime(2026, 11, 1, 9, 0),
              gestation_weeks=ga[0] if ga else None, gestation_days=ga[1] if ga else None,
              exclusion_present=bool(excl), exclusion_reasons=excl)


def test_consent_refusals_by_staff_and_reason():
    rows = [woman("01-1", consent="No", by="Asha", reason="Family pressure, Other"),
            woman("01-2", consent="Yes", by="Asha"),
            woman("01-3", consent="No", by="Bina", reason="Fear of adverse effects"),
            woman("01-4", consent=None)]
    secs = rr.consent_report(rows, ["PGIMER"])
    assert secs[0]["rows"] == [["PGIMER", 3, 2, "66.7%"]] or secs[0]["rows"][0][1:] == [3, 2, "66.7%"]
    staff = {r[1]: r[2:] for r in secs[1]["rows"]}
    assert staff["Asha"] == [2, 1, "50.0%"] and staff["Bina"] == [1, 1, "100.0%"]
    reasons = {r[0]: r[1] for r in secs[2]["rows"]}
    assert reasons == {"Family pressure": 1, "Other": 1, "Fear of adverse effects": 1}
    assert len(secs[4]["rows"]) == 2


def test_exclusions_match_consort_boxes_4a_4b():
    assert rr.exclusion_reasons(woman("a", ga=(24, 6))) == ["Gestation outside 25+0 to 31+6 weeks"]
    assert rr.exclusion_reasons(woman("b", ga=None)) == ["Gestation not recorded / could not be determined"]
    assert rr.exclusion_reasons(woman("c", excl="Structural anomaly, Fetal hydrops")) == \
        ["Major structural anomaly", "Fetal hydrops"]
    assert rr.exclusion_reasons(woman("d", ga=(31, 6))) == []
    secs = rr.exclusions_report([woman("a", ga=(33, 0)), woman("d")], ["PGIMER"])
    assert secs[0]["rows"][0][1:] == [2, 1, "50.0%"]


def test_csv_and_pdf_render():
    rep = {"key": "consent", "title": "Consent refusals", "scope": "PGIMER · all", "generated_at": "06-11-2026 10:00 IST",
           "sections": rr.consent_report([woman("01-1", consent="No", by="Asha", reason="Family pressure"),
                                          woman("01-2", consent="Yes", by="Asha")], ["PGIMER"])}
    assert "Consent taken by" in rr.to_csv(rep)
    assert rr.to_pdf(rep)[:4] == b"%PDF"
