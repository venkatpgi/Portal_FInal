# 10 — Plausible ranges for typed numbers (PI 2026-11-12)

Approved by the Global PI on 12 Nov 2026 in `PORTAL_value_ranges_review_2026-11-12.xlsx` (17 limits changed from the draft, self-inflating bag PEEP dropped, the rest approved). The table lives in **`backend/range_rules.py` `RULES`** and **`frontend-app/src/utils/valueRanges.js`**; `test_range_rules.test_frontend_table_matches_backend` fails if the two drift apart.

## Two limits per field
| | What happens |
|---|---|
| **Confirm range** | Outside it the value saves. The screen lists it in the "Check these values" panel (bottom right, input outlined amber) and the data query `VALUE_OUT_OF_RANGE` asks the site to correct or confirm it. Clinically abnormal values belong here. |
| **Refuse limit** | Outside it the save is refused (422) with a plain message, on the web and the tablet (server listener). The panel shows it in red as "will not save". |

The server check (`range_rules.install()`, a SQLAlchemy `before_flush` listener) looks only at values typed or changed in this save: a wrong value saved earlier never blocks saving the rest of the record. DMS readings are compared reading by reading; Helper 5 electrolytes reading by reading; text boxes (Helper 2 pH / PaO₂ / PaCO₂ ranges, Helper 5 creatinine) by every number in them. Form D caffeine loading is checked per kg (Form D birth weight, else Form B).

## Table (confirm range / refuse limits)
| Form | Field | Unit | Confirm | Refuse outside |
|---|---|---|---|---|
| B | Birth weight | g | 400–3000 | 300–4000 |
| B | Cord clamping time | s | up to 180 | 0–600 |
| B | SpO₂ at 5 min | % | 40 or more | 0–100 |
| B | Cord pH | | 6.8–7.5 | 6.5–7.8 |
| B | Cord pCO₂ | mmHg | 25–90 | 10–150 |
| B | Cord base excess | mmol/L | −20 to 5 | −30 to 10 |
| B | T-piece PIP / PEEP / flow | cmH₂O, L/min | 12–30 / 4–8 / 4–12 | 5–40 / 3–15 / 1–15 |
| C | Mother's age | years | 16–45 | 12–60 |
| D | FiO₂, max FiO₂ first hour | % | — | 21–100 |
| D | CPAP | cmH₂O | 4–10 | 0–15 |
| D | Surfactant | mg/kg | 100–200 | 50–300 |
| D | Caffeine loading | mg/kg | 10–25 | 5–50 |
| E | Temperatures (DR, skin, axillary) | °C | 35–38 | 25–42 |
| E | FiO₂ (transport, NICU) | % | — | 21–100 |
| E | CPAP, PEEP | cmH₂O | 4–10 | 0–15 |
| E | PIP | cmH₂O | 12–30 | 5–40 |
| E | MAP (HFO) | cmH₂O | 6–18 | 0–30 |
| DMS | Weight | g | — (10% change query) | 300–6000 |
| DMS | Axillary temperature | °C | 35–37.8 | 24–42 |
| DMS | SBP / DBP / MAP | mmHg | 30–90 / 15–60 / 20–60 | 15–140 / 5–100 / 10–100 |
| DMS | Glucose | mg/dL | 20–200 | 5–600 |
| DMS, Helper 2 | pH / PaCO₂ / PaO₂ | , mmHg | 6.8–7.6 / 20–100 / 25–200 | 6.5–7.9 / 10–150 / 10–600 |
| Helper 2 | Max FiO₂ / max flow | %, L/min | — / up to 20 | 21–100 / 0–30 |
| Helper 4 | Feed volume / Hb / peak TSB | ml/kg/d, g/dL, mg/dL | up to 200 / 7–22 / up to 25 | 0–300 / 3–28 / 0–40 |
| Helper 5 | Creatinine | mg/dL | 0.2–2.0 | 0.1–6.0 |
| Helper 5 | Na / K / iCa | mmol/L | 125–155 / 2.5–7.5 / 0.6–1.5 | 100–190 / 1.5–10 / 0.4–2.5 |
| Helper 5 | Urine output | ml/kg/hr | 0.5–6 | above 15 (`value_ranges.py`, chapter 03) |
| H | Discharge weight | g | 1000–4000 | 800–8000 |
| H | Length of stay | days | up to 150 | 0–365 |

## Data queries (`data_checks.py`)
| Check | Raised when | One query per |
|---|---|---|
| `VALUE_OUT_OF_RANGE` | a saved value is outside the confirm range | baby, field and record (DMS / readings: per day, listing the times) |
| `STAY_DAYS_OVER_LOS` | Form H ventilation / CPAP / oxygen / PN days longer than a finished stay | baby |
| `DISCHARGE_WEIGHT_LOW` | discharge weight below birth weight after more than 21 days | baby |
| `DMS_BP_ORDER` | diastolic not below systolic (also refused on save), or mean outside them | baby and DMS day |
| `DMS_WEIGHT_JUMP` | a DMS weight more than 10% from the previous weight | baby |
| `URINE_OUT_OF_RANGE`, `URINE_WINDOW_MISSING` | chapter 03 | |

Facts carry the values only, so a confirmed query stays closed until the value itself changes.

## Screen
`components/RangeWatch.jsx` in `FormLayout` watches typing on every form page: inputs are matched by `name` (Forms B–E, H) or `data-range="<key>"` (DMS flowsheet and blood gas, Helpers 2, 4, 5). Values loaded from the server are left to the data queries. The older per-form checks were aligned to the refuse limits (Form D CPAP / surfactant / FiO₂, Form E temperatures and ventilator settings, Form H discharge weight, DMS and Helper 2 blood gases, Helper 4).
