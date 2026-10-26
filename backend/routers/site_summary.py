"""GET /site-summary: the twice-weekly site summary, live (PI 2026-10-26).

Same content as the Monday / Thursday email (site_summary.py). Same people
as Reports: Global PI + Project Scientist any or all sites, Site PI / Site
Scientist their own site. Nothing by arm. Unlike the email, each baby
(and each M8 mother) carries a "name" when the viewer may see that site's
PII (pii_service.can_view_pii_for_site; PI 2026-10-26).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import User
from pii_service import can_view_pii_for_site
from routers.reports import ALL_SITES as SITES, _scope_sites
import site_summary

router = APIRouter(prefix="/site-summary", tags=["Site summary"])


@router.get("")
def get_site_summary(site: str | None = None, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    sites = _scope_sites(current_user, site)
    scope = sites[0] if len(sites) == 1 else site_summary.ALL_SITES
    out = site_summary.build(db, scope)
    rows = out["babies"] + out["mothers"]
    names = site_summary.pii_names(
        db, [x["screening_id"] for x in rows if can_view_pii_for_site(current_user, x["site"])])
    for x in out["babies"]:
        x["name"] = names.get(x["screening_id"], {}).get("baby")
    for x in out["mothers"]:
        x["name"] = names.get(x["screening_id"], {}).get("mother")
    out["rules"] = site_summary.RULES
    out["sites"] = SITES if len(sites) > 1 or site else sites
    return out
