"""AE candidates for one baby: every ae_reference detector over Helpers 2/4/5,
Forms D, F, H and I. Shared by GET /adverse-events/candidates/{id} (the AE
form's "Scan" button) and the site summary, so both see the same episodes.
"""
from ae_reference import (
    detect_metab_renal_vasc_eye_candidates,
    detect_form_h_morbidity_candidates,
    detect_infection_candidates,
    detect_form_h_heme_candidates,
    detect_pending_cranial_usg_findings,
    detect_form_h_neuro_seizure_candidates,
    detect_form_h_cv_shock_candidates,
    detect_resp_misc_candidates,
    detect_domain8_candidates,
)
from infection_windows import _compute_infection_windows
from models import (CranialUSGRecord, InfectGIHemaDayLog, MetabRenalVascEyeDayLog, NeonatalMorbidities,
                    NICUAdmission, PostnatalDay1, RespCVNeuroDayLog, StudyOutcomes)


def collect_ae_candidates(db, enrollment_id):
    logs = (
        db.query(MetabRenalVascEyeDayLog)
        .filter(MetabRenalVascEyeDayLog.enrollment_id == enrollment_id)
        .all()
    )
    nm = (
        db.query(NeonatalMorbidities)
        .filter(NeonatalMorbidities.enrollment_id == enrollment_id)
        .first()
    )
    inf_logs = (
        db.query(InfectGIHemaDayLog)
        .filter(InfectGIHemaDayLog.enrollment_id == enrollment_id)
        .order_by(InfectGIHemaDayLog.nicu_day)
        .all()
    )
    resp_logs = (
        db.query(RespCVNeuroDayLog)
        .filter(RespCVNeuroDayLog.enrollment_id == enrollment_id)
        .order_by(RespCVNeuroDayLog.nicu_day)
        .all()
    )
    cranial_usg_record = (
        db.query(CranialUSGRecord)
        .filter(CranialUSGRecord.enrollment_id == enrollment_id)
        .first()
    )
    postnatal = (
        db.query(PostnatalDay1)
        .filter(PostnatalDay1.enrollment_id == enrollment_id)
        .first()
    )
    outcomes = (
        db.query(StudyOutcomes)
        .filter(StudyOutcomes.enrollment_id == enrollment_id)
        .order_by(StudyOutcomes.id.desc())
        .first()
    )
    if (not logs and nm is None and not inf_logs and not resp_logs and not cranial_usg_record
            and postnatal is None and outcomes is None):
        return {"has_data": False, "candidates": [], "pending_cranial_usg_findings": []}

    nicu = (
        db.query(NICUAdmission)
        .filter(NICUAdmission.enrollment_id == enrollment_id)
        .first()
    )
    day1_date = nicu.day1_date if nicu else None

    candidates = []
    if logs:
        candidates += detect_metab_renal_vasc_eye_candidates(logs, day1_date=day1_date)
    candidates += detect_form_h_morbidity_candidates(nm, day1_date=day1_date)
    infection_windows = _compute_infection_windows(inf_logs, nicu) if inf_logs else []
    candidates += detect_infection_candidates(nm, infection_windows, day1_date=day1_date)
    candidates += detect_form_h_heme_candidates(nm, inf_logs, day1_date=day1_date)
    candidates += detect_form_h_neuro_seizure_candidates(nm, day1_date=day1_date)
    candidates += detect_form_h_cv_shock_candidates(nm, resp_logs, day1_date=day1_date)
    candidates += detect_resp_misc_candidates(nm, resp_logs, inf_logs, logs, day1_date=day1_date)
    candidates += detect_domain8_candidates(nm, postnatal, outcomes, resp_logs, inf_logs, logs,
                                            day1_date=day1_date)
    pending_cranial_usg_findings = detect_pending_cranial_usg_findings(cranial_usg_record, nm)
    return {
        "has_data": True,
        "candidates": candidates,
        "pending_cranial_usg_findings": pending_cranial_usg_findings,
    }
