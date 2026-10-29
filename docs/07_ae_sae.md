# 07 — Adverse events (AE) and serious adverse events (SAE)

Severity scale: **INC Neonatal Adverse Event Severity Scale (NAESS) v1.0**
as reorganised by the PI (`AdvEvents_26.08.26_VSedits_26aug2026.docx`).
Definitions and grade text: `backend/ae_reference.py` `AE_DEFINITIONS`
(41 terms, stable lowercase keys).

## 1. AE candidate detection (`GET /adverse-events/candidates/{id}`)

The AE form's "Scan daily logs / Form H" button asks for **candidates**; they
are added as suggested rows (badge "auto-detected", evidence quoted) and
**never saved until a person saves the AE form**. The page sends the rows on screen
(`POST /adverse-events/candidates/{id}`) and skips a candidate the form
already records (`ae_terms.duplicate_of`, PI 2026-10-26): same term, matched
by key, CDISC / MedDRA code or name (case, spacing, a bracketed abbreviation
and a leading "Neonatal" / "Infantile" ignored), and its start within 3 days
of the row's start..end, or a start date missing. The scan message names the
skipped ones and their row numbers. A later episode of the same term is
still offered. Grade 5 (death) is never
auto-assigned; a grade the scale leaves undefined steps down to the highest
defined grade below it (`_resolve_grade`).

| Domain | Detector (`ae_reference.py`) | Terms | Source | Auto-grade |
|---|---|---|---|---|
| 1 | `detect_metab_renal_vasc_eye_candidates` | hyper/hyponatraemia, hyperkalaemia, hypo/hyperglycaemia, hypo/hyperthermia, AKI | Helper 5 values (hard thresholds) | yes, from the numbers / KDIGO stage |
| 2 | `detect_form_h_morbidity_candidates` | IVH, PVL, NEC, BPD, ROP, PDA | **Form H only** (adjudicated) | IVH grade→G1–4; PVL→G1–3; NEC Bell IIA–IIIA→G3, IIIB/surgery→G4, stage I detect-only; ROP treated→G3; PDA none/medical/surgical→G1/2/3; BPD detect-only |
| 3 | `detect_infection_candidates` | culture-positive / culture-negative sepsis, meningitis | Form H infection episodes; else the infection windows | episode→G2 floor; meningitis→G3; lone positive culture detect-only |
| 4 | `detect_form_h_heme_candidates` | hyperbilirubinaemia, anaemia, thrombocytopenia | Form H per term; else Helper 4 treatments | BIND→G4; exchange/DVET→G3; phototherapy→G2; PRBC→G3; platelets→G2 |
| 5 | `detect_form_h_neuro_seizure_candidates` | clinical / EEG seizure | Form H | detect-only |
| 6 | `detect_form_h_cv_shock_candidates` | shock, coagulopathy (weak signal: FFP/cryo) | Form H, else Helper 2 | detect-only |
| 7 | `detect_resp_misc_candidates` | pneumothorax, pulmonary haemorrhage, PPHN, apnoea, feeding intolerance, cholestasis, ventriculomegaly/hydrocephalus, extravasation | Form H per term (an explicit Form H "No" suppresses the day-log fallback), else day logs | detect-only |
| 8 | `detect_domain8_candidates` (PI 2026-10-27) | HIE; hypotension; thromboembolism; administration-site complication; RDS; VAP; UTI; bone-joint infection; osteopenia | HIE: Form I `hie_grade`. Hypotension, line thrombosis / phlebitis: Form H. RDS: surfactant given (Form D, else first Helper 2 day). VAP: Form H infection episode "VAP" or VAP count, else Helper 4. UTI: Form H episode UTI focus or urine culture. Bone-joint: Form H episode focus. Osteopenia: Form H, else Helper 5 "suspected" | HIE Mild/Moderate/Severe→G1/2/3; the rest detect-only |

**Not detected (enter by hand on the AE form; PI 2026-10-27):** porencephalic
cyst (Form F free text only) and the document terms no form captures:
irritability, sedation, brain abscess, stroke, systemic hypertension, sinus
tachy/bradycardia, tachy/bradyarrhythmia, oedema, myocarditis, respiratory
insufficiency, air leak / PIE, lung collapse, subglottic stenosis, pleural
effusion, aspiration, diarrhoea, vomiting, GI bleeding, spontaneous intestinal
perforation, constipation, gastroenteritis, peritonitis, hepatic failure,
liver abscess, rash, fever, neutropenia, polycythaemia, hearing loss, nasal
trauma, nephrocalcinosis, gangrene, accidental injury, inguinal hernia,
pressure sore, and "any other AE". DIC is only suggested through the
coagulopathy check (FFP / cryo given).

Advisory (never a candidate): `detect_pending_cranial_usg_findings` — a severe
Form F finding (IVH III/IV or cPVL ≥ II) not yet reflected in Form H.

Known gap: hyperglycaemia from Helper 5 only sees readings > 180 mg/dL
(the day-log field only stores abnormal values); DMS readings use > 125.

## 2. AE form (`adverse_events`)
- One record per baby; `events` list: description, definition, start/end,
  severity description, grade (1–5), converted to SAE.
- An event that an SAE report is linked to shows "Linked to SAE report" with
  **Apply: Yes** for "Converted to SAE" (never automatic).
- **Save rules (PI 2026-10-26, `main._clean_ae_events`, web + mobile + API):**
  rows with nothing in them are dropped; a row with a grade, date or SAE
  answer but no event (description, or a definition other than "NA") is
  refused with its row number ("enter the event (term) or delete the row").

## 3. SAE list (`sae_list`) and SAE report — Form Y (`sae_reports`)
- SAE list: one row per SAE with 24-h / 14-day notification dates (India NDCT
  Rules 2019 timeline).
- Form Y: one record per report (Initial / Follow-up / Final). Severity uses
  the INC NAESS 5 grades (old 3-level values mapped on load).
- **Form Y needs a diagnosis** to save (create or update, 422 otherwise;
  `main._refuse_empty_sae_report`, PI 2026-10-26). An empty report had been
  saved for 01-B-001 and sent the SAE alert email. The site summary also
  counts only reports with a diagnosis.
- **Linking an AE** (Form Y "Prefill from a recorded AE") saves a **copy** of that
  AE on the report (`linked_ae`: description, dates, grade, evidence) — the
  report keeps what was reported even if the AE list changes; Form Y warns if
  the AE's grade changed or it was removed.
- IEC items stored on the report (v1.1, 30-09-2026): 15.4 dechallenge
  (standard wording by default), 15.9 delay reason (asked when the report date
  is > 24 h after onset), 16.2 cause of death (fatal only), 16.3 other relevant
  information, 20 sponsor causality.
- **Fatal** = "Death" ticked under seriousness **or** outcome "Fatal"
  (`sae_report._is_fatal`).

## 4. Documents
- `GET /sae-report/{enrollment_id}/{report_id}/document?kind=report|covering_letter`
  → CDSCO / PGIMER-DSMC SAE form (22 items) or PI covering letter (`.docx`),
  built by `sae_report.py` from the report + `main._assemble_sae_context`
  (patient details from Form B / A / PII, concomitant therapy from the helper
  logs, prior reports, linked AE).
- Trial / sponsor / site / IEC constants: `sae_config.py`. Items still marked
  `[TO BE PROVIDED …]` there print as such — never guessed.
- **Blinded**: item 13 "suspect drug" is always the generic 30/60/90% oxygen
  description; the app holds no per-baby arm.
- Periodic cumulative site-wise summary:
  `GET /dashboard/safety/summary-report` (`sae_summary_report.py`) — SAE line
  listing + all-AE listing by site for a chosen date range; rows with an
  unparseable onset date are included, never dropped.
- SAE e-mail notification (`email_service.py`, recipients
  `main._sae_notification_recipients`), sent when a Form Y is saved: the
  site's active Site Scientist(s), the site PI email in `sae_config.py`, and
  (PI 2026-10-25) the Global PI and Overall Project Scientist for **every**
  site (active superadmin / project_scientist / global_scientist accounts
  with an email). Duplicates removed ignoring case. SES production access
  granted 2026-10-25; failures never block saving.
