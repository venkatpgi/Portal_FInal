from ae_terms import duplicate_of, term_of

# Rows as staff typed them on a PGIMER AE form (Oct 2026)
TYPED = [
    {"definition_no": "NA", "description": "Hyperkalemia", "start_date": "2026-10-19"},
    {"definition_no": "C154928 | 10082059", "description": "Neonatal Culture Negative Sepsis",
     "start_date": "2026-10-18"},
    {"definition_no": "NA", "description": "Patent  Ductus  Arteriosus ", "start_date": "2026-10-18"},
    {"definition_no": "C154938 | 10077322", "description": "Apnea", "start_date": "2026-10-18"},
    {"definition_no": "C154937 | 10022844", "description": "Neonatal Intraventricular\nHemorrhage IVH",
     "start_date": "2026-10-18"},
    {"definition_no": "NA", "description": "Lung Collapse", "start_date": "2026-10-20"},
]


def test_term_of_typed_rows():
    assert [term_of(r) for r in TYPED] == ["hyperkalemia", "sepsis_culture_negative", "pda", "apnea", "ivh", None]
    assert term_of({"definition_no": "C154944 | 10076042", "description": "Feeding Intolerance"}) == \
        "feeding_intolerance"
    assert term_of({"description": "Acute renal failure"}) == "aki"
    assert term_of({"description": "Infantile apnea"}) == "apnea"
    assert term_of({"definition_no": "ivh"}) == "ivh"


def test_candidate_already_typed_is_a_duplicate():
    assert duplicate_of({"definition_no": "pda", "start_date": "2026-10-19"}, TYPED) == 3
    assert duplicate_of({"definition_no": "sepsis_culture_negative", "start_date": "2026-10-20"}, TYPED) == 2
    assert duplicate_of({"definition_no": "ivh", "start_date": ""}, TYPED) == 5


def test_new_or_later_episode_is_not_a_duplicate():
    assert duplicate_of({"definition_no": "hypoglycemia", "start_date": "2026-10-19"}, TYPED) is None
    # a second sepsis episode two weeks later is a new AE
    assert duplicate_of({"definition_no": "sepsis_culture_negative", "start_date": "2026-11-02"}, TYPED) is None
    # ...unless the first one is recorded as still running then
    running = [dict(TYPED[1], end_date="2026-11-01")]
    assert duplicate_of({"definition_no": "sepsis_culture_negative", "start_date": "2026-11-02"}, running) == 1
    assert duplicate_of({"definition_no": "nec", "start_date": "2026-10-18"}, []) is None
