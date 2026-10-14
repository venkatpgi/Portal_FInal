"""Writes from sites not yet enrolling are refused on the trial server (deps.py)."""
from types import SimpleNamespace

from fastapi import HTTPException

import deps


def req(method, path="/screenings/"):
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path))


def user(site, role="nurse"):
    return SimpleNamespace(site_name=site, role=role)


def blocked(method, u, path="/screenings/"):
    try:
        deps.refuse_non_live_site_write(req(method, path), u)
        return False
    except HTTPException as e:
        assert e.status_code == 403 and "training.portaltrial.in" in e.detail
        return True


def test_default_only_pgimer_live(monkeypatch):
    monkeypatch.delenv("LIVE_SITES", raising=False)
    assert not blocked("POST", user("PGIMER"))
    assert blocked("POST", user("AMC"))
    assert blocked("PUT", user("GMCH"))
    assert blocked("PATCH", user("GMCH-A"))
    assert blocked("DELETE", user("IOG"))


def test_reads_never_blocked(monkeypatch):
    monkeypatch.delenv("LIVE_SITES", raising=False)
    assert not blocked("GET", user("AMC"))
    assert not blocked("HEAD", user("AMC"))


def test_auth_paths_and_global_users_exempt(monkeypatch):
    monkeypatch.delenv("LIVE_SITES", raising=False)
    assert not blocked("POST", user("AMC"), "/auth/change-password")
    assert not blocked("POST", user("AMC", role="superadmin"))
    assert not blocked("POST", user("AMC", role="global_scientist"))
    assert not blocked("POST", user(None))
    assert not blocked("POST", user("  "))


def test_env_list_and_star(monkeypatch):
    monkeypatch.setenv("LIVE_SITES", "PGIMER, AMC")
    assert not blocked("POST", user("AMC"))
    assert blocked("POST", user("GMCH"))
    monkeypatch.setenv("LIVE_SITES", "*")
    assert not blocked("POST", user("GMCH"))
