"""Plain-English names for report columns (PI 2026-10-25).

The report builder shows "Birth weight (B_birth_weight)": the English name the
PI and site staff read, with the variable name statisticians use in brackets.
label(form, column) builds the English name from the variable name:
  1. OVERRIDES[form.column] or OVERRIDES[column] when written out by hand;
  2. otherwise each "_" word through WORDS (abbreviations, units, eyes), and
     a trailing 36 / 40 / 44 in a Form I name becomes "at 36 wk" etc.
Unknown words are kept as they are, so a label is never wrong, only plain;
the variable name in brackets is always the exact source.
"""
import re

# Whole-word replacements (lower-case word -> text).
WORDS = {
    # Abbreviations kept as clinicians write them
    "ga": "GA", "rop": "ROP", "ivh": "IVH", "pvl": "PVL", "cpvl": "cystic PVL", "nec": "NEC",
    "bpd": "BPD", "pda": "PDA", "hs": "haemodynamically significant", "cpap": "CPAP",
    "fio2": "FiO2", "spo2": "SpO2", "ppv": "PPV", "peep": "PEEP", "pip": "PIP", "map": "MAP",
    "mgso4": "MgSO4", "hie": "HIE", "mri": "MRI", "eeg": "EEG", "aed": "anti-seizure drug",
    "aeds": "anti-seizure drugs", "lscs": "LSCS", "edd": "EDD", "lmp": "LMP", "anc": "ANC",
    "hdp": "HDP", "gdm": "GDM", "fgr": "FGR", "aph": "APH", "pprom": "PPROM", "uti": "UTI",
    "nst": "NST", "fm": "fetal movements", "rom": "rupture of membranes", "msl": "MSL",
    "kmc": "KMC", "lisa": "LISA", "imv": "IMV", "niv": "NIV", "nippv": "NIPPV", "hfnc": "HFNC",
    "uac": "UAC", "uvc": "UVC", "picc": "PICC", "vap": "VAP", "aki": "AKI", "tsb": "TSB",
    "hb": "Hb", "prbc": "PRBC", "ffp": "FFP", "ivig": "IVIG", "cmv": "CMV", "dvet": "DVET",
    "bind": "BIND", "sga": "SGA", "nicu": "NICU", "dr": "delivery room", "vp": "VP",
    "phvd": "PHVD", "phh": "PHH", "pvhi": "PVHI", "ich": "ICH", "csf": "CSF", "vi": "VI",
    "ahw": "AHW", "tod": "TOD", "aca": "ACA", "mca": "MCA", "ri": "RI", "la": "LA", "ao": "Ao",
    "lpa": "LPA", "tdd": "TDD", "sbp": "SBP", "dbp": "DBP", "vis": "VIS", "alp": "ALP",
    "ebm": "EBM", "pdhm": "PDHM", "pn": "PN", "tpn": "TPN", "hc": "HC", "hr": "HR",
    "tlc": "TLC", "vdrl": "VDRL", "hiv": "HIV", "tb": "TB", "edf": "EDF", "et": "ET",
    "pma": "PMA", "a": "A", "arop": "A-ROP", "vegf": "VEGF", "nichd": "NICHD", "sib": "SIB",
    "eos": "early-onset", "los": "late-onset", "crf": "CRF",
    "co2": "CO2", "pco2": "pCO2", "ph": "pH", "sbe": "SBE", "ino": "iNO",
    "cc": "chest compressions", "epi": "adrenaline", "rx": "treatment", "dx": "diagnosis",
    "fi": "feed intolerance", "ibu": "ibuprofen", "indo": "indomethacin", "pcm": "paracetamol",
    "milri": "milrinone", "miliri": "milrinone", "adr": "adrenaline", "nadr": "noradrenaline",
    "dopa": "dopamine", "dobu": "dobutamine", "vaso": "vasopressin",
    "dyselectro": "dyselectrolytaemia", "ca": "Ca", "k": "K", "na": "Na",
    "bi": "bifidobacterium", "mono": "single-strain", "multi": "multi-strain",
    # Units and short words
    "mm": "(mm)", "cmh2o": "(cm H2O)", "mgkg": "(mg/kg)", "hrs": "hours", "dob": "date of birth",
    "rand": "at randomisation", "tpiece": "T-piece", "abs": "(absolute)", "maint": "maintenance",
    "mins": "minutes", "min": "minutes", "max": "maximum", "approx": "approximate",
    "resp": "respiratory", "resus": "resuscitation", "temp": "temperature", "htn": "hypertension",
    "comp": "complication", "chf": "CHF", "pp": "pulse pressure", "ido": "indirect ophthalmoscopy",
    "retcam": "RetCam", "jensen": "Jensen", "beta": "betamethasone", "dexa": "dexamethasone",
    "lddi": "last dose to delivery interval", "treat": "treatment", "cryo": "cryoprecipitate",
    "o2": "oxygen", "1hr": "1 hour", "7d": "7-day", "28d": "28-day", "72h": "72-hour",
    "le": "(left eye)", "re": "(right eye)",
    "datetime": "date and time",
}

# Hand-written names: "form.column" for one form, "column" for every form.
OVERRIDES = {
    # Bookkeeping, every form
    "is_complete": "Form marked complete",
    "explicitly_saved": "Saved by the user",
    "created_at": "Record created (date and time)",
    "updated_at": "Last changed (date and time)",
    "created_by": "Created by (user ID)",
    "updated_by": "Last changed by (user ID)",
    "completed_by": "Completed by",
    "completion_date": "Date completed",
    "designation": "Designation of person completing",
    "gestation_weeks": "Gestation (weeks)",
    "gestation_days": "Gestation (+ days)",
    "birth_weight": "Birth weight (g)",
    "annual_number": "Baby annual number",
    # Form A
    "A.site_id": "Site code",
    "A.screened_by": "Screened by",
    "A.screening_status": "Screening status (as saved)",
    "A.screening_datetime": "Screening date and time",
    "A.gestation_known": "Gestation known",
    "A.gestation_method": "How gestation was assessed",
    "A.ga_source": "Source of GA",
    "A.lmp_date": "LMP date",
    "A.expected_delivery_date": "Expected delivery date",
    "A.inclusion_gest_lt_32": "Inclusion: gestation < 32 weeks",
    "A.anticipated_dr_resus": "Inclusion: delivery-room resuscitation anticipated",
    "A.exclusion_present": "Any exclusion criterion present",
    "A.exclusion_reasons": "Exclusion reasons",
    "A.major_structural_anomalies_if_yes": "Major structural anomalies (details)",
    "A.final_decision": "Final eligibility decision",
    "A.consent_given": "Consent given",
    "A.consent_datetime": "Consent date and time",
    "A.reconsent_obtained": "Re-consent obtained",
    "A.reconsent_datetime": "Re-consent date and time",
    "A.relationship_to_participant": "Consent given by (relationship)",
    "A.video_pis_shown": "Video PIS shown",
    "A.pregnancy_episodes": "Pregnancy follow-up episodes (A6)",
    "A.pregnancy_outcome": "Pregnancy outcome (A6)",
    "A.pregnancy_outcome_date": "Pregnancy outcome date (A6)",
    "A.deleted_at": "Deleted (date and time)",
    "A.deleted_by": "Deleted by",
    # Form B
    "B.baby_admission_no": "Baby admission number",
    "B.baby_annual_no": "Baby annual number",
    "B.gestation_rand_weeks": "Gestation at randomisation (weeks)",
    "B.gestation_rand_days": "Gestation at randomisation (+ days)",
    "B.intrauterine_centile": "Intrauterine growth centile",
    "B.poor_resp_efforts": "Poor respiratory effort at birth",
    "B.hr_above_100": "Heart rate above 100 at birth",
    "B.required_resuscitation": "Needed PPV (resuscitation)",
    "B.strata": "Randomisation stratum",
    "B.blender_letter": "Blender letter",
    "B.enrollment_reason_not_randomized": "Reason not randomised",
    "B.enrollment_reason_not_randomized_other": "Reason not randomised (other)",
    "B.device_ppv": "PPV device",
    "B.randomised": "Randomised",
    "B.randomisation_date": "Randomisation date",
    "B.med_doses": "Adrenaline doses",
    "B.time_to_respiration": "Time to spontaneous breathing",
    "B.time_to_spo2_80": "Time to SpO2 80%",
    "B.spo2_5min": "SpO2 at 5 minutes",
    "B.resus_failure": "Resuscitation failure",
    "B.reason_exit_trial_gas": "Reason for leaving trial gas",
    "B.spo2_exit_trial_gas": "SpO2 when leaving trial gas",
    "B.total_resus_time": "Total resuscitation time",
    "B.cord_clamp_time": "Time to cord clamping",
    "B.cord_clamp_timestamp": "Cord clamping time",
    # Form C
    "C.mother_age": "Mother's age (years)",
    "C.live": "Live children",
    "C.still": "Stillbirths",
    "C.booked": "Booked pregnancy",
    "C.multiple": "Multiple pregnancy",
    "C.lmp": "LMP",
    "C.edd": "EDD",
    "C.conception": "Mode of conception",
    "C.artificial_type": "Assisted conception type",
    "C.lddi_known": "Last dose to delivery interval known",
    "C.lddi_hours": "Last dose to delivery interval (hours)",
    "C.triple_i": "Triple I (intra-amniotic infection)",
    "C.liquor": "Liquor volume",
    "C.duration_rom": "Duration of rupture of membranes",
    # Form D
    "D.ga_method": "How GA was assessed",
    "D.growth_status": "Growth status",
    "D.plastic_wrap": "Plastic wrap used",
    "D.remained_intubated": "Remained intubated after resuscitation",
    "D.et_intubation": "Endotracheal intubation",
    "D.labored_breathing": "Laboured breathing",
    "D.fio2_percent": "FiO2 (%)",
    "D.cpap_cm": "CPAP (cm H2O)",
    "D.max_fio2_1hr": "Maximum FiO2 in first hour",
    "D.mode_of_support": "Respiratory support mode",
    "D.immediate_kmc": "Immediate KMC",
    # Form E
    "E.admission_datetime": "NICU admission date and time",
    "E.age_at_admission_hours": "Age at NICU admission (hours)",
    "E.age_at_admission_minutes": "Age at NICU admission (minutes)",
    "E.temp_dr": "Temperature in delivery room",
    "E.temp_skin": "Skin temperature on admission",
    "E.temp_axillary": "Axillary temperature on admission",
    "E.day1_date": "Day 1 date",
    "E.finalized": "Finalised",
    # Form F
    "F.scan_entries": "Scan entries (all scans)",
    "F.brain_injury_composite": "Brain injury composite",
    "F.schedule_key": "Scan schedule",
    # Form G (columns without _le are the right eye)
    "G.risk_factors": "ROP risk factors",
    "G.screenings": "ROP screening entries",
    "G.dob": "Date of birth",
    "G.pma_discharge": "PMA at discharge",
    "G.rop_treatment_composite": "ROP treatment composite",
    # Form H
    "H.total_los_days": "Total length of stay (days)",
    "H.total_los": "Total length of stay",
    "H.nicu_days": "NICU stay (days)",
    "H.discharge_hc": "Head circumference at discharge",
    "H.hc_first_drug": "Hydrocortisone: first drug",
    "H.hc_after_first": "Hydrocortisone after first course",
    "H.hc_after_second": "Hydrocortisone after second course",
    "H.hydrocortisone_bp": "Hydrocortisone for blood pressure",
    "H.bpd_support_36w": "BPD: respiratory support at 36 weeks",
    "H.o2_days": "Oxygen (days)",
    "H.vent_days": "Ventilation (days)",
    "H.pn": "Parenteral nutrition",
    "H.pn_days": "Parenteral nutrition (days)",
    "H.fm_days": "Formula milk (days)",
    "H.age_full_feeds": "Age at full feeds",
    "H.age_first_feed": "Age at first feed",
    "H.back_referred_hospital": "Back-referred to hospital",
    "H.back_referral_hospital": "Back-referral hospital",
    "H.infection_flags_reviewed": "Infection flags reviewed",
    "H.rop_flags_reviewed": "ROP flags reviewed",
    # Form I
    "I.mortality_in_hospital": "Death in hospital",
    "I.mortality_after_discharge": "Death after discharge",
    "I.mortality_7_days": "Death within 7 days",
    "I.mortality_28_days": "Death within 28 days",
    "I.switched_100_o2": "Switched to 100% oxygen",
    "I.cc_epi_volume": "Chest compressions / adrenaline volume",
    "I.resp_support_72h": "Respiratory support at 72 hours",
    "I.sepsis_72h": "Sepsis within 72 hours",
    "I.mv_days": "Mechanical ventilation (days)",
    "I.rop_44w": "ROP at 44 weeks",
    "I.abnormal_mri_tea": "Abnormal MRI at term-equivalent age",
    "I.crf_additional_notes": "CRF additional notes",
    # Form J
    "J.assessment_weeks": "Assessment at (weeks PMA)",
    "J.hospital": "Hospital",
    "J.resp_mode": "Respiratory support mode",
    "J.radiographic_lung": "Radiographic lung disease",
    "J.mri_done": "MRI done",
}

_TIMEPOINT = re.compile(r"^([a-z]+?)(36|40|44)(?=_|$)")   # death36_cause, rop36, nec40_stage
_MINUTES = re.compile(r"^(\d+)min$")                       # 5min
_WEEKS = re.compile(r"^(\d+)w$")                           # 36w
_NUMBERED = re.compile(r"^([a-z]+)(\d+)$")                 # stage1, grade3, day1


def _word(w: str) -> str:
    if w in WORDS:
        return WORDS[w]
    m = _MINUTES.match(w)
    if m:
        return f"at {m.group(1)} minutes"
    m = _WEEKS.match(w)
    if m:
        return f"at {m.group(1)} weeks"
    m = _NUMBERED.match(w)
    if m:
        return f"{_word(m.group(1))} {m.group(2)}"
    return w


def label(form: str, column: str) -> str:
    """English name for one report column, e.g. ("B", "birth_weight") -> "Birth weight (g)"."""
    text = OVERRIDES.get(f"{form}.{column}") or OVERRIDES.get(column)
    if text:
        return text
    suffix = ""
    m = _TIMEPOINT.match(column)
    if m:
        column = m.group(1) + column[m.end():]
        suffix = f" at {m.group(2)} weeks"
    words = [_word(w) for w in column.split("_") if w]
    text = " ".join(words) + suffix
    return text[:1].upper() + text[1:]
