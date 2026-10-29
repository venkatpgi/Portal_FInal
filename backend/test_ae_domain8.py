from datetime import date
from types import SimpleNamespace as NS

from ae_reference import detect_domain8_candidates
from ae_terms import duplicate_of, term_of

D1 = date(2026, 10, 14)


def run(nm=None, postnatal=None, outcomes=None, resp=(), inf=(), metab=()):
    return {c["definition_no"]: c for c in
            detect_domain8_candidates(nm, postnatal, outcomes, list(resp), list(inf), list(metab), day1_date=D1)}


def test_nothing_recorded_nothing_detected():
    assert run() == {}
    assert run(nm=NS(hypotension=False, osteopenia="No", vap_episodes=0, infections=[]),
               outcomes=NS(hie_grade="None"), postnatal=NS(surfactant_required=False)) == {}


def test_hie_graded_from_form_i():
    for text, g in (("Mild", "1"), ("Mod", "2"), ("Moderate", "2"), ("Severe", "3")):
        c = run(outcomes=NS(hie_grade=text))["hie"]
        assert c["grade"] == g and c["start_date"] == "2026-10-14"


def test_detect_only_terms_from_form_h():
    nm = NS(hypotension="Yes", hypotension_systolic=True, line_comp_thrombosis=True, line_comp_phlebitis=True,
            osteopenia="Yes", alp_peak=900.0, lowest_phosphorus=None, vap_episodes=None,
            infections=[{"sepsis": "Yes", "sepsis_episode_number": 1, "sepsis_onset_age": 120,
                         "focus_uti": True, "focus_bone_joint": True, "vap": "Yes"}])
    c = run(nm=nm)
    assert set(c) == {"hypotension", "thromboembolism", "administration_site", "osteopenia", "uti",
                      "bone_joint_infection", "vap"}
    assert all(x["grade"] == "" for x in c.values())
    assert "systolic" in c["hypotension"]["evidence"] and "peak ALP 900" in c["osteopenia"]["evidence"]
    assert c["uti"]["start_date"] == "2026-10-19"


def test_rds_when_surfactant_given():
    assert run(postnatal=NS(surfactant_required=True, surfactant_indication="RDS"))["rds"]["start_date"] == \
        "2026-10-14"
    c = run(postnatal=NS(surfactant_required=False), resp=[NS(nicu_day=3, surfactant=True)])["rds"]
    assert c["start_date"] == "2026-10-16" and c["grade"] == ""


def test_form_h_no_suppresses_day_log():
    assert "osteopenia" in run(metab=[NS(nicu_day=20, osteopenia_suspected=True)])
    assert "osteopenia" not in run(nm=NS(osteopenia="No"), metab=[NS(nicu_day=20, osteopenia_suspected=True)])
    assert "vap" in run(inf=[NS(nicu_day=8, vap=True)])
    assert "vap" not in run(nm=NS(vap_episodes=0), inf=[NS(nicu_day=8, vap=True)])


def test_typed_rows_are_recognised():
    assert term_of({"definition_no": "C154945 | 10070512", "description": "HIE"}) == "hie"
    assert term_of({"definition_no": "NA", "description": "RDS"}) == "rds"
    assert term_of({"definition_no": "NA", "description": "Respiratory distress syndrome"}) == "rds"
    assert term_of({"definition_no": "NA", "description": "Hypotension"}) == "hypotension"
    typed = [{"definition_no": "NA", "description": "RDS", "start_date": "2026-10-14"}]
    assert duplicate_of(run(postnatal=NS(surfactant_required=True))["rds"], typed) == 1
