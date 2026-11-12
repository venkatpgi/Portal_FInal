"""Generate PORTAL CRF clinical-formula PDF."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "calibrii.ttf")))
F, FB, FI = "Body", "Body-Bold", "Body-Italic"

OUT = Path(__file__).with_name("PORTAL_CRF_Formulas.pdf")
NAVY = colors.HexColor("#1e3a5f")
TEAL = colors.HexColor("#0f5c6b")
HEAD_BG = colors.HexColor("#1e3a5f")
ROW_ALT = colors.HexColor("#f4f7fa")
RULE = colors.HexColor("#c5d0dc")
AMBER = colors.HexColor("#92400e")


def styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle(
            "cover", parent=base["Title"], fontName=FB,
            fontSize=20, leading=24, textColor=NAVY, alignment=TA_CENTER, spaceAfter=6,
        ),
        "sub": ParagraphStyle(
            "sub", parent=base["Normal"], fontName=F,
            fontSize=11, leading=14, textColor=TEAL, alignment=TA_CENTER, spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], fontName=F,
            fontSize=9, leading=12, textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER, spaceAfter=10,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName=F,
            fontSize=9, leading=12.5, textColor=colors.HexColor("#1e293b"), spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName=FB,
            fontSize=13, leading=16, textColor=NAVY, spaceBefore=12, spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontName=FI,
            fontSize=8.5, leading=11.5, textColor=colors.HexColor("#475569"), spaceAfter=8,
        ),
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontName=FB,
            fontSize=8, leading=10, textColor=colors.white, alignment=TA_LEFT,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontName=F,
            fontSize=8, leading=10.5, textColor=colors.HexColor("#0f172a"),
        ),
        "cellb": ParagraphStyle(
            "cellb", parent=base["Normal"], fontName=FB,
            fontSize=8, leading=10.5, textColor=colors.HexColor("#0f172a"),
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName=F,
            fontSize=8, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER,
        ),
    }


S = styles()


def P(text, style="cell"):
    return Paragraph(str(text).replace("\n", "<br/>"), S[style])


def form_table(rows):
    header = [
        P("Screen field", "th"),
        P("Stored / API field", "th"),
        P("Formula", "th"),
    ]
    data = [header]
    for field, key, formula in rows:
        data.append([P(field, "cellb"), P(key), P(formula)])
    col_w = [48 * mm, 42 * mm, 90 * mm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(cmds))
    return t


def section(title, intro, rows):
    bits = [Paragraph(title, S["h1"])]
    if intro:
        bits.append(Paragraph(intro, S["note"]))
    bits.append(form_table(rows))
    bits.append(Spacer(1, 4))
    return KeepTogether(bits)


# (screen field, api key, formula)
FORMS = [
    (
        "Form A — Screening",
        "Nurses enter best gestational age. EDD is still derived from LMP when LMP is present. Same on web and tablet.",
        [
            (
                "2 (b). EDD",
                "expected_delivery_date",
                "Naegele: EDD = LMP + 1 year − 3 months + 7 days. Not LMP + 280 days (that is 1–2 days early when the 9-month span has extra 31-day months).",
            ),
            (
                "LMP from EDD (if only EDD is known)",
                "lmp_date",
                "Inverse Naegele: LMP = EDD − 1 year + 3 months − 7 days.",
            ),
            (
                "1 (a) / 1 (b). Best estimate of GA",
                "gestation_weeks, gestation_days",
                "If checking against LMP: completed weeks = floor(calendar days from LMP to screening date / 7); days = remainder. Direct entry of weeks+days is the live path.",
            ),
            (
                "Eligibility window",
                "—",
                "Best GA must be 25+0 to 31+6 weeks. Screening ID is assigned only inside this window.",
            ),
        ],
    ),
    (
        "Form B — Birth and resuscitation",
        "Weight is stored in grams. Centile uses Male/Female only; if sex is DSD the chart uses designated gender.",
        [
            (
                "Gestation at randomisation (weeks + days)",
                "gestation_rand_weeks, gestation_rand_days",
                "Screening GA in days (weeks × 7 + days) + calendar days from screening date to date of birth. Then weeks = floor(total / 7), days = remainder. Never negative.",
            ),
            (
                "16. Intrauterine growth status (centile)",
                "intrauterine_centile",
                "INTERGROWTH-21st Very Preterm birthweight tables (Villar et al., Lancet 2016), 24+0 to 32+6 weeks, Male/Female. Birth weight kg is compared with the published 3rd, 5th, 10th, 50th, 90th, 95th, 97th kg for that exact week+day (no interpolation). Stores the lower published point (3, 5, 10, 50, 90, 95, 97) or “&lt;3rd centile”. Outside the chart, the nurse types it.",
            ),
            (
                "26. Strata (if randomised Yes)",
                "strata",
                "If GA at randomisation &lt; 28+0 weeks → “&lt; 28 weeks”. Else → “≥ 28 – 31 weeks”.",
            ),
            (
                "44. Cord clamp elapsed seconds",
                "cord_clamp_time",
                "Seconds from time of birth (clock) to cord-clamp clock, wrapping midnight. Allowed 0–300 seconds.",
            ),
            (
                "43. Cord clamp clock",
                "cord_clamp_timestamp",
                "Time of birth + elapsed seconds, wrapped to 24 hours. Auto-filled when elapsed seconds are typed.",
            ),
        ],
    ),
    (
        "Form C — Maternal details",
        "Triple I does not use foul-smelling liquor. Steroid courses are counted from doses given.",
        [
            (
                "Triple I",
                "triple_i",
                "If maternal fever = No → No. If fever = Yes: Yes when at least 2 of these 4 are Yes — fetal tachycardia, maternal TLC high, maternal tachycardia, abdominal tenderness. If all 4 are answered and fewer than 2 are Yes → No. Unresolved while those 4 are incomplete.",
            ),
            (
                "22. Antenatal steroid course status",
                "derived from beta/dexa doses",
                "Betamethasone: 1 course = 2 doses. Dexamethasone: 1 course = 4 doses. Status = Complete only when doses &gt; 0 and doses divide evenly by doses-per-course; else Incomplete.",
            ),
            (
                "23. Number of completed courses",
                "derived",
                "floor(doses given / doses per course) for that drug.",
            ),
            (
                "MgSO4 gestation (weeks + days)",
                "mgso4_gestation_weeks, mgso4_gestation_days",
                "Preferred: GA at birth in days − (date of birth − MgSO4 date) in calendar days. If birth GA is missing: calendar days from LMP to MgSO4 date. Then weeks = floor(/7), days = remainder. Cleared if result is outside 0–314 days.",
            ),
            (
                "LMP / EDD (autofill from Form A)",
                "lmp, edd",
                "Same Naegele pair as Form A. Stored LMP/EDD first; missing one is completed from the other; if both missing, derived from screening GA + screening date.",
            ),
        ],
    ),
    (
        "Form D — Postnatal day 1",
        "Caffeine loading is a single mg/kg dose. Maintenance is total mg/kg/day (not split by OD/BD).",
        [
            (
                "3. Growth status",
                "growth_status",
                "From Form B intrauterine_centile (or recalculated INTERGROWTH if NBS GA is used): &lt;10th centile → SGA; 10th–90th → AGA; &gt;90th → LGA.",
            ),
            (
                "3 (a). SGA centile (if SGA)",
                "sga_centile",
                "“&lt;3rd” if centile is “&lt;3rd centile” or numeric &lt; 3. “&lt;10th” if numeric ≥ 3 and &lt; 10.",
            ),
            (
                "16 (c). Caffeine loading dose (mg/kg)",
                "display from caffeine_loading_abs; caffeine_dose also stored",
                "mg/kg = absolute mg ÷ (birth_weight grams ÷ 1000). Typical 20 mg/kg. Soft warn if outside 10–25 mg/kg.",
            ),
            (
                "Typical loading amount (hint)",
                "—",
                "20 × birth weight in kg (mg).",
            ),
            (
                "16 (f). Caffeine maintenance (mg/kg/day)",
                "display from caffeine_maint_abs",
                "mg/kg/day = absolute mg ÷ birth weight kg. Soft warn if outside 5–10 mg/kg/day.",
            ),
            (
                "Effective GA for later forms",
                "Form B gestation_weeks overlay / Form D NBS",
                "If Form D method is NBS and |NBS days − Form B days| &gt; 14, Forms F–K and helpers use the NBS GA. Form B itself keeps the original screening/birth GA.",
            ),
            (
                "13. Surfactant dose (mg/kg)",
                "surfactant_dose",
                "Entered as mg/kg (not calculated). Soft warn outside 50–200 mg/kg.",
            ),
        ],
    ),
    (
        "Form E — NICU admission",
        "Age uses both date and time of birth and of admission.",
        [
            (
                "Age at admission (hours)",
                "age_at_admission_hours",
                "floor( (admission datetime − birth datetime) in minutes / 60 ). Empty if admission is before birth.",
            ),
            (
                "Age at admission (total minutes)",
                "age_at_admission_minutes",
                "floor( (admission datetime − birth datetime) in milliseconds / 60 000 ). This is total minutes, not the remainder after hours. Displayed as “H hr M min” = floor(minutes/60) hr and minutes % 60.",
            ),
        ],
    ),
    (
        "Form F — Cranial USG",
        "DOL is 1-indexed: the calendar day of birth is DOL 1. PMA adds completed postnatal days (DOL − 1).",
        [
            (
                "Day of life (each scan)",
                "dol",
                "DOL = (scan date − date of birth) in calendar days + 1.",
            ),
            (
                "PMA (each scan)",
                "pma_weeks / pma_days (shown as W+D wks)",
                "PMA days = (GA weeks × 7 + GA days) + (DOL − 1). PMA weeks = floor(PMA days / 7); PMA days = remainder.",
            ),
        ],
    ),
    (
        "Form G — ROP screening",
        "Same DOL/PMA arithmetic as Form F (birth day = DOL 1).",
        [
            (
                "DOL at screening",
                "dol",
                "DOL = (screening date − date of birth) in days + 1.",
            ),
            (
                "PMA at screening",
                "pma",
                "PMA days = GA days at birth + (screening date − DOB). Shown as “Ww Dd”.",
            ),
            (
                "PMA at treatment / other event",
                "derived",
                "Same as screening PMA, using that event’s date instead of the screening date.",
            ),
        ],
    ),
    (
        "Form H — Neonatal morbidities",
        "BPD is a suggestion only. The clinician applies Yes/No and grade on Form H. Assessment day is 36+0 weeks PMA.",
        [
            (
                "36+0 PMA date (BPD assessment day)",
                "—",
                "Date = date of birth + (252 − GA days at birth) days. 252 = 36 weeks.",
            ),
            (
                "35–37. BPD / support / grade (Jensen 2019 suggestion)",
                "bpd, bpd_support_36w, bpd_grade",
                "From Helper 2 (or Form J 36-week visit if already left): room air → No BPD. NC ≤ 2 L/min → Grade 1. NC &gt; 2 L/min, HFNC, CPAP or NIPPV → Grade 2. Intubated or SIMV / A-C / PSV / HFOV → Grade 3. Died before 36+0 → no suggestion. Still in NICU → Helper 2 that day (±1 if missing). Discharged/LAMA before 36+0 → Form J 36-week visit, else last Helper 2 day. Back-referred → Form J 36-week visit only.",
            ),
            (
                "PMA checkpoint dates (36 / 40 / 44 weeks) for Form I prefill",
                "target_date",
                "Date = Day 1 Date + (target PMA weeks × 7 − GA days at birth).",
            ),
        ],
    ),
    (
        "Form I — Study outcomes",
        "One death is copied across Yes sections. Age uses times when both birth and death times are known.",
        [
            (
                "Age at death — 7-day mortality",
                "mortality_7d_age_hrs",
                "Round( (death − birth) in hours ). Uses time of birth and time of death when both are present; otherwise dates only at 00:00.",
            ),
            (
                "Age at death — other mortality places",
                "mortality_28d_age_days, death36_age_days, death40_age_days, death44_age_days, mortality_hospital_age_days, mortality_after_discharge_age_days",
                "floor( (death − birth) in hours / 24 ).",
            ),
            (
                "36 / 40 / 44 week PMA checkpoint date",
                "target_date (prefill)",
                "Same as Form H: Day 1 Date + (checkpoint weeks × 7 − GA days at birth).",
            ),
        ],
    ),
    (
        "Form J — External hospital outcomes",
        "36-week visit respiratory fields also feed the Form H BPD suggestion.",
        [
            (
                "Visit / assessment calendar date",
                "from assessment_weeks",
                "PMA target date = Day 1 Date + (assessment weeks × 7 − GA days at birth).",
            ),
            (
                "36-week BPD grading (via Form H suggestion)",
                "resp_support, resp_mode, flow_rate",
                "No support → No BPD. IMV → Grade 3. CPAP/NIPPV → Grade 2. Nasal cannula: Grade 1 if flow ≤ 2 L/min, Grade 2 if flow &gt; 2.",
            ),
        ],
    ),
    (
        "Form K — MRI brain",
        "PMA at MRI uses completed postnatal days (MRI date − DOB), not DOL+1.",
        [
            (
                "PMA at MRI (weeks + days)",
                "pma_weeks, pma_days",
                "Postnatal days = MRI date − date of birth. PMA days = GA days at birth + postnatal days. Weeks = floor(/7), days = remainder. Empty if MRI is before birth.",
            ),
        ],
    ),
    (
        "Daily Monitoring Sheet (DMS)",
        "Web and tablet. Slot frequency is chosen by the nurse (usually 2 h). Unlogged slots are not treated as NPO or as feeds.",
        [
            (
                "GI total volume (ml)",
                "summary (not a stored CRF field)",
                "Sum of volume_ml on slots marked EF (enteral feed).",
            ),
            (
                "Volume by milk type",
                "summary",
                "Same sum, split by FM / EBM / PDHM.",
            ),
            (
                "EF hours / NPO hours",
                "summary",
                "Count of EF (or NPO) slots × feed-log frequency hours.",
            ),
            (
                "5.7.A Weight used downstream",
                "growth_a.weight_g → kg",
                "Latest weight on/before the helper calendar day, as kg = grams ÷ 1000. Helpers only switch from birth weight to this value once it is ≥ birth weight.",
            ),
            (
                "Day of life divider on the sheet",
                "display",
                "Day of life = floor( (clock − birth datetime) / 24 h ) + 1. The sheet shows when DOL ticks over on that calendar date.",
            ),
        ],
    ),
    (
        "Shared helper calendar (Helpers 2–5 and DMS)",
        "Day 1 Date is date of birth. Before 08:00 local, the NICU “working day” is still yesterday.",
        [
            (
                "NICU day number (“today”)",
                "nicu_day",
                "Working date = calendar today, minus 1 day if local hour &lt; 08:00. NICU day = (working date − Day 1 Date) in days + 1, minimum 1.",
            ),
            (
                "Calendar date for NICU day N",
                "—",
                "Day 1 Date + (N − 1) days.",
            ),
            (
                "Day of life (display on helpers)",
                "—",
                "Birth to &lt;24 h = Day 1 of life; 24–48 h = Day 2; and so on. Helper tab numbers stay calendar-based (Day 1 = date of birth).",
            ),
        ],
    ),
    (
        "Helper 2 — Resp / CV / Neuro  (tablet: Helper 2)",
        "MAP vs CPAP which box to show is derived from the support modes. Values themselves are typed.",
        [
            (
                "4. Max MAP or Max CPAP (which field)",
                "map_cpap / map_cpap_secondary",
                "From selected modes: NC/HFNC only → field N/A. CPAP only → CPAP. Pressure modes (NIPPV, SIMV, A/C, PSV, HFOV) → MAP. CPAP + a pressure mode → MAP plus 4 (b) CPAP.",
            ),
        ],
    ),
    (
        "Helper 3 — FiO2 logging  (web Helper 3; not a tablet CRF calculator)",
        "AUC uses fraction of inspired oxygen, not the percent number raw.",
        [
            (
                "Row AUC",
                "derived per row",
                "AUC = (FiO2 percent ÷ 100) × duration hours.",
            ),
            (
                "Window AUC (each 12 h block)",
                "derived",
                "Sum of row AUCs in that window.",
            ),
            (
                "Day AUC",
                "derived",
                "Window 1 AUC + Window 2 AUC.",
            ),
            (
                "Grand total AUC",
                "derived",
                "Sum of day AUCs across logged days. Days with Helper 2 Supplemental O2 = Yes need both 12 h windows filled.",
            ),
        ],
    ),
    (
        "Helper 4 — Infect / GI / Hema  (tablet: Helper 3)",
        "Feed volume is ml/kg/day from cumulative millilitres, not a typed rate.",
        [
            (
                "Effective weight (kg)",
                "used for #15; not the nurse-typed field",
                "Latest DMS 5.7.A weight (kg) on/before this NICU day, but only if it is ≥ birth weight kg. Until then (normal postnatal loss) use Form B birth_weight ÷ 1000. If only one of the two exists, use that one.",
            ),
            (
                "15. Feed volume (ml/kg/d)",
                "feed_volume",
                "cumulative_feed_volume (ml) ÷ effective weight kg, rounded to 1 decimal.",
            ),
        ],
    ),
    (
        "Helper 5 — Metab / Renal / Eye  (tablet: Helper 4)",
        "Nurses type millilitres per urine window. The rate and the daily total are ml/kg/hr. Same weight rule as Helper 4 feeds. PI 2026-11-11.",
        [
            (
                "Effective weight (kg)",
                "urine_effective_weight_kg",
                "Same as Helper 4: DMS 5.7.A kg if recovered to/past birth kg, else birth weight kg.",
            ),
            (
                "8am–2pm urine rate (display)",
                "from urine_output_8am_2pm (ml)",
                "ml/kg/hr = ml ÷ (kg × 6 hours), 2 decimals.",
            ),
            (
                "2pm–8pm urine rate (display)",
                "from urine_output_2pm_8pm (ml)",
                "ml/kg/hr = ml ÷ (kg × 6 hours), 2 decimals.",
            ),
            (
                "8pm–8am urine rate (display)",
                "from urine_output_8pm_8am (ml)",
                "ml/kg/hr = ml ÷ (kg × 12 hours), 2 decimals.",
            ),
            (
                "Urine output total",
                "urine_output_total",
                "ml/kg/hr over recorded windows only: (sum of typed ml) ÷ (kg × hours of those windows). Blank or Not Recorded windows are skipped. Worked out on the server on save.",
            ),
            (
                "Window range (PI 2026-11-11)",
                "—",
                "A typed window &gt; 15 ml/kg/hr is refused (HTTP 422) and will not save. Above 6 or below 0.5 ml/kg/hr is allowed but raises Data queries URINE_OUT_OF_RANGE (one per window). A blank window with no status, 24 h after the day, raises URINE_WINDOW_MISSING.",
            ),
            (
                "1. Lowest glucose",
                "lowest_glucose",
                "From DMS 5.3.A readings: minimum of values &lt; 45 mg/dL. If none low → “Not Low”. If no readings → “Not Tested”.",
            ),
            (
                "2. Hypoglycaemia episodes",
                "hypoglycemia_episodes",
                "Count of DMS glucose readings &lt; 45 mg/dL.",
            ),
            (
                "4. Highest glucose",
                "highest_glucose",
                "Maximum of DMS readings &gt; 125 mg/dL. If none high → “Not High”. Insulin follow-up is asked when this is a number &gt; 125.",
            ),
            (
                "6. Metabolic acidosis",
                "metabolic_acidosis",
                "Yes if any pH reading &lt; 7.2. No if every recorded pH is ≥ 7.2. Empty if no numeric pH.",
            ),
        ],
    ),
]


def add_page_bits(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont(F, 8)
    canvas.drawString(18 * mm, A4[1] - 8 * mm, "PORTAL Trial  |  Clinical formulas by form")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 8 * mm, "Web and tablet")
    canvas.setFillColor(colors.HexColor("#e2e8f0"))
    canvas.rect(0, 0, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.setFont(F, 8)
    canvas.drawString(18 * mm, 5 * mm, "Generated 12 November 2026 from live CRF code")
    canvas.drawRightString(A4[0] - 18 * mm, 5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="PORTAL Trial — Clinical formulas by form",
        author="PORTAL Trial",
    )
    story = [
        Spacer(1, 8 * mm),
        Paragraph("PORTAL Trial", S["sub"]),
        Paragraph("Clinical formulas used in the CRFs", S["cover"]),
        Paragraph(
            "Field name, stored key, and the equation  |  12 November 2026",
            S["meta"],
        ),
        Paragraph(
            "This list is the <b>calculated</b> fields only — values the screen works out, "
            "not every typed number. Web and tablet use the same equations. "
            "Tablet Helper 3 is web Helper 4 (Infect / GI / Hema). "
            "Tablet Helper 4 is web Helper 5 (Metab / Renal / Eye). "
            "Database keys are not renamed.",
            S["body"],
        ),
        Paragraph(
            "Weight in formulas is always kilograms (birth_weight grams ÷ 1000, or DMS 5.7.A grams ÷ 1000). "
            "Day of life on scans is 1-indexed (birth calendar day = DOL 1). "
            "Forms AE, Y, SAE listing and Form L have no clinical calculators.",
            S["body"],
        ),
    ]
    for title, intro, rows in FORMS:
        story.append(section(title, intro, rows))
    story.append(PageBreak())
    story.append(Paragraph("Quick copy of the weight and time building blocks", S["h1"]))
    story.append(Paragraph(
        "These sit under several forms. They are listed once here so the per-form tables stay short.",
        S["note"],
    ))
    story.append(form_table([
        (
            "Grams → kilograms",
            "birth_weight, growth_a.weight_g",
            "kg = grams ÷ 1000.",
        ),
        (
            "GA as total days",
            "gestation_weeks, gestation_days",
            "days = weeks × 7 + days (0–6).",
        ),
        (
            "PMA date for a target week",
            "used by Forms H, I, J, K",
            "date = Day 1 Date (DOB) + (target weeks × 7 − GA days at birth).",
        ),
        (
            "PMA weeks+days on a given date",
            "Forms F, G, K",
            "PMA days = GA days at birth + (event date − DOB) in days. For DOL-based screens, postnatal days = DOL − 1. Then weeks = floor(/7), leftover days = remainder.",
        ),
        (
            "Effective weight for feeds and urine",
            "Helpers 4 and 5",
            "Use DMS 5.7.A kg on/before the day if it is ≥ birth kg; otherwise birth kg. Physiological weight loss must not inflate ml/kg.",
        ),
        (
            "Urine ml/kg/hr",
            "Helper 5 windows and total",
            "rate = volume_ml ÷ (effective kg × hours). 8am–2pm and 2pm–8pm = 6 h; 8pm–8am = 12 h; daily total uses only the hours that were actually recorded.",
        ),
    ]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Source in code (for developers): frontend-app/src/utils/datetime.js, caffeineDose.js, "
        "gestation.js, dayOfLife.js, deathDetails.js, mmlHelperSync.js, data/intergrowthVeryPreterm.js; "
        "backend/value_ranges.py, bpd_suggestion.py, main.py _pma_target_date; "
        "tablet lib/utils/mml_helper_linkages.dart and matching form screens.",
        S["note"],
    ))
    doc.build(story, onFirstPage=add_page_bits, onLaterPages=add_page_bits)
    print(OUT)


if __name__ == "__main__":
    build()
