# 08 — Screening logs, matching and CONSORT

## 1. Gestation (Inclusion Criteria) Screening Log (`ga_check_log`)
Page `GACheckLog.jsx`; API `/ga-check/…`; rules `backend/ga_check.py`.

- One entry per woman whose gestation is checked (antenatal clinic / labour
  triage), **including those who turn out not eligible** — this is the true
  "approached" population (CONSORT Box 1).
- Fields: site, how identified ("Checked at triage" / "Missed — identified
  retrospectively"), mother name, CR number, gestation source
  (Reliable / Unknown-Unreliable), method, weeks/days, found IUFD.
- **Server clean-up** (`main._normalize_ga_check_payload`): source not Reliable →
  method/weeks/days blanked; IUFD → source/method/weeks/days blanked.
- **Eligible** (`ga_check.classify_eligibility`): Reliable **and** 25–31
  completed weeks; not Reliable → unknown (never eligible); outside → No.
- Eligible → "Continue to Form A" (seeds Form A; `screening_id` linked back
  when Form A is saved, `PATCH /ga-check/{id}/link`). "Eligible, no Form A
  yet" list = `GET /ga-check/gap`.
- Entries can be edited (`PUT /ga-check/{id}`); eligibility is recomputed.

## 2. Log of All Births (`birth_log_all_births`)
Page `LogOfAllBirths.jsx`; API `/birth-log/…`; matching `backend/birth_log_matching.py`.

- Every birth at the site, randomised or not (digital version of the paper CRF).
- **Matching** (`birth_log_matching.match_against`), within the site:
  1. CR number match against `participant_pii` (normalised: spaces/dashes
     removed, upper-case) → **`matched`** — the only way to be "matched".
  2. Otherwise a same full-name Form A → **`possible_match`** ("Possible match
     — check CR"), but **only if the GA fits**: Form A GA + days from Form A
     (`created_at`) to the birth must be within **±14 days** of the GA at
     birth (`ga_consistent`). If either GA is missing it is still offered as
     possible. A same-name woman whose GA cannot fit is not linked at all
     (PI 2026-10-14, after several same-name women were linked to the wrong
     Form A). Staff resolve a possible match by correcting the CR on
     whichever record is wrong.
- **Refreshed on read** (`refresh_birth_log_matches`): the birth-log list,
  `/birth-log/alerts` and the CONSORT endpoint re-match every entry of the
  relevant sites against current Form A / Gestation Log data and save any
  change — a match is no longer frozen at the moment the birth was saved.
- Two independent badges:
  - `match_status` (Form A): `matched` / `possible_match` / `in_range_no_match`
    (GA 25w0d–31w6d, no Form A → **"Not filled Form A"**) / `out_of_range` /
    `ga_unknown`.
  - `ga_log_missing`: no Gestation Log entry for her (**"Never Checked GA log"**)
    — only computed when matched or in range.
- "Reason not approached" (+ Other) captured per birth; the "+ Add reason"
  button shows only for `in_range_no_match`.
- `GET /birth-log/alerts` = entries with either badge, plus possible matches.
- CONSORT Box 2 "never checked" still counts only `in_range_no_match` +
  `ga_log_missing`; a possible match is treated as screened until staff
  correct it.

## 3. CR-number rules (both logs, PI 2026-09-28)
- **Optional.** Saved without one → **"CR pending"** badge + count banner
  (`cr_pending`, computed in the list endpoints).
- If typed: PGIMER 12 digits, AMC `serial/year` (`utils/maternalUid.js`).
- **Duplicate** = same site + same normalised CR (Log of All Births: **and same
  date of birth**). Shown under the field; saving needs the tick
  "New contact of the same woman" (Gestation Log) / "This is a genuinely
  separate record" (Log of All Births, edge-case fallback only — see below).
  The server enforces it too (**409**, `cr_duplicates.py`,
  `main._refuse_duplicate_cr`).

### Twin / triplet / quadruplet births (Log of All Births, PI 2026-10-01)
A CR number belongs to the **mother**, so every baby of a multiple birth
genuinely shares it and the same date of birth with its sibling(s) — that is
not a duplicate. Each entry now also records **`multiple_birth_count`**
(1 = singleton, the default) and **`birth_order`** (this baby's position),
chosen via "Birth type" + "This baby is the…" at the top of the Add-a-birth
form — a deliberate, upfront declaration, not a reactive override.
- The duplicate check (`cr_duplicates.find_duplicate`) adds `birth_order` to
  its match key: two entries with the **same** site, CR and date of birth are
  *not* flagged as duplicates when they state a **different** birth order.
  Both sides must state an order for this to apply — a row saved before
  this field existed (`birth_order` NULL) still triggers the old behaviour,
  so an existing genuine duplicate is never silently hidden.
- The generic "This is a genuinely separate record" tick remains as a
  fallback for whatever doesn't fit the structured field (e.g. an unusual
  record-keeping situation), consistent with every other duplicate check
  in the app — never a silent block, always an informed override.
- The table shows the computed label ("Twin — 1st of 2") for a classified
  entry; an *unclassified* entry (`birth_order` NULL) that genuinely shares
  a CR + date of birth with another entry is flagged "Not classified —
  shares CR + DOB" so it's visibly waiting on someone to pick an order.
  An ordinary non-duplicated singleton shows a plain "—", not a warning.
- **4 real twin/triplet pairs (8 rows) existed in the live data before this
  field was added** — left unclassified rather than guessed at (nobody can
  know which twin was born first from the data alone); a nurse fills them
  in via Edit (chapter 09 §9 has the row ids).

## 4. CONSORT (Trial Monitoring dashboard, Section 1)
Code: `backend/routers/dashboard.py`. **Its module docstring is the full,
authoritative definition of every box** — read it before changing any count.
Summary:

| Box | Definition (source) |
|---|---|
| 1 Approached for screening | Gestation Log entries **+** Form A records with no log entry ("orphans") |
| 2 Not approached / not screened | independent computation: never checked (Log of All Births, with its reasons), missed-retrospective, IUFD at screening, checked ≥ 32 wk, checked unreliable |
| 3 Screened for eligibility | all Form A records |
| 4a Did not meet inclusion criteria | Form A GA out of window (legacy — Form A now refuses these) |
| 4b Met exclusion criteria | Form A A4 exclusions (anomaly, hydrops, forego resuscitation, no time to approach for consent, legacy IUFD) |
| 5 Eligible | Form A in window, no exclusion |
| 6 Refused consent | consent No, by refusal reason |
| 7 Consented, not randomised | Form B reason not randomised (dynamic breakdown) + **"vigorous, no PPV needed"** (`required_resuscitation = False`) |
| 8 Randomised | Form B randomised = True |
| 9–11 Followed up at 36 / 40 / 44 wk | expected PMA date passed; + 28-day grace separates lost-to-follow-up from awaiting |

Every row carries a plain-language "where this number comes from" tooltip
(`_row(..., source=...)`).

Invariant the dashboard relies on: **Box 1 ≥ Box 3** (Box 1 − Box 3 = log
entries that never became a Form A).

**Trial start date (PI, 2026-10-14).** The true trial started on
**2026-10-14** (`TRIAL_START_DATE` in `backend/routers/dashboard.py`,
overridable by the env var of the same name). Box 1 and Box 2 count only
Gestation Log entries with `check_date` (else `created_at`) on/after that
date, and Box 2's "never checked" rows only Log of All Births entries with
`date_of_birth` (else `created_at`) on/after it. The logs themselves keep all
their pre-trial entries; only the CONSORT counting is restricted. A Form A
record kept from before the start (a woman still pregnant on 2026-10-14) has
no in-period log entry, so it is counted in Box 1 as an orphan — which is
what keeps Box 1 ≥ Box 3. On the same day all other pre-trial PGIMER Form A
records and everything linked to them were deleted (25 kept); other sites
were left unchanged.
