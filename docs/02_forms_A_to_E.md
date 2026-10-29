# 02 — Forms A to E

Frontend pages: `ScreeningForm.jsx` (A), `BirthResuscitationForm.jsx` (B),
`FormC.jsx`, `FormD.jsx`, `FormE.jsx`. Backend: `main.py`. Forms A and B are
**frozen** (PI, 2026-09-19): wording changes only by explicit decision.

---

## Form A — Screening (`screenings`)

**Where it starts.** Normally from the Gestation Log: a Reliable, in-window
gestation check → "Continue to Form A" stores a seed in the browser
(`localStorage.ga_check_seed`) → Form A pre-fills Best-estimate GA + Method
and, once saved, links back to the log entry (`PATCH /ga-check/{id}/link`).

**Server rules**
- **No screening id / no save unless GA is 25w0d–31w6d**
  (`main.require_ga_in_inclusion_window` → 422). Window constants
  `GA_MIN_TOTAL_DAYS = 175`, `GA_MAX_TOTAL_DAYS = 223`.
- `screening_status` is recomputed on every save and re-healed on every read
  (`main.compute_screening_status`, `heal_screening_status`):
  | Condition (in order) | Status |
  |---|---|
  | GA "Neither" (legacy path) | Screen Failure |
  | no GA | Pending |
  | GA outside window | Not Eligible |
  | any exclusion Yes | Screen Failure |
  | consent Yes | Eligible ("Trial run" retired 2026-10-18: refused on save, no longer counts) |
  | consent No / Not approached | Not Eligible |
  | otherwise | Pending |
- Identity fields go to `participant_pii` (chapter 01 §4).

**Page rules (`ScreeningForm.jsx`)**
- Best-estimate GA is item 1 (the old "Gestation known?" item was removed
  23-09-2026). GA outside the window shows "Not eligible" and **locks Forms B+**.
- **LMP cross-check** (`lmpMismatch`): if Method = LMP, the LMP-implied GA
  (as of the screening date) is compared with Best-estimate GA; > 3 days apart
  → amber warning (does not block).
- CR number / admission number format per site (`idFieldRule`):
  PGIMER CR 12 digits (**required** on Form A); AMC CR `serial/year`
  (required); admission numbers optional with per-site digit counts.
- Mobiles: 10 digits starting 6–9.
- Exclusions (A4): structural anomaly, hydrops, decision to forego
  resuscitation, insufficient time, IUFD — each Yes needs its detail.
- Consent (A5): relationship + nurse required for Yes / No;
  **signature pad only for Yes** (a refusal saves without one);
  refusal reasons required for No, not-approached reasons for Not approached.
- `is_complete` sent on every save = `validate()` found nothing missing.
- **Consent after Form A is saved** (`pregnancy_followup.consent_change_error`,
  server 422 on `PUT /screenings/{id}`, PI 2026-10-20; only once
  `explicitly_saved`; Site PI / Global PI may correct a data-entry mistake):
  - **Yes stands** for every admission of the pregnancy; it is not changed to
    No. If the woman herself withdraws, record it in A6.
  - **No (refused) is final**: she is not approached again.
  - **Not approached → Yes** is allowed on a later admission while her GA
    today (Form A GA + days since screening) is 25w0d–31w6d. Edit the same
    Form A; never a second one (same CR is refused anyway).
- **A6 Pregnancy follow-up** (consent Yes only; `components/PregnancyFollowUp.jsx`,
  `PATCH /screenings/{id}/pregnancy-follow-up`, saved without unlocking Form A):
  discharges home undelivered + readmission dates (in order, only the last may
  lack a readmission), pregnancy outcome (Delivered here / Delivered elsewhere /
  Lost to follow-up + date; not "elsewhere/lost" once Form B exists) and
  **consent withdrawn by the woman** + date (not once Form B exists; Form B is
  then refused). Columns `screenings.pregnancy_episodes` (JSON),
  `pregnancy_outcome`, `pregnancy_outcome_date`, `consent_withdrawn`,
  `consent_withdrawn_date`. CONSORT boxes do not yet show withdrawals separately.

---

## Form B — Birth & resuscitation (`birth_resuscitation`)

**Key derived values**
- **Strata**: from GA at randomisation — `< 28 weeks` if < 196 days, else
  `≥ 28 – 31 weeks` (auto, page `computedStrata`).
- **Blender letter** = the letter in the enrollment id (`01-B-123` → B)
  (`blenderLetterFromEnrollmentId`).
- **Cord clamp**: elapsed seconds from time of birth ↔ clamp clock time,
  wrapping past midnight (`cordClampElapsedSeconds`).
- IOG: baby admission no. = baby UID (auto).
- **Effective gestation** for every later form: Form B GA, **replaced by Form D
  "NBS" GA when that differs by more than 14 days** (backend
  `get_birth_resuscitation` returns it as `gestation_weeks/days` with
  `gestation_source = "Form D NBS"`; frontend `utils/gestation.resolveEffectiveGestation`).
  → A wrong Form D NBS entry shifts **every PMA checkpoint date** downstream.

**Pregnancy (single / twins / triplets / quadruplets, PI 2026-10-29)** is
recorded on the Gestation Log entry (`ga_check_log.number_of_fetuses`),
carried into Form A on "Continue to Form A" (`screenings.number_of_fetuses`,
editable there) and starts Form B's "Number of babies" when no baby of that
mother has a Form B yet. The Log of All Births birth type wins over it
(`GET /screenings/{id}/babies` returns `log_of_births_babies` and
`pregnancy_babies`); Form B warns when its number differs from the Log of
All Births.

**Twins / triplets (PI 2026-10-29)** — B1 "Number of babies born to this
mother" and, for 2 or more, a switcher "Baby 1 / Baby 2 …" (dashed = Form B
not entered yet; click to add it). One Form B per baby; each baby is
randomised independently with its own envelope. Chapter 01 "Twins" has the
ID and save rules. Form C for a second baby offers "Copy its answers to this
baby" from a co-twin's saved Form C (a new record; check every answer).
The sidebar shows the same switcher on every form of a twin.

**Enrollment decision**
- "Does baby require ventilation (PPV)?" = No → **not randomised, locked**
  (`applyInitialStepsNotRequired`, `lockEnrollmentNoPpv`); server assigns
  `NR-<screening id>`.
  **Enrolment ends at Form B** (PI 2026-10-16): Form C and later are not filled; the
  sidebar opens only Forms A and B and the server refuses Form C
  (`main._refuse_form_c_without_ppv`). A baby who needed PPV but was not
  randomised keeps all forms (followed for major outcomes).
- Randomised = Yes needs enrollment id (`01-A-001` format on Save), randomisation
  date, strata. Randomised = No needs "Reason not randomised" (feeds CONSORT
  Box 7, chapter 08).

**Checks on Save (page `validate`)**: birth weight 300–6000 g; DOB not in
future; **birth not before the Form A screening time**; centile 0–100; time to
spontaneous breathing ≤ total resuscitation time (APGAR timer); SpO₂ > 80%
time as MM:SS; per-device PPV fields; chest compressions / epinephrine /
fluid bolus details when Yes.

**Server checks (`main.create_birth_resuscitation` / `update_birth_resuscitation`)**:
enrollment id and baby UID must not belong to another patient (409);
**enrollment id must be a complete `<site>-<A-D>-<number>` id or an `NR-`
placeholder** (`require_valid_enrollment_id_format`, 422 otherwise — added
30-09-2026 after `01-` and `01-B-` each became their own permanent record);
**the linked Form A screening must be Eligible** — GA in window, no
exclusion, consent Yes / Trial run (`require_eligible_screening_for_form_b`,
422 otherwise, applies to the `NR-` "no PPV needed" path too — added
30-09-2026 after a consent-"No" screening still ended up with two randomised
Form B rows and helper-form data, chapter 09 §1/§2). Both guards run on
every create *and* update, so they apply to any caller (web, mobile app, a
direct API call), not just the browser's own sidebar lock.

---

## Form C — Maternal details (`maternal_details`)

- **GPAL consistency** (`computeGpalErrors`): gravida ≥ 1; parity ≤ G−1;
  abortions ≤ G−1; **parity + abortions = G−1**; live ≤ parity; still ≤ parity;
  live + still ≤ parity.
- **Antenatal steroids** (`computeSteroidCourse`): doses per course —
  Betamethasone 2, Dexamethasone 4 (caps 8 / 12 doses). Course "Complete"
  only when doses fill whole courses exactly. Per-drug last-dose-to-delivery
  interval (LDDI) captured separately.
- **Triple I** (`computeTripleI`, auto): maternal fever No → No; fever Yes and
  ≥ 2 of {fetal tachycardia, high TLC, maternal tachycardia, uterine
  tenderness} → Yes; all four answered with < 2 Yes → No; otherwise blank.
- "No known medical disorder" clears all disorder ticks.
- Isoimmunization Yes → Type (Rh / ABO / Minor blood group).

---

## Form D — Day-1 postnatal (`postnatal_day1`)

- **GA method NBS**: if the NBS GA differs from Form B GA by > 14 days, a
  confirmation popup appears (`checkGaDiffOnBlur`) and the NBS GA becomes the
  effective gestation for all later forms (see Form B above).
- **Growth status** from INTERGROWTH-21st very-preterm centile of birth
  weight/GA/sex (`growthFromIntergrowth`, 24+0–32+6 wk only):
  < 3rd → SGA "<3rd"; < 10th → SGA "<10th"; > 90th → LGA; else AGA.

---

## Form E — NICU admission (`nicu_admission`)

- **Age at admission** = admission time − (DOB + time of birth), in minutes
  (`calcAgeAtAdmission`); stored as `age_at_admission_minutes`.
- **Server: admission cannot be before birth** (`main._validate_admission_after_birth`, 422).
- **Respiratory mode greys out / clears fields** that don't apply
  (`computeModeClearFields`): Room air clears everything; CPAP clears
  PIP/PEEP/MAP/HFOV; SIB clears all but FiO₂; NIPPV/IMV/SIMV clear CPAP;
  HFOV clears CPAP/PIP/PEEP and shows Amplitude (2–80) / Frequency (5–20 Hz).
  Applies to both "During transport" and "In NICU".
- Mode of transport (one selector) is stored in the legacy
  `transport_incubator` + `transport_mode` columns (`deriveTransportModeFields`).
- **Day 1 Date** (`PUT /nicu-admission/{id}/day1-date`): should equal DOB.
  Nurses may set only today, or yesterday before 08:00; **locked once any
  Helper 2/4/5 day log exists** (`_day1_date_is_locked`) except for superadmin.
  **Form I's 36/40/44-week section needs it** — if blank, Form I shows
  "no data" for every checkpoint (chapter 04).
- `finalized` is set by the explicit Save; `is_complete` from `collectFormEErrors()`.
