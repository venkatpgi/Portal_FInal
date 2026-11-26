"""GET /followup-list: the Follow-up list page (followup_list.py, PI 2026-11-25).

All staff: site staff (nurses, scientists, Site PI) their own site; Global PI,
Project Scientist and Global Scientist any or all sites. Each row carries the
baby's name only when the viewer may see that site's PII.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from clinical_time import clinical_today
from db import get_db
from deps import get_current_user
from models import BirthResuscitation, User
from pii_service import can_view_pii_for_site
from routers.reports import ALL_SITES, CENTRAL
import followup_list

router = APIRouter(prefix="/followup-list", tags=["Follow-up list"])


def _sites(user: User, site: str | None) -> list[str]:
    role = (user.role or "").lower()
    if role in CENTRAL:
        if site:
            if site not in ALL_SITES:
                raise HTTPException(status_code=422, detail=f"Unknown site {site!r}")
            return [site]
        return list(ALL_SITES)
    if user.site_name:
        return [user.site_name]
    raise HTTPException(status_code=403, detail="No site on this account.")


@router.get("")
def get_followup_list(site: str | None = None, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    rows = followup_list.build(db, _sites(current_user, site), clinical_today())
    allowed = sorted({r["enrollment_id"] for r in rows if can_view_pii_for_site(current_user, r["site"])})
    names = {}
    if allowed:
        from site_summary import pii_names
        brs = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id.in_(allowed)).all()
        found = pii_names(db, [b.screening_id for b in brs],
                          [b.enrollment_id for b in brs if (b.baby_number or 1) > 1])
        for b in brs:
            if (b.baby_number or 1) > 1:
                mother = (found.get(b.screening_id) or {}).get("mother")
                names[b.enrollment_id] = (found.get(b.enrollment_id) or {}).get("baby") or (
                    f"Baby of {mother}" if mother else None)
            else:
                names[b.enrollment_id] = (found.get(b.screening_id) or {}).get("baby")
    out = []
    for r in rows:
        x = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items() if k != "screening_id"}
        x["name"] = names.get(r["enrollment_id"])
        out.append(x)
    return {"today": clinical_today().isoformat(), "rows": out,
            "sites": list(ALL_SITES) if (current_user.role or "").lower() in CENTRAL else _sites(current_user, None)}
