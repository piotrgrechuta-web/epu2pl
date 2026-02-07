#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _step(title: str) -> None:
    print(f"\n== {title} ==")


def run_git(
    args: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    cp = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=capture,
    )
    if check and cp.returncode != 0:
        if capture:
            if cp.stdout.strip():
                print(cp.stdout.strip())
            if cp.stderr.strip():
                print(cp.stderr.strip(), file=sys.stderr)
        raise SystemExit(cp.returncode)
    return cp


def ahead_behind(branch: str) -> Tuple[int, int]:
    cp = run_git(
        ["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"],
        check=False,
        capture=True,
    )
    if cp.returncode != 0:
        return (0, 0)
    parts = cp.stdout.strip().split()
    if len(parts) != 2:
        return (0, 0)
    return int(parts[0]), int(parts[1])


def get_remote_url(name: str, *, push: bool = False) -> str:
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.append(name)
    cp = run_git(args, check=False, capture=True)
    if cp.returncode != 0:
        return ""
    return cp.stdout.strip()


def derive_private_backup_url(origin_url: str) -> str:
    url = origin_url.strip()
    if not url:
        return ""
    if url.endswith(".git"):
        base = url[:-4]
        return f"{base}-private-backup.git"
    return f"{url}-private-backup"


def cmd_setup(args: argparse.Namespace) -> None:
    _ = args
    _step("Local git setup")
    settings = {
        "pull.ff": "only",
        "fetch.prune": "true",
        "rebase.autoStash": "true",
        "push.default": "simple",
    }
    for key, value in settings.items():
        run_git(["config", "--local", key, value])
        current = run_git(["config", "--local", "--get", key], capture=True).stdout.strip()
        print(f"{key}={current}")

    _step("Dual-push setup (origin + backup)")
    origin_url = get_remote_url("origin")
    if not origin_url:
        print("Brak zdalnego origin. Pomijam konfiguracje dual-push.")
        return

    backup_url = get_remote_url("backup")
    if not backup_url:
        backup_url = derive_private_backup_url(origin_url)
        run_git(["remote", "add", "backup", backup_url], check=False)
        backup_url = get_remote_url("backup")

    if not backup_url:
        print("Nie udalo sie ustawic remote backup. Publish bedzie pushowal tylko origin.")
        return

    # Ustawiamy push URL dla origin tak, by pojedynczy 'git push origin ...'
    # wysylal na oba zdalne repozytoria.
    run_git(["remote", "set-url", "--push", "origin", origin_url])
    run_git(["remote", "set-url", "--add", "--push", "origin", backup_url])
    print(f"origin(push)-> {origin_url}")
    print(f"origin(push)-> {backup_url}")
    print(f"backup(fetch/push)-> {backup_url}")


def cmd_start(args: argparse.Namespace) -> None:
    branch = args.branch
    _step("Fetch origin")
    run_git(["fetch", "--prune", "origin"])

    _step(f"Switch to {branch}")
    run_git(["switch", branch])

    _step(f"Pull latest origin/{branch}")
    run_git(["pull", "--ff-only", "origin", branch])

    _step("Status")
    run_git(["status", "-sb"])
    local_only, remote_only = ahead_behind(branch)
    print(f"ahead={local_only} behind={remote_only} vs origin/{branch}")


def cmd_publish(args: argparse.Namespace) -> None:
    branch = args.branch
    message = args.message.strip()
    if not message:
        raise SystemExit("Podaj tresc commitu przez --message.")

    _step("Fetch + switch")
    run_git(["fetch", "--prune", "origin"])
    run_git(["switch", branch])

    local_only, remote_only = ahead_behind(branch)
    if remote_only > 0:
        raise SystemExit(
            f"Branch jest {remote_only} commit(y) za origin/{branch}. "
            f"Uruchom najpierw: python scripts/git_workflow.py start --branch {branch}"
        )

    _step("Stage changes")
    run_git(["add", "-A"])
    staged = run_git(["diff", "--cached", "--quiet"], check=False)
    if staged.returncode == 0:
        print("Brak zmian do commitu.")
        return
    if staged.returncode != 1:
        raise SystemExit(staged.returncode)

    _step("Commit")
    run_git(["commit", "-m", message])

    _step(f"Push origin/{branch} (dual-push origin + backup, jesli skonfigurowane)")
    run_git(["push", "origin", branch])

    _step("Done")
    run_git(["log", "-1", "--oneline", "--decorate"])
    run_git(["status", "-sb"])


def cmd_status(args: argparse.Namespace) -> None:
    branch = args.branch
    if args.fetch:
        _step("Fetch origin")
        run_git(["fetch", "--prune", "origin"], check=False)

    _step("Status")
    run_git(["status", "-sb"])
    current = run_git(["rev-parse", "--abbrev-ref", "HEAD"], capture=True).stdout.strip()
    local_only, remote_only = ahead_behind(branch)
    print(f"branch={current}")
    print(f"ahead={local_only} behind={remote_only} vs origin/{branch}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ustandaryzowany workflow git dla pracy na wielu komputerach."
    )
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("setup", help="Jednorazowa konfiguracja lokalnego repo (.git/config).")
    ps.set_defaults(func=cmd_setup)

    pst = sub.add_parser("start", help="Start dnia: fetch + switch + pull --ff-only.")
    pst.add_argument("--branch", default="ep2pl", help="Nazwa brancha roboczego (domyslnie: ep2pl).")
    pst.set_defaults(func=cmd_start)

    pp = sub.add_parser("publish", help="Publikacja: add + commit + push.")
    pp.add_argument("--branch", default="ep2pl", help="Nazwa brancha roboczego (domyslnie: ep2pl).")
    pp.add_argument("-m", "--message", required=True, help="Wiadomosc commitu.")
    pp.set_defaults(func=cmd_publish)

    pss = sub.add_parser("status", help="Szybki status + ahead/behind.")
    pss.add_argument("--branch", default="ep2pl", help="Branch referencyjny origin (domyslnie: ep2pl).")
    pss.add_argument("--fetch", action="store_true", help="Najpierw wykonaj fetch --prune origin.")
    pss.set_defaults(func=cmd_status)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
