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


def birth(site="PGIMER", born=None, form_a=False, reasons=(), other=(), rows=(1,), ga=("28+0",)):
    from datetime import date
    return {"site": site, "born": born or date(2026, 11, 1), "rows": list(rows), "ga": list(ga),
            "form_a": form_a, "reasons": list(reasons), "other": list(other)}


def test_eligible_births_to_consent_funnel():
    births = [birth(form_a=True), birth(form_a=True, rows=(2, 3), ga=("30+1", "30+1")),
              birth(reasons=["No time to approach to screen"], rows=(4,)),
              birth(reasons=["Other", "No time to approach to screen"], other=["Mother unwell"], rows=(5,)),
              birth(rows=(6,))]
    rows = [woman("01-1", consent="No"), woman("01-2", consent="Yes"), woman("01-3", consent="Yes"),
            woman("01-4", excl="Insufficient time"), woman("01-5", excl="Structural anomaly"), woman("01-6")]
    secs = rr.consent_report(rows, ["PGIMER"], births)
    titles = [s["title"] for s in secs]
    assert titles[:5] == ["From eligible births to consent", "Eligible births with no Form A: reasons",
                          "Screened but not asked for consent: reasons",
                          "List of eligible births with no Form A (3)",
                          "List of screened women not asked for consent (3)"]
    assert titles[5] == "Refusals by site"
    # site: eligible 5 women, 3 no Form A, screened 6, 3 not asked, 3 asked, 2 consented, 1 refused
    assert secs[0]["rows"] == [["PGIMER", 5, 3, "60.0%", 6, 3, 3, 2, 1, "33.3%"]]
    assert {r[0]: r[1] for r in secs[1]["rows"]} == {"No time to approach to screen": 2, "Other": 1,
                                                      "(not recorded)": 1}
    assert {r[0]: r[1] for r in secs[2]["rows"]} == {"Insufficient time to approach for consent": 1,
                                                      "Major structural anomaly": 1, "Consent not yet recorded": 1}
    assert secs[3]["rows"][1] == ["5", "PGIMER", "01-11-2026", "28+0", "Other, No time to approach to screen",
                                  "Mother unwell"]
    assert [r[0] for r in secs[4]["rows"]] == ["01-4", "01-5", "01-6"]


def test_funnel_two_sites_has_total_and_site_columns():
    births = [birth(site="PGIMER", reasons=["No time to approach to screen"]), birth(site="GMCH", form_a=True)]
    rows = [woman("01-1", consent="No"), woman("02-1", site="GMCH", consent="Yes")]
    secs = rr.consent_report(rows, ["PGIMER", "GMCH"], births)
    assert secs[0]["rows"][-1] == ["All sites", 2, 1, "50.0%", 2, 0, 2, 1, 1, "50.0%"]
    assert secs[1]["columns"][-2:] == ["PGIMER", "GMCH"] and secs[1]["rows"][0][-2:] == [1, 0]


def test_not_asked_reason_uses_reason_not_approached():
    w = woman("01-9")
    w.reason_not_approached = "Mother in active labour"
    assert rr.not_asked_reasons(w) == ["Mother in active labour"]


def test_gap_ranges():
    assert rr._ranges([1, 2, 3, 7, 9, 10]) == "001–003, 007, 009–010"
    assert rr._ranges([]) == ""
