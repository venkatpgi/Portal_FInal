from datetime import date
from types import SimpleNamespace as NS

import ae_summary as s
import ready_reports as rr


def test_terms_typed_by_hand_group_under_inc_terms():
    t = lambda d, c="NA": s.term_of({"description": d, "definition_no": c})[0]
    assert t("Hyperbillirubinemia") == "hyperbilirubinemia"
    assert t("Apnea") == t("Infantile Apnea") == "apnea"
    assert t("Neonatal Respiratory Distress\nSyndrome (RDS") == "rds"
    assert t("Patent  Ductus  Arteriosus ") == "pda"
    assert t("Acute Kidney Injury (AKI) / Acute Renal Failure (ARF)") == "aki"
    assert t("anything", "sepsis_culture_negative") == "sepsis_culture_negative"
    assert t("Lung Collapse") is None and s.term_of({"description": "Lung Collapse"})[1] == "Other: Lung Collapse"


def ev(desc, start, grade="2", end="", sae="No"):
    return {"description": desc, "definition_no": "NA", "start_date": start, "end_date": end,
            "grade": grade, "converted_to_sae": sae}


def build(date_from=None, date_to=None):
    babies = [("PGIMER", "01-A-001", date(2026, 10, 1)), ("PGIMER", "01-A-002", date(2026, 10, 20)),
              ("GMCH", "02-A-001", date(2026, 11, 2))]
    events = {"01-A-001": [ev("Hypothermia", "2026-10-01", "1"), ev("Hypothermia", "2026-10-03", "2"),
                           ev("Shock", "2026-10-25", "4", sae="Yes")],
              "01-A-002": [ev("Hypothermia", "2026-10-21", ""), ev("Lung collapse", "")],
              "02-A-001": [ev("Hypothermia", "2026-11-03", "1")]}
    saes = [NS(enrollment_id="01-A-001", report_type="Initial", diagnosis="Shock", onset_datetime="2026-10-25T10:00",
               seriousness=["Life-threatening"], severity="Grade 4", causality="Unlikely", outcome="Recovering")]
    return s.sections(babies, events, saes, {"01-A-001": date(2026, 10, 28)}, date_from, date_to, rr.site_label)


def test_october_counts_and_denominators():
    secs = build(date(2026, 10, 1), date(2026, 10, 31))
    summary = {r[0]: r[1:] for r in secs[0]["rows"]}
    assert summary["Randomised babies (denominator)"] == [2]          # GMCH baby born in November
    assert summary["Babies with any AE"] == ["2 (100.0%)"]
    assert summary["AE rows started in the period"] == [4]           # the dateless row is not in the period
    assert summary["AE rows, cumulative"] == [5]
    assert summary["Deaths, cumulative"] == ["1 (50.0%)"]
    terms = {r[0]: r for r in secs[1]["rows"]}
    hypo = terms["Hypothermia"]
    assert hypo[1:4] == ["2 (100.0%)", 3, 3] and hypo[4:6] == [1, 1] and hypo[9] == 1
    assert terms["Shock"][10] == 1 and terms["Shock"][11] == "not yet sourced"
    assert terms["Death (any cause)"][1] == "1 (50.0%)" and "[V26]" in terms["Death (any cause)"][11]
    assert len(secs[3]["rows"]) == 1 and len(secs[4]["rows"]) == 4
    checks = {(r[0], r[4]) for r in secs[5]["rows"]}
    assert ("01-A-002", "No readable start date") in checks and ("01-A-002", "Grade blank") in checks
    assert ("01-A-002", "Not matched to an INC AE term") in checks


def test_all_sites_and_files():
    secs = build()
    assert secs[0]["columns"] == ["Measure", "GMCH", "PGIMER", "All sites"]
    rep = {"key": "ae_summary", "title": "AE summary", "scope": "All sites", "generated_at": "09-11-2026", "sections": secs}
    assert "Literature baseline" in rr.to_csv(rep)
    assert rr.to_pdf(rep)[:4] == b"%PDF"
