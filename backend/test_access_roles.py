"""Role rules (access hierarchy SOP 1 Oct 2026, PI 2026-10-15): read-only
roles, PTS3 limits, who sees participant identity, all-site scope."""
from types import SimpleNamespace

from fastapi import HTTPException

import deps
from pii_service import can_view_pii_for_site


def req(method, path):
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path))


def user(role, site=None):
    return SimpleNamespace(role=role, site_name=site)


def refused(method, path, u):
    try:
        deps.refuse_role_restricted_request(req(method, path), u)
        return False
    except HTTPException as e:
        assert e.status_code == 403
        return True


def test_project_scientist_is_all_sites_and_view_only():
    ps = user("project_scientist")
    assert deps.is_global(ps) and deps.is_read_only(ps) and deps.is_central_analytics(ps)
    assert not refused("GET", "/screenings/", ps)
    assert refused("POST", "/screenings/", ps)
    assert refused("PUT", "/birth-resuscitation/01-A-001", ps)
    assert refused("DELETE", "/screenings/5", ps)
    assert not refused("POST", "/dashboard/ai-insights", ps)
    assert not refused("POST", "/pii/batch", ps)
    assert not refused("POST", "/auth/change-password", ps)


def test_tech_support_reads_records_but_no_reports_or_identity():
    ts = user("tech_support")
    assert deps.is_global(ts) and deps.is_read_only(ts) and not deps.is_central_analytics(ts)
    assert not refused("GET", "/birth-resuscitation/01-A-001", ts)
    assert not refused("GET", "/audit/", ts)
    assert refused("GET", "/dashboard/consort", ts)
    assert refused("GET", "/pii/screening/01-0017", ts)
    assert refused("GET", "/sae-report/01-A-001/3/document", ts)
    assert refused("POST", "/dashboard/ai-insights", ts)
    assert refused("PUT", "/screenings/3", ts)
    assert not refused("POST", "/users/", ts)
    assert not refused("PUT", "/users/4", ts)
    assert not refused("DELETE", "/users/4", ts)
    assert deps.can_manage_users(ts)
    assert not deps.can_manage_users(user("nurse", "PGIMER"))


def test_editing_roles_unaffected():
    for role, site in [("superadmin", None), ("site_pi", "PGIMER"), ("site_scientist", "PGIMER"), ("nurse", "PGIMER")]:
        u = user(role, site)
        assert not deps.is_read_only(u)
        assert not refused("POST", "/screenings/", u)
        assert not refused("GET", "/dashboard/data-quality", u)


def test_who_sees_participant_identity():
    assert can_view_pii_for_site(user("superadmin"), "AMC")
    assert can_view_pii_for_site(user("project_scientist"), "AMC")
    assert not can_view_pii_for_site(user("tech_support"), "AMC")
    assert can_view_pii_for_site(user("nurse", "AMC"), "AMC")
    assert not can_view_pii_for_site(user("nurse", "AMC"), "GMCH")
    assert can_view_pii_for_site(user("site_scientist", "GMCH"), "GMCH")
    # placeholder roles being retired no longer see identity
    assert not can_view_pii_for_site(user("deo", "GMCH"), "GMCH")
    assert not can_view_pii_for_site(user("monitor", "GMCH"), "GMCH")
