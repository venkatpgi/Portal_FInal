# 03 — Daily Monitoring Sheet (DMS) and Helpers 2–5

The **DMS** is the bedside scratchpad: nurses log readings as they happen.
The four **Helper** forms are the once-a-day CRF logs. The DMS feeds the
helpers (and, separately, Form H — chapter 04).

## 1. Days and dates

| Concept | Rule | Code |
|---|---|---|
| NICU day | Day 1 = date of birth; Day N = DOB + (N − 1) | `mml_resp_a_autofill.calendar_date_for_nicu_day_from_birth` |
| Working day | before **08:00 IST** = previous day | `clinical_time.py`, `form_completion.nicu_day_today`, frontend `nicuDayNumberFromDay1` |
| DMS sheet date | new readings: today; or **yesterday until 08:00**. Earlier sheets, from the date of birth to the end of stay, open for **corrections only** (edit or remove a saved reading; a save that adds one is refused, 422) until any of that day's Helper 2 / 4 / 5 days is locked (then view only, 403; an active Override & Unlock reopens it) (PI 2026-11-03) | `main._mml_sheet_date`, `dms_sheets.py` (`GET /minimal-monitoring/{id}/sheet-dates`: open / correction / closed + reason) |
| Day of life | from Form B date **and time** of birth: birth to < 24 h = Day 1 of life. Display only: the DMS shows it under the sheet date with a divider row in the hourly tables where it changes; Helpers 2, 4, 5 show it under "Day N" for that 08:00-to-08:00 day (Day 1 from birth). Helper day numbers and DMS dates are unchanged (PI 2026-11-03) | `utils/dayOfLife.js`, `components/helper/DayOfLifeNote.jsx` |
| Helper "today" | the working day; future days are not editable; past days lock | helper pages (`useNicuWorkingDay`) |
| End-of-stay lock | DMS and Helpers 2, 4, 5 take **nothing after the end of stay**: the earliest of the Form H discharge date and the first Helper 5 "did not survive" day (PI 2026-10-31). That day itself stays open. Enforced on the server (422), so an old tablet app cannot get round it; helper pages and the DMS go read-only. `GET /birth-resuscitation/{id}` returns the end as `discharge_date`, plus `died`. Form H outcome Died with no date locks nothing | `stay_end.py`, `get_birth_resuscitation`, helper `setDischargeDay`, DMS `stayClosed` |

**Recording the end of stay (PI 2026-10-31).** "Survived the day" comes late in the day's work, so the DMS has **Record death or discharge** at the top (`POST /enrollment/{id}/end-of-stay`, any site staff): outcome, date, and time for a death. It saves to Form H at once, creating the record if needed, and the logs close. A wrong entry is corrected on Form H. On the day of death the DMS refuses new readings timed after the time of death, and Helper 5 shows "Survived the day" as No until saved. Helper days stay open on the day of death. Entries that got in first raise the data query `LOG_AFTER_STAY_END`; saving "did not survive" warns about later days. A Helper day with nothing entered is refused (422), so no blank row is created.

> **Two different "Day 1" anchors exist.** The DMS read-time overlays use the
> **date of birth** (Form B). The DMS transfusion write-through (§3) and Form I's
> PMA section use **Form E's Day 1 Date** (`nicu_admission.day1_date`). They
> must be the same date; if they differ, readings land on the wrong helper day.

## 2. DMS blocks (`MinimalMonitoringLog.jsx` `BLOCK_META`)

| Block | Content | Feeds |
|---|---|---|
| 5.1.A Vitals | skin/axillary temp, SBP, DBP, MAP (hourly flowsheet) | Helper 5 temperature (#15); Form H lowest SBP/DBP/MAP |
| 5.1.B Fluid bolus | volume | Helper 2 fluid bolus given; Form H fluid bolus count |
| 5.1.C Vasoactive drugs | agent, dose | Helper 2 vasoactive support + drug names (Epinephrine→Adrenaline, Norepinephrine→Noradrenaline, `VASOACTIVE_DRUG_NAME_ALIASES`) |
| 5.1.D PDA medical Rx | agent, dose | Helper 2 PDA medical Rx |
| 5.2.A Respiratory support | time range, modes, max MAP/CPAP, max FiO₂ | Helper 2 #1–5; **FiO₂ AUC prefill** |
| 5.2.B Blood gas | pH, PaO₂, PaCO₂ | Helper 2 #8–10 (day's range) |
| 5.2.C Apnea / desaturation | episode counts | Helper 2 #13–15 (day totals) |
| 5.2.D Postnatal steroids | agent, dose | Helper 2 postnatal steroids |
| 5.3.A Glucose | spot glucose (flowsheet) | Helper 5 #1/#4 lowest/highest; Form H hypo/hyperglycaemia |
| 5.3.B ALP, total Ca, P | lab values | Form H osteopenia labs (ALP peak, lowest Ca/P) |
| 5.4.A Feed volume | EF/NPO, milk type, volume (hourly flowsheet) | Helper 4 NPO, enteral feeds, feed type, cumulative volume, ml/kg/day |
| 5.4.B Direct bilirubin | value | Form H |
| 5.5 Neurological | ventriculomegaly, Doppler | Form H |
| 5.6.A Transfusion | products, count, PRBC volume | Helper 4 PRBC / platelet / FFP-cryo (#28–30) |
| 5.7.A Weight | grams, 12- or 24-hourly | Helper 4 ml/kg/day; **day-on-day weight-change warning** (§5) |

(5.3.C electrolyte block was retired 19-09-2026 — Helper 5's own Na/K/Ca
readings feed Form H.)

**Not required today** (PI 2026-10-20): every block with no reading that day
counts as one open item until it has a reading or the nurse marks it "Not
required today" (test not done / treatment not given). Stored per sheet in
`minimal_monitoring_day_logs.not_required_blocks` (JSON list of block keys,
5.5 = `neuro_a` + `neuro_b`); a block that gets a reading drops out of the
list on the next save. Display only: nothing downstream reads it.

**Tablet readings in flowsheets** (2026-10-21): the app saves a reading with
a time but no `slot_time`; the web files it under the slot its time falls in
(`buildFlowsheetRows`), so it no longer shows as an extra row with its slot
still flagged missing.

**Helper 5 reading times** (pH / Na / K / iCa readings JSON): the tablet's
time was free text until 2026-10-21 (now a 24 h picker); the web normalises
"7:30", "7.30", "7:30 pm" to HH:MM on load (`normalizeReadingTime`), since a
time input shows anything else as blank.

Flowsheets 5.1.A / 5.3.A / 5.4.A: "Log every" 1, 2, 3, 6, 8 or 12 h
(6/8/12 added 2026-10-20); 5.7.A Weight: 12 or 24 h. The cadence only
changes which empty slots are shown, never stored readings.

DMS saves: entries are merged by id, explicit deletes honoured
(`concurrent_writes.merge_mml_entries_json`, chapter 01 §5).

## 3. How the DMS reaches the helpers

There are **three different mechanisms** — knowing which one applies explains
most "why is this value here / not here" questions.

### (a) Read-time overlay — computed on every read, never saved
The server fills the helper day **as it is returned** (`GET` day, `/summary`,
`/records`), in memory only (`db.no_autoflush`, never committed). So the
database row may show blank while the page shows a value.

- **Helper 2** (`main._overlay_resp_cv_from_mml`, module `mml_resp_a_autofill.py`):
  - 5.2.A → support modes (union of the day), respiratory support = Yes,
    endotracheal intubation = Yes if any invasive mode (SIMV/AC/PSV/HFOV),
    max FiO₂, max MAP / CPAP (both when both used).
    **DMS wins** unless the field's "Not Recorded / Not Done" status is set.
  - 5.2.B → pH / PaO₂ / PaCO₂ low–high; 5.2.C → apnea / desaturation /
    severe desaturation totals.
  - 5.1.C / 5.1.D / 5.2.D → the Yes/No presence fields.
- **Helper 5** (`main._overlay_helper5_from_mml`, module `mml_helper5_autofill.py`):
  - lowest glucose = min of readings **< 45 mg/dL**; highest = max of
    readings **> 125 mg/dL**; axillary temperature = min of readings
    < 36.5 °C, else max of readings > 37.5 °C.
  - **Fill-if-blank only** — a typed value is never replaced.
- Both use the DMS sheet dated that calendar day **plus** today's still-open
  sheet (readings logged before the 08:00 rollover).

### (b) Page-side autofill — the page fills its own fields, then saves
- **Helper 4** (`InfectGIHemaLog.jsx`):
  - `applyFeedVolumeFromMml`: cumulative volume = sum of EF-row volumes;
    any EF volume sets **NPO = No** and **Enteral feeds = Yes** (fill-if-blank).
  - `applyFeedTypeFromMml`: feed types = distinct EF milk types (FM/EBM/PDHM).
  - `applyFeedVolumeCalcFromWeight`: **feed volume (ml/kg/day) =
    cumulative volume ÷ weight**, where weight = the latest DMS weight on or
    before that day **if it has regained birth weight, else birth weight**;
    rounded to 0.1. "Force refill" overwrites a stale value.
  - `applyTransfusionFlagsFromMml`: 5.6.A products → #28–30 Yes. A nurse's
    own Yes/No stays; the DMS only clears a Yes it set **in this page session**
    (the marker isn't saved — see PR #49 comment).
- **Helper 5** `applyGlucoseAutofill` mirrors the server overlay on the page.
- **FiO₂ AUC**: "Prefill from DMS" per day converts 5.2.A time ranges into
  (FiO₂, hours) rows split at the 12-h window boundary
  (`utils/mmlRespASync.buildFio2AucRowsFromRespA`); fills empty windows only.

### (c) Write-through on DMS save — actually saved into the helper
- `main._sync_helper3_transfusions_from_minimal_monitoring`: after a DMS save,
  sets Helper 4 transfusion fields to **True** for products in 5.6.A (never
  False; skips locked days unless an override is active). Uses **Form E Day 1
  Date** to find the helper day (none if Day 1 Date is blank).

## 4. Completion % (the day badges and ticks)

Server functions — the pages use the same rules, and page % must equal
server % (fixed 26-09-2026):

| Helper | Function | Notes |
|---|---|---|
| 2 | `main._compute_completion_pct` | respiratory 22 items (+4b when both CPAP and MAP used; weight 2.1 retired 29-09-2026), CV, neuro (cranial-USG items only when USG done) |
| 4 | `main._infect_completion_pct` | GI items conditional on NPO / enteral answers |
| 5 | `main._metab_completion_pct` | AKI and ROP sub-items not counted. #23 ROP screening due and #24 ROP screened are both always asked (#24 no longer hidden when not due, PI 2026-10-20); #25 ROP detected only if screened |

Helpers 2 and 5 are scored **after** the DMS overlay (§3a), so a day can reach
100% from DMS data alone.

## 5. Weight
- Recorded **only** in DMS 5.7.A (Helper 2's 2.1 Weight retired 29-09-2026;
  old values stay in `resp_cv_neuro_day_logs.weight_kg`).
- `GET /minimal-monitoring/{id}/latest-weight-kg/{date}`: most recent DMS
  weight on or before that date (grams ÷ 1000).
- **Weight-change warning** (DMS, advisory): day's last weight vs yesterday's
  last — age < 14 d: > 2% either way; age ≥ 14 d: any loss, or gain ≥ 2%
  (`MinimalMonitoringLog.jsx weightChangeWarning`).

**DMS Edit (PI 2026-11-03).** Each saved reading in a block's Readings table has **Edit**: it opens in the form above ("Editing reading of …", **Done editing**) and saves automatically; the audit trail keeps the old value. The hourly tables (vitals, glucose, feeds, weight) were already editable in place. On an earlier sheet the blank "new reading" form, **Log another reading** and "tap to add" on empty slots are hidden. A sheet remembered from an earlier visit reopens only if it still takes new readings.

## 6. Locking, override, concurrent edits
- **Lock** = `PATCH …/{day}/submit` → `submission_status = submitted`.
  A past day stays editable ("Past day — still editable") until it is locked. Locked days reject edits (403) unless an
  override is active.
- **Override & Unlock** (superadmin only, `main._override_unlock_day`):
  reason ≥ 5 chars, 1–24 h window, recorded on the row
  (`override_unlocked_until`, `override_reason`, `override_by`) and in
  `audit_log`. The page shows "Day N reopened by override …" only while the
  window is active. Re-locking clears the override.
- **Stale write**: Helpers 2/4/5 return 409 if the day changed since it was
  loaded (`concurrent_writes.assert_fresh_write`).

## Location / area of the baby (PI 2026-11-04)

Helper 5 "4.6 Location", Form E "Area of admission" and Form D "Transferred
out on 1st day: Location" use one list (`utils/helperLocation.js`): **DR,
NICU, HDU, Nursery, Transitional nursery, KMC nursery**. Form D has no DR.
Every site stores the same generic area so sites compare like with like. A
site that sends its ward names sees them on the buttons only (PGIMER: DR =
AMCC 1A, NICU = AMCC 4A / 4B, Nursery = AMCC 5A / 5B, Transitional nursery =
AMCC 1C LR nursery, KMC nursery = AMCC 5C); other sites see the area alone
until they send theirs. Earlier labels (Step-down/Nursery, KMC-N, AMCC-…)
are shown as the matching area and saved that way on the next save; any
other saved value (e.g. "Other") stays as an extra button.

## Saved Helper days open in view mode (Harsh 86b5ded; PI 2026-11-04)

A saved Helper 2 / 4 / 5 day that is not locked opens in view mode with
"Edit Day N"; a locked day with a live Override & Unlock opens in edit mode.
DMS values that fill in on their own (Helper 2 fluid bolus and blood gases;
Helper 4 NPO / feeds / feed type / volumes / transfusions; Helper 5 glucose)
are saved quietly when they change on such a day, so the stored day matches
the screen. Locked days are never changed. A day without DMS feed readings
is not filled (a blank DMS volume is no reading, not 0 ml).

## DMS drugs: one drug per row (PI 2026-11-06)

5.1.C vasoactive drugs, 5.1.D PDA agent, 5.2.D postnatal steroids (and 5.6.A
transfusion products) take one choice per reading; two drugs running at
once are two rows. A dose change is a new row of the same drug at the time of
the change; "Stopped at this time" records the end (no dose needed). In the
readings table the latest row of each drug has **Change dose** (new row,
same drug and unit, time now; only the dose to type) and **Stop** (saves a
stopped row). Above the table one line per drug shows the doses over time,
e.g. "Dopamine: 10 → 15 → 20 mcg/kg/min (10:18 · 10:23 · 10:24)". A drug row
with no dose is marked "Dose not entered" (warning only). Vitals (5.1.A) is
its own module on the page (stored block `cv_a` unchanged).
Old readings with more than one choice were split by `backend/dms_split_drugs.py`
(one row each, same date / time / stamps; a dose on a multi-drug reading
stays on the first drug only).
