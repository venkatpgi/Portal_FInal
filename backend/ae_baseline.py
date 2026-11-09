"""Literature baseline for the monthly AE summary (PI 2026-11-09: IEC and
DSMB monthly, pooled, compared with the expected frequency in this
population). DRAFT until the PI approves it: set APPROVED = True then.

Each value is quoted from the source's abstract with its population; none is
adjusted to PORTAL's 25+0 to 31+6 weeks. Terms not listed here show "not yet
sourced" in the report rather than a guess. Keys are ae_reference slugs, plus
"death".
"""

APPROVED = False

SOURCES = {
    "V26": ("Vardhelli V, Vadije PR, Kishore Kumar R, Venkatesh V, Kasaragod AB. In-hospital outcomes of very "
            "preterm and very low birth weight neonates: a multicenter retrospective study from India. "
            "Indian Pediatr 2026. doi:10.1007/s13312-026-00289-5 (PMID 41729383)",
            "India, 14 tertiary units, 2018-2022; 1691 very preterm 24+0 to 31+6 wk, mean GA 29 wk"),
    "S10": ("Stoll BJ, Hansen NI, Bell EF, et al. Neonatal outcomes of extremely preterm infants from the NICHD "
            "Neonatal Research Network. Pediatrics 2010;126:443-456. doi:10.1542/peds.2009-2959",
            "USA, NICHD NRN, 2003-2007; 9575 infants 22-28 wk (more immature than PORTAL)"),
    "D16": ("Investigators of the Delhi Neonatal Infection Study (DeNIS) collaboration. Characterisation and "
            "antimicrobial resistance of sepsis pathogens in neonates born in tertiary care centres in Delhi, "
            "India: a cohort study. Lancet Glob Health 2016;4:e752-60. doi:10.1016/S2214-109X(16)30148-6",
            "India, 3 Delhi centres, 2011-2014; 13 530 inborn NICU admissions of all gestations"),
    "E15": ("Ancel PY, Goffinet F; EPIPAGE-2 Writing Group. Survival and morbidity of preterm children born at 22 "
            "through 34 weeks' gestation in France in 2011: results of the EPIPAGE-2 cohort study. "
            "JAMA Pediatr 2015;169:230-238. doi:10.1001/jamapediatrics.2014.3351",
            "France, national population cohort, 2011; 3257 births at 27-31 wk"),
    "J19": ("Jain K, Sankar MJ, Nangia S, et al. Causes of death in preterm neonates (<33 weeks) born in tertiary "
            "care hospitals in India: analysis of three large prospective multicentric cohorts. "
            "J Perinatol 2019;39:13-19. doi:10.1038/s41372-019-0471-1",
            "India, NNPD + DeNIS + GLSE-Plus cohorts; 8024 preterm <33 wk admitted to NICUs"),
}

BASELINE = {
    "death": "Survival to discharge 87.8% (31 wk 97.7%, 28 wk 89.8%, 25 wk 51%) [V26]; 93.6% at 27-31 wk [E15]; "
             "sepsis caused 20-40% of deaths <33 wk in Indian NICUs [J19]",
    "bpd": "4.0% [V26]; oxygen at 36 wk 42% in 22-28 wk [S10]",
    "ivh": "Grade 3 or more 2.4% [V26]; severe IVH 16% in 22-28 wk [S10]",
    "pvl": "Cystic PVL 0.9% [V26]",
    "rop": "Needing treatment 5.1% [V26]",
    "nec": "11% in 22-28 wk [S10]; no Indian very preterm figure sourced yet",
    "pda": "46% in 22-28 wk [S10]",
    "rds": "93% in 22-28 wk [S10]",
    "sepsis_culture_positive": "Late-onset sepsis 36% in 22-28 wk [S10]; culture-positive sepsis 6.2% of all inborn "
                               "NICU admissions, any gestation [D16]",
    "sepsis_culture_negative": "Any sepsis 14.3% of all inborn NICU admissions, any gestation [D16]",
}

NOT_SOURCED = "not yet sourced"


def baseline(slug: str) -> str:
    return BASELINE.get(slug, NOT_SOURCED)
