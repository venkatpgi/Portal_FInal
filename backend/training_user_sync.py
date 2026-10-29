"""Copy login accounts from the trial database to the training database
(PI 2026-10-29).

The training site got a one-off copy of the trial users on 2026-10-14 and the
two then drifted: passwords changed on one site only, Site PIs created later
missing on training, and six placeholder accounts plus the old superadmin
`portal_admin` still active on training long after the trial site switched
them off. The trial site is now the master: every hour this script makes
training's users match it (username, password hash, role, site, on/off,
contact fields). Accounts that exist only on training are switched off.
Training keeps its own last_login_at. On training, password changes and
Manage Staff writes are refused (LOGINS_FROM_TRIAL=1, deps.py).

Run on the server (no names or hashes are printed):
  venv/bin/python training_user_sync.py --source-env .env --target-env .env.training [--dry-run]
"""
from __future__ import annotations

import argparse

from sqlalchemy import create_engine, text

COPIED = ("email", "hashed_password", "role", "site_name", "is_active", "full_name", "mobile",
          "must_change_password", "designation")


def database_url(env_file: str) -> str:
    for line in open(env_file, encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"no DATABASE_URL in {env_file}")


def sync(source_url: str, target_url: str, dry_run: bool = False) -> dict:
    if source_url == target_url:
        raise SystemExit("source and target are the same database")
    cols = ", ".join(("username", "created_at") + COPIED)
    with create_engine(source_url).connect() as src:
        master = {r["username"]: dict(r) for r in src.execute(text(f"SELECT {cols} FROM users")).mappings()}
    counts = {"updated": 0, "added": 0, "switched_off": 0, "unchanged": 0}
    eng = create_engine(target_url)
    with eng.connect() as dst:
        tx = dst.begin()
        current = {r["username"]: dict(r) for r in dst.execute(text(f"SELECT {cols} FROM users")).mappings()}
        # email is unique: first clear it on any training row whose email the
        # master gives to another username (e.g. portal_admin vs tech_admin)
        claimed = {row["email"]: name for name, row in master.items() if row["email"]}
        for name, have in current.items():
            if have["email"] and claimed.get(have["email"], name) != name:
                dst.execute(text("UPDATE users SET email = NULL WHERE username = :u"), {"u": name})
        for name, row in master.items():
            have = current.get(name)
            if have is None:
                dst.execute(text(f"INSERT INTO users ({cols}) VALUES ({', '.join(':' + c for c in ('username', 'created_at') + COPIED)})"), row)
                counts["added"] += 1
            elif any(have[c] != row[c] for c in COPIED):
                dst.execute(text(f"UPDATE users SET {', '.join(f'{c} = :{c}' for c in COPIED)} WHERE username = :username"), row)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
        for name, have in current.items():
            if name not in master and have["is_active"]:
                dst.execute(text("UPDATE users SET is_active = FALSE WHERE username = :u"), {"u": name})
                counts["switched_off"] += 1
        tx.rollback() if dry_run else tx.commit()
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-env", required=True)
    ap.add_argument("--target-env", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        result = sync(database_url(a.source_env), database_url(a.target_env), a.dry_run)
    except Exception as e:   # never print SQL parameters (password hashes)
        raise SystemExit(f"sync failed, nothing changed: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
    print(("DRY RUN (rolled back) " if a.dry_run else "") + " ".join(f"{k}={v}" for k, v in result.items()))
