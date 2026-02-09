#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="EPUB Translator Studio launcher")
    parser.add_argument(
        "--variant",
        choices=("classic", "horizon"),
        default="classic",
        help="UI variant to launch",
    )
    parser.add_argument("--migrate-only", action="store_true", help="Run DB migration only and exit")
    parser.add_argument("--rollback-last", action="store_true", help="Rollback last DB migration and exit")
    parser.add_argument("--migration-report", type=Path, default=None, help="Write migration report JSON")
    args = parser.parse_args()

    if args.migrate_only and args.rollback_last:
        parser.error("Use only one of: --migrate-only, --rollback-last")
    if args.migrate_only:
        from db_maintenance import cmd_migrate_only, _default_db_path, _default_series_path

        return int(cmd_migrate_only(_default_db_path(), _default_series_path(), args.migration_report))
    if args.rollback_last:
        from db_maintenance import cmd_rollback_last, _default_db_path

        return int(cmd_rollback_last(_default_db_path(), args.migration_report))

    if args.variant == "horizon":
        from app_gui_horizon import main as run_main
    else:
        from app_gui_classic import main as run_main

    return int(run_main())


if __name__ == "__main__":
    raise SystemExit(main())
