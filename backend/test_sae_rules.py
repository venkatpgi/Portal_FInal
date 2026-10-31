from datetime import date
from types import SimpleNamespace as NS

import sae_config
from sae_narrative import DRAFT_LINE, ae_terms_of, compose, course_events
from sae_rules import apply_rules, event_title


def report(**kw):
    return {"report_type": "Follow-up", "seriousness": [], "outcome": None, "causality": None,
            "sponsor_causality": None, "death_from_event": None, **kw}


def test_initial_drops_new_causality_but_keeps_what_an_old_report_holds():
    p = report(report_type="Initial", causality="Possible", sponsor_causality="Related")
    assert apply_rules(p) is None
    assert (p["causality"], p["sponsor_causality"]) == (None, None)
    p = report(report_type="Initial", causality="Possible")
    assert apply_rules(p, NS(causality="Unlikely", sponsor_causality=None)) is None
    assert p["causality"] == "Unlikely"


def test_follow_up_optional_final_required():
    assert apply_rules(report()) is None
    assert "Causality (item V) and" in apply_rules(report(report_type="Final"))
    assert apply_rules(report(report_type="Final", causality="Possible",
                              sponsor_causality="Awaiting sponsor assessment")) is None


def test_fatal_title_never_doubles_death():
    assert event_title("NEC", True) == "NEC, Death"
    assert event_title("NEC", False) == "NEC"
    assert event_title("Death due to sepsis", True) == "Death due to sepsis"
    assert event_title("", True) == "Death"


def test_a_death_not_from_this_sae_is_refused_here():
    assert "separate SAE report" in apply_rules(report(outcome="Fatal", death_from_event=False))
    assert apply_rules(report(seriousness=["Death"], death_from_event=True)) is None
    p = report(death_from_event=True)
    apply_rules(p)
    assert p["death_from_event"] is None


def test_pgimer_iec_people():
    assert sae_config.PGIMER_IEC["chairperson"] == "Justice M R Agnihotri"
    assert sae_config.PGIMER_IEC["convener"] == "Dr Ashish Kakkar, Member-Secretary"


def resp(day, modes="", **kw):
    return NS(nicu_day=day, support_modes=modes, vasoactive_support=None, pneumothorax=None, pulm_hemorrhage=None,
              shock=None, clinical_seizures=None, eeg_seizures=None, **kw)


def inf(day, **kw):
    return NS(**{**dict(nicu_day=day, antibiotics=None, nec_confirmed_stage=None, nec_suspected=None,
                        prbc_transfusion=None, platelet_transfusion=None), **kw})


def test_course_is_in_order_only_changes_and_blanks_say_not_recorded():
    terms = ae_terms_of([{"definition_no": "ivh", "grade": "3", "start_date": "2026-10-04"}],
                        [{"definition_no": "ivh", "grade": 2, "start_date": "2026-10-04"}])
    events = course_events([resp(1, "CPAP"), resp(2, "CPAP"), resp(3, "SIMV")],
                           [inf(2, antibiotics=True), inf(3, antibiotics=True), inf(4, nec_suspected=True)],
                           [], terms)
    text = compose({"dob": date(2026, 10, 1), "gestation": "27 weeks 1 day", "birth_weight": 900.0}, events,
                   {"enrollment_id": "01-0001", "diagnosis": "NEC", "outcome": "Fatal", "onset_datetime": "2026-10-04T09:30"},
                   date(2026, 10, 1), date(2026, 10, 9))
    assert text.startswith(DRAFT_LINE)
    assert "birth weight 900 g" in text and "sex not recorded" in text and "delivery not recorded" in text
    days = [l for l in text.splitlines() if "(Day" in l]
    assert [l.split(": ", 1)[1] for l in days] == [
        "Respiratory support: CPAP.", "Antibiotics started.", "Respiratory support: SIMV.",
        "NEC suspected.", "Neonatal Intraventricular Hemorrhage (IVH) grade 3 (AE form)."]
    assert days[4].startswith("04 Oct 2026 (Day 4)")
    assert "SAE: NEC, Death." in text and "Date of death: not recorded." in text


def test_nothing_from_after_today_and_no_oxygen_values():
    text = compose({}, [(9, None, "Later")], {"enrollment_id": "1"}, date(2026, 10, 1), date(2026, 10, 5))
    assert "Later" not in text and "Course: daily entries not recorded." in text
    import sae_narrative
    code = open(sae_narrative.__file__).read().split('"""', 2)[2].lower()
    assert "fio2" not in code and "spo2" not in code and "evidence" not in code
