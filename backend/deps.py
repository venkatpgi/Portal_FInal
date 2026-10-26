import os

from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from config import SECRET_KEY, ALGORITHM
from models import User
from db import get_db
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ============================================================================
# ROLE HIERARCHY
# Superadmin -> Project Scientist (head, all sites) -> Site PI -> Site
# Scientist -> Nurse. Stored lowercase/snake_case in User.role.
# ============================================================================
ROLE_SUPERADMIN = "superadmin"
ROLE_PROJECT_SCIENTIST = "project_scientist"   # Overall Project Scientist (PRS3-M): all sites, view only (PI 2026-10-15)
ROLE_SITE_PI = "site_pi"
ROLE_SITE_SCIENTIST = "site_scientist"
ROLE_NURSE = "nurse"
ROLE_PII_OFFICER = "pii_officer"               # existing, unrelated to site hierarchy
ROLE_GLOBAL_SCIENTIST = "global_scientist"       # cross-site read (trial monitoring, etc.)
ROLE_TECH_SUPPORT = "tech_support"             # Project Technical Support 3 (PTS3): read-only, no PII, no reports

ALL_ROLES = frozenset({
    ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST,
    ROLE_SITE_PI, ROLE_SITE_SCIENTIST, ROLE_NURSE, ROLE_PII_OFFICER,
    ROLE_TECH_SUPPORT,
})

# Roles that see every site, not just their own site_name (access hierarchy
# SOP 1 Oct 2026 + PI 2026-10-15). project_scientist is now the Overall
# Project Scientist (PRS3-M) -- all sites, replacing the Aug 2026 site-scoped
# rule; global_scientist is kept as its legacy alias. tech_support (PTS3)
# reads all sites to reproduce bugs. Write limits: READ_ONLY_ROLES below.
GLOBAL_ROLES = frozenset({ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST, ROLE_TECH_SUPPORT})

# Cannot create, edit or delete clinical data anywhere (PI 2026-10-15): only
# the Global PI (superadmin) and site roles edit. Enforced for every endpoint
# in get_current_user (refuse_role_restricted_request).
READ_ONLY_ROLES = frozenset({ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST, ROLE_TECH_SUPPORT})

# Trial-wide analytics: dashboards, AI Insights, CSV export.
CENTRAL_ANALYTICS_ROLES = frozenset({ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST})

# Mobile app (Flutter UserRole enum) only knows ADMIN/PI/SCIENTIST/NURSE/DEO/MONITOR.
# Both project_scientist (global) and site_scientist map to SCIENTIST; the mobile
# client tells them apart by whether site_name is null.
MOBILE_ROLE_MAP = {
    ROLE_SUPERADMIN: "ADMIN",
    ROLE_PROJECT_SCIENTIST: "SCIENTIST",
    ROLE_GLOBAL_SCIENTIST: "SCIENTIST",
    ROLE_SITE_PI: "PI",
    ROLE_SITE_SCIENTIST: "SCIENTIST",
    ROLE_NURSE: "NURSE",
    ROLE_PII_OFFICER: "MONITOR",
    ROLE_TECH_SUPPORT: "MONITOR",
}


def _role(user: User) -> str:
    return (user.role or "").lower()


def is_superadmin(user: User) -> bool:
    return _role(user) == ROLE_SUPERADMIN


def is_read_only(user: User) -> bool:
    return _role(user) in READ_ONLY_ROLES


def is_central_analytics(user: User) -> bool:
    return _role(user) in CENTRAL_ANALYTICS_ROLES


def is_global(user: User) -> bool:
    """True for roles with cross-site read access (see GLOBAL_ROLES)."""
    return _role(user) in GLOBAL_ROLES


def require_superadmin(user: User):
    if not is_superadmin(user):
        raise HTTPException(status_code=403, detail="Superadmin access required")


def ensure_same_site(site_name: str | None, user: User):
    if is_global(user):
        return
    if not user.site_name or site_name != user.site_name:
        raise HTTPException(status_code=403, detail="Access denied for this site")


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Use access token, not refresh token",
            )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401)

    refuse_role_restricted_request(request, user)
    refuse_non_live_site_write(request, user)
    db.info["audit_user"] = (user.id, user.username)   # audit_trail.py: who made this request's changes
    return user


# ============================================================================
# SITES NOT YET ENROLLING (PI 2026-10-14)
# Only staff of live sites may save on the trial server; staff of other sites
# practise on training.portaltrial.in (own database). LIVE_SITES env var:
# comma-separated site names, "*" = every site (set on the training server).
# Default PGIMER. Reading is unaffected; global roles (superadmin,
# global_scientist), users without a site, and /auth/* (login, refresh,
# logout, change password) are never blocked. Add a site on its go-live day.
# ============================================================================
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
WRITE_EXEMPT_PATH_PREFIXES = ("/auth/", "/reports/")  # running a report is a read
TRAINING_SITE_URL = "https://training.portaltrial.in"


def live_sites() -> frozenset | None:
    """Sites allowed to save here, or None when every site is allowed."""
    raw = os.getenv("LIVE_SITES", "PGIMER").strip()
    if raw == "*":
        return None
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def refuse_non_live_site_write(request: Request, user: User) -> None:
    if request.method.upper() not in WRITE_METHODS:
        return
    if is_global(user) or not (user.site_name or "").strip():
        return
    if request.url.path.startswith(WRITE_EXEMPT_PATH_PREFIXES):
        return
    sites = live_sites()
    if sites is None or user.site_name in sites:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"{user.site_name} is not enrolling in the trial yet, so entries cannot be "
            f"saved here. Please use the training site: {TRAINING_SITE_URL}"
        ),
    )


# ============================================================================
# READ-ONLY ROLES AND PTS3 LIMITS (PI 2026-10-15, enforced for every endpoint)
# ============================================================================
# POSTs allowed for read-only roles: reads, and acting on data queries
# (oversight, not data entry).
READ_ONLY_ALLOWED_WRITE_PREFIXES = ("/auth/", "/pii/batch", "/data-queries/", "/reports/")
# Central analytics roles may also use the AI Insights chat (a POST).
ANALYTICS_ALLOWED_WRITE_PREFIXES = ("/dashboard/ai-insights",)
# PTS3 (tech_support) reads records to reproduce bugs, but never sees
# participant identity, quality / analytics dashboards or generated reports.
TECH_SUPPORT_DENIED_PREFIXES = ("/dashboard/", "/pii/", "/data-queries", "/reports")
TECH_SUPPORT_DENIED_SUFFIXES = ("/document",)


def refuse_role_restricted_request(request: Request, user: User) -> None:
    path = request.url.path
    role = _role(user)
    if role == ROLE_TECH_SUPPORT and (
        path.startswith(TECH_SUPPORT_DENIED_PREFIXES) or path.endswith(TECH_SUPPORT_DENIED_SUFFIXES)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not available to the technical support role.")
    if request.method.upper() not in WRITE_METHODS or role not in READ_ONLY_ROLES:
        return
    if path.startswith(READ_ONLY_ALLOWED_WRITE_PREFIXES):
        return
    if role in CENTRAL_ANALYTICS_ROLES and path.startswith(ANALYTICS_ALLOWED_WRITE_PREFIXES):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="This account is view-only: entries cannot be created, changed or deleted.")
