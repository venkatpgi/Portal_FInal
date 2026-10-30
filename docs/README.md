# PORTAL eCRF — logic, calculations and form linkage reference

This folder documents **how every form's data is derived, checked and passed on**,
from Form A (screening) to Form L (summary), the daily logs, AE/SAE and the
screening logs. It exists for one purpose: **when a number looks wrong, find
where it came from and why.**

It was written from the code as of 30-09-2026 (commit on `main` after
`06b9f68`). Every rule names the file and function that implements it — if
the doc and the code ever disagree, **the code is what runs**; fix the doc in
the same commit.

## Chapters

| File | Covers |
|---|---|
| [01_data_model_and_ids.md](01_data_model_and_ids.md) | Tables per form, ID scheme (screening / enrollment / NR-), site isolation, PII split + encryption, autosave, "saved" vs "complete" flags |
| [02_forms_A_to_E.md](02_forms_A_to_E.md) | Screening, birth/resuscitation, maternal, day-1 postnatal, NICU admission |
| [03_daily_logs_DMS_and_helpers.md](03_daily_logs_DMS_and_helpers.md) | Daily Monitoring Sheet (DMS) and Helpers 2–5: what the DMS feeds, completion %, day numbering, locking and override |
| [04_forms_F_to_L.md](04_forms_F_to_L.md) | Cranial USG, ROP, Form H (morbidities) and its 10 auto-fill domains, Form I checkpoints, Forms J/K/L |
| [05_outcome_suggestions.md](05_outcome_suggestions.md) | BPD, ROP, NEC, brain injury and composite-outcome suggestions; death rules |
| [06_ticks_and_unlocking.md](06_ticks_and_unlocking.md) | Sidebar green ticks, form unlocking, "x / 19 forms" |
| [07_ae_sae.md](07_ae_sae.md) | AE detection (41 terms), grading, SAE reports, IEC/CDSCO documents |
| [08_screening_logs_and_consort.md](08_screening_logs_and_consort.md) | Gestation (Inclusion Criteria) Screening Log, Log of All Births, matching, CR-number rules, CONSORT boxes |
| [09_data_integrity_playbook.md](09_data_integrity_playbook.md) | Known failure modes, checks to run, how to investigate and repair |

## Trial site vs training site (PI 2026-10-14)
- **portaltrial.in** holds the real trial data. Only staff of **live sites**
  can save there: `LIVE_SITES` env var on the server (default `PGIMER`;
  comma-separated; `*` = all). Any save/change/delete (POST/PUT/PATCH/DELETE)
  by a user of another site gets **403** "…not enrolling in the trial yet…
  Please use the training site" (`deps.refuse_non_live_site_write`, run inside
  `get_current_user`). Reading, `/auth/*` and global roles (superadmin,
  global_scientist / project_scientist) are never blocked. **Add the site to `LIVE_SITES` on its
  go-live day** (then restart the backend).
- **training.portaltrial.in**: same app, own database `icmr_training`,
  `LIVE_SITES=*`, red "TRAINING SITE" bar. Sites not yet enrolling practise
  there; the Android app has a "Training site" switch on the login screen.
- **Logins (PI 2026-10-29):** the trial site's accounts are the master.
  `backend/training_user_sync.py` (timer `portal-training-user-sync`, every
  10 min) copies every account (password hash, role, site, on/off, contact
  fields) to training and switches off training-only accounts. On training
  (`LOGINS_FROM_TRIAL=1`) password changes and Manage Staff writes get 403
  "change it on portaltrial.in", and the first-login password change is not
  asked (`deps.logins_from_trial`). Found 2026-10-29: passwords differing
  between the sites, two Site PIs missing on training, and six placeholder
  accounts plus the old superadmin `portal_admin` still active there.
- Trial start: `backend/trial_dates.py` `TRIAL_START_DATE` (2026-10-14) —
  CONSORT and Log of All Births alerts count from this date (chapter 08).

## Roles and rights (access hierarchy SOP 1 Oct 2026, PI 2026-10-15)
Enforced on the server (`deps.py`, `pii_service.py`); the UI only mirrors it (`utils/roles.js`).

| Designation | App role | Scope | Edits data | Participant identity | Dashboards / AI / CSV | Audit trail |
| --- | --- | --- | --- | --- | --- | --- |
| Global PI (Nodal / main PI) | `superadmin` | All sites | Yes; also accounts, day reopening | All sites | Yes | All |
| Overall Project Scientist (PRS3-M) | `project_scientist` | All sites | **No** (view only) | All sites, view | Yes | All |
| Technical support (PTS3) | `tech_support` | All sites | No | **None** (`/pii/*` refused, Form C address hidden) | **No** (`/dashboard/*`, report `/document` refused) | All |
| Site PI | `site_pi` | Own site | Yes, incl. delete | Own site | Data quality / site views | Own site |
| Site Scientist (PRS3-NM, PRS2-M) | `site_scientist` | Own site | Yes, incl. delete | Own site | Data quality / site views | No |
| Project Nurse (PN3) | `nurse` | Own site | Yes, **no delete**, no CONSORT | Own site | Data quality only | No |

- Read-only roles (`project_scientist`, `global_scientist`, `tech_support`): every POST/PUT/PATCH/DELETE is refused (403) except `/auth/*`, `/pii/batch` (a read), `/data-queries/`, `/reports/` (running a report is a read; tech support is refused `/reports` outright) and, for analytics roles, `/dashboard/ai-insights` (`deps.refuse_role_restricted_request`, run inside `get_current_user`).
- Trial-wide analytics (CONSORT CSV, safety, baseline, clinical quality, enrolment trend, ops summary, AI Insights) = `CENTRAL_ANALYTICS_ROLES` (Global PI, Overall Project Scientist). Opening the site-scoped views to Site PI / Site Scientist (SOP change 3) is still to do.
- Placeholder roles (`pi`, `scientist`, `deo`, `monitor`) no longer see identity data and are being retired.

## CR number and name rules (PI 2026-10-18)
Enforced by the server on every save where they are entered (Form A, Form B,
Form C, AE form via `pii_service.split_and_store_pii`; Gestation Log; Log of
All Births) — `backend/identity_rules.py`; the pages filter typing the same
way (`utils/maternalUid.js`, `utils/personName.js`, Form A `idFieldRule`).
- CR: PGIMER exactly 12 digits; AMC serial/year (`123/2026`); other sites
  numbers only ("-" or "/" as separators). Blank allowed (CR optional in the
  logs). 422 otherwise.
- Mother's / husband's names: no digits (twins use Birth type / Birth order).
- A value already stored is not re-checked when saved unchanged, so an old
  record with a bad value can still be edited; changing it needs a valid one.
- Consent "Trial run" is retired: removed from the dropdowns, refused on
  save (`main.refuse_trial_run_consent`, 422) and no longer counts as consent
  in `compute_screening_status` (such a record becomes Pending, so Form B is
  refused). A record saved with it opens with consent blank and a notice.

## Report builder (PI 2026-10-24)
`/reports` page, `backend/routers/reports.py`. Pick columns from Forms A–J,
filter (site, tile group such as Randomised, screening dates, trial period
from `TRIAL_START_DATE`), preview 50 rows, download CSV (UTF-8 with BOM, opens
in Excel). One row per Form A; every row starts with site, screening ID,
enrollment number (+ optional Stage). Forms A/B join on `screening_id`, C–J on
`enrollment_id`; if a table has two rows for one baby the latest (highest id)
is used. Day-by-day logs are not offered.
- **Column names** (PI 2026-10-25): the picker shows a plain-English name with
  the variable name in brackets (`backend/report_labels.py`: hand-written
  OVERRIDES, else the variable name with abbreviations expanded). Columns are
  click-to-toggle tiles (no Ctrl). CSV headings: "English (variable)" (default),
  English only, or variable names only (for Stata / R / SPSS).
- **Who**: Global PI and Overall Project Scientist all sites; Site PI and Site
  Scientist own site; nurses and tech support refused.
- **Never offered** (PI: IDs only): any column whose name has the word name /
  contact / phone / mobile / address / email / uid / aadhaar / signature /
  image / photo / pincode / landmark / cr, admission numbers, the
  `pii_service` field lists; and, for blinding, Form I `fio2_0..fio2_10`,
  Form K and Form L. Columns come only from this fixed list (no SQL from the
  browser); an unknown column is a 422.
- Each download is an audit row: action `EXPORT`, table `report`, with the
  columns, filters and row count. Saved reports are kept in the browser only.

## Data queries (Phase 1, PI 2026-10-15)
Fixed checks in `backend/data_checks.py` (catalogue `CHECKS`) find problems
and keep one row per problem in `data_queries`. `run_checks()` opens new
ones, resolves those whose problem has gone, reopens resolved ones that come
back, and leaves "confirmed correct" ones closed unless their facts change.
It runs hourly (`run_data_checks.py`, systemd timer) and on demand
(`POST /data-queries/run`, Global PI). Checks never edit clinical data; facts
and details hold ids, numbers and dates only.
- Age colour from `due_at`: amber after 72 h, red after 7 days. Form
  timeliness checks (Form C / D / E not complete for randomised babies) are
  raised only once 72 h have passed.
- Who (`routers/data_queries.py`): Site PI and Site Scientist their site;
  Global PI and Overall Project Scientist all sites. Nurses and PTS3: none.
- Lifecycle: open → acknowledged → resolved (automatic) or "confirmed
  correct" with a reason. Identity, consent / eligibility and safety checks
  (`second_signoff=True`) need the Overall Project Scientist or Global PI to
  sign off a site's confirmation; they can also reopen it. Every action is
  in the audit log (`table_name='data_queries'`).
- Page: `/data-queries` (`DataQueries.jsx`, CSS prefix `dqy-`); top-bar link
  with the open count (`DataQueriesNavLink.jsx`, red if any is over 7 days);
  dashboard Section 2 Panel 0 (open / amber / red per site).
- "Open entry #N" on a Gestation Log / Log of All Births query opens the log
  at that entry (`/ga-check?entry=N`, `/log-of-all-births?entry=N`,
  `hooks/useEntryFocus.js`): search and filters are cleared, the row is
  scrolled into view and highlighted. Both logs show the entry # column and
  search by name, CR or entry # (`utils/gaCheckSearch.js`).
- Gestation Log entries checked before `TRIAL_START_DATE` raise only the
  "eligible / now eligible, no Form A" queries; their CR-mismatch and
  delivery-not-logged statuses show as "Before trial start" (PI 2026-10-17).
- `FORMA_POSSIBLE_SAME_WOMAN`: two live Form A at one site whose CR numbers
  differ by 1-2 characters (edit distance), with names that do not clearly
  differ and GAs that fit the screening dates (±14 d). Second sign-off.
  Exact CR / hospital-number matches stay with `FORMA_DUPLICATE_ID`.
- Banner on every form (`DataQueryBanner.jsx` in `FormLayout`): open queries
  on the current screening / enrollment id, via `GET /data-queries/for-record`
  (also for nurses, their site; read-only).
- On save: a middleware in `main.py` calls `data_checks_trigger.request_run()`
  after every successful write (except auth, dashboards, users, data queries);
  debounced to one run a minute per worker. `run_checks` takes a Postgres
  advisory lock (`RUN_LOCK_KEY`), so overlapping runs skip. A full run takes
  about 2 s.
- **Daily email** (PI 2026-10-25, `backend/daily_query_email.py`): every day
  at 08:00 IST (`deploy/systemd/portal-daily-query-email.timer`). Site PI and
  Site Scientist get their own site; Project Scientist / Global Scientist and
  the Global PI one all-sites email with a by-site table. Each lists open /
  new (24 h) / red / amber / awaiting sign-off / closed (24 h) counts and the
  new, red and closed queries. **Sent on quiet days too** ("nil to report",
  PI). Runs the checks first. One send per IST day (audit `EMAIL`, table
  `daily_query_email`); `--dry-run` builds without sending, `--only EMAIL`
  sends one test copy (audit `EMAIL_TEST`, does not count). Query text holds
  IDs only, so the email carries no names, CR or phone numbers. Needs
  `SES_SENDER_EMAIL` (trial `.env` only; training never sends). It also
  lists the site summary's **urgent safety items** (W1, W3, W9, W10, below; IDs only).

## Site summary (PI 2026-10-26)

`backend/site_summary.py`, page `/site-summary` (`GET /site-summary`), email
**Monday and Thursday 08:00 IST** (`deploy/systemd/portal-site-summary.timer`),
same recipients as the daily email; nil summaries are sent. Covers
**randomised** babies born since the trial start (Form B `randomised`; PPV
babies who were not randomised are left out), never by arm. The email shows
enrolment IDs only; the page also shows "Baby of <mother>" (or the Form E
baby name) to viewers who may see that site's PII (`can_view_pii_for_site`),
and the mother's name on Form B-missing rows. The W / M codes below are
internal: page and email show only the rule name (PI 2026-10-26).
**Rule-based only, no AI.** Rules approved by the PI (rule sheet
https://claude.ai/artifact/MSSUiC1sRbvQMqN2V6fNmZ ):

| Rule | Fires when |
|---|---|
| W1 Serious AE not reviewed for SAE | AE grade ≥ 3 on the AE form with "Converted to SAE" blank, or auto-detected grade ≥ 3 whose term is not on the AE form |
| W2 Grade going up | a term's grade is higher than at the last live send (grades kept in the audit row, table `site_summary`) |
| W3 Severe brain scan not in Form H | `detect_pending_cranial_usg_findings` (IVH III/IV, cPVL ≥ II) |
| W4 Proven infection | culture-positive sepsis or meningitis starting in the last 7 days |
| W5 Suspected NEC | Helper 4 NEC suspected / stage I in the last 7 days and no stage IIA+ anywhere |
| W6 Grade 2 band | last 3 days: Na 120–129 or 151–160, K 6.5–8.0, AKI stage ≥ 2; last 7 days: glucose 20–40 on ≥ 2 days or any < 20 |
| W7 Escalating support | invasive ventilation (intubated or SIMV/AC/PSV/HFOV) or inotropes started in the last 3 days (previous day logged without it) |
| W8 Acute event | Helper 2 pneumothorax, pulmonary haemorrhage, shock, clinical / EEG seizure in the last 7 days |
| W9 Death without SAE report | died (Form H outcome or Helper 5) and no Form Y report with a diagnosis |
| W10 SAE deadline | SAE list row: 24-h notification blank after the start day; detailed (initial) report blank within 3 days of, or past, start + 14 days |
| M1 / M7 / M8 | existing Dashboard tasks: daily logs ≥ 2 days missing, Form C missing, delivered without Form B |
| M2 Cranial USG | a Form F schedule window (< 28 wk or < 1000 g: Day 1–3, 4–7, 10–14, 28, 36 and 40 wk PMA; else Day 4–7, 10–14, 28, 40 wk PMA) ended 2 days ago with no scan in it (± tolerance), skipping windows after the stay ended |
| M3 | Helper 2 IVH / cPVL flag and no Form F scan |
| M4 ROP | no real Form G visit by DOL 30 (national ROP operational guidelines, RBSK / NPCB), or discharged before one; auto-suggested visit unfilled |
| M5 | Form I 36 / 40 / 44 wk checkpoint date passed with no encounter method or death recorded |
| M6 | Form H or Form I incomplete 48 h after discharge / death (**not Form L**: it is filled after unblinding) |
| M9 | an auto-detected AE whose term is not on the AE form |
| M10 | red data queries (count per site) |

AE-form rows are matched to terms by key, CDISC / MedDRA code ("C154928 |
10082059") or term name (`term_of`), because the AE form's "No." is free
text. Gestation is Form B's (no NBS override). `--dry-run` / `--only` /
`--force` as for the daily email (audit `EMAIL` / `EMAIL_TEST`; a test does
not move the W2 baseline).

## Audit trail for every form (PI 2026-10-26)

`backend/audit_trail.py`: an after_flush listener writes one `audit_log` row
per insert / update / delete on every table except `audit_log`, `screenings`
(Form A is audited by hand in main.py), `data_queries` (system-generated)
and `users`. UPDATE stores only the changed columns, old and new. The user
is the request's login (`deps.get_current_user` sets `db.info["audit_user"]`);
scripts are "system". Identity is never stored: encrypted columns, names,
UIDs, contacts, address, annual number and signature images are written as
"[redacted]"; `participant_pii` keeps only its keys. Bulk `query().update()`
/ `delete()` bypass it (only the legacy `/respiratory-log-bulk`). On only
where `AUDIT_ALL_FORMS=1` is in the backend env file: training from
2026-10-26, trial from 2026-10-28. Before then only Form A, day-log override
unlocks, data queries and emails were audited.

## Glossary

| Term | Meaning |
|---|---|
| **Screening ID** | Form A id, `<site code>-<4 digits>`, e.g. `01-0023`. Issued by the server (`main.generate_screening_id`) only once GA is known and inside 25w0d–31w6d. |
| **Enrollment ID** | Randomised baby id, `<site code>-<blender A–D>-<3 digits>`, e.g. `01-B-123`. **Typed by the nurse on Form B** (no generator); valid format `^\d{2}-[A-D]-\d{3}$` (`baby_uid_duplicate.ENROLLMENT_ID_PATTERN`, `frontend utils/enrollmentId.js`). |
| **NR- id** | `NR-<screening id>`, auto-assigned by the server to a birth that was **not randomised or needed no PPV** (`main.resolve_birth_enrollment_id`). Used as that baby's enrollment id everywhere. |
| **Site code** | PGIMER 01, GMCH 02, IOG 03, AFMC 04, GMCH-A 05, AMC 06 (`main.CANONICAL_SITE_ID_MAP`). |
| **DOB / Day 1** | NICU Day 1 = date of birth. Day N = DOB + (N − 1). Form E also stores a nurse-entered "Day 1 Date" (`nicu_admission.day1_date`), which should equal DOB. |
| **NICU working day** | The current NICU day, where **before 08:00 counts as the previous day** (`frontend utils/datetime.nicuDayNumberFromDay1`, `backend form_completion.nicu_day_today`). Clinical time is **IST** (`backend clinical_time.py`); the server clock is UTC. |
| **PMA checkpoint** | Date the baby reaches 36+0 / 40+0 / 44+0 weeks PMA = DOB + (weeks×7 − GA-at-birth days) (`main._pma_target_date`). |
| **DMS** | Daily Monitoring Sheet (`minimal_monitoring_day_logs`), the bedside scratchpad — was "Helper 1". |
| **Helper 2 / 3 / 4 / 5** | Resp-CV-Neuro daily log / FiO₂ AUC / Infect-GI-Hema daily log / Metab-Renal-Vasc-Eye daily log. **Some backend names still use older numbering** — e.g. `mml_helper5_autofill.py` is Helper 5 today; always check the route, not the name. |
| **Suggestion** | A value the system proposes from other forms. Either fills a blank field (Form H / Form I prefill) or waits for an **Apply** click (BPD, NEC stage, Form L composites, Form G item 18). Never overwrites a saved answer except via an explicit "Force refill". |

## How to use this when data looks wrong

1. Identify the **field** and the **form** it shows on.
2. Look it up in the chapter for that form: it says whether the value is typed, derived, or suggested, and from which source.
3. If derived: check the **source** record(s) named there (the playbook, chapter 09, has read-only queries).
4. If the source is right but the field is wrong: the field was probably **answered before the source existed** (fill-if-blank never overwrites) — use the form's Force refill / Apply, or correct by hand.
5. If the source itself is wrong, go one step further upstream and repeat.
