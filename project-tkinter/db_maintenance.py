#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_db import DB_FILE, ProjectDB


def _default_db_path() -> Path:
    return Path(__file__).resolve().with_name(DB_FILE)


def _default_series_path() -> Path:
    return Path(__file__).resolve().with_name("data").joinpath("series")


def cmd_migrate_only(db_path: Path, series_path: Path, report_file: Path | None) -> int:
    db = ProjectDB(
        db_path,
        recover_runtime_state=True,
        backup_paths=[series_path],
        run_migrations=True,
    )
    try:
        if db.last_migration_summary:
            m = db.last_migration_summary
            print(
                "MIGRATION_OK "
                f"from={m.get('from_schema')} to={m.get('to_schema')} "
                f"backup={m.get('backup_dir')}"
            )
        else:
            print("MIGRATION_SKIPPED schema already current")
        report = db.build_migration_report(limit=100)
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"REPORT_WRITTEN {report_file}")
        return 0
    finally:
        db.close()


def cmd_rollback_last(db_path: Path, report_file: Path | None) -> int:
    db = ProjectDB(
        db_path,
        recover_runtime_state=False,
        run_migrations=False,
    )
    try:
        ok, msg = db.rollback_last_migration()
        print(msg)
        report = db.build_migration_report(limit=100)
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"REPORT_WRITTEN {report_file}")
        return 0 if ok else 2
    finally:
        db.close()


def cmd_report(db_path: Path, report_file: Path | None) -> int:
    db = ProjectDB(
        db_path,
        recover_runtime_state=False,
        run_migrations=False,
    )
    try:
        report = db.build_migration_report(limit=200)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(text, encoding="utf-8")
            print(f"REPORT_WRITTEN {report_file}")
        else:
            print(text)
        return 0
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="EPUB Translator Studio DB migration maintenance")
    ap.add_argument("--db-path", type=Path, default=_default_db_path())
    ap.add_argument("--series-path", type=Path, default=_default_series_path())
    ap.add_argument("--report-file", type=Path, default=None)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--migrate-only", action="store_true")
    mode.add_argument("--rollback-last", action="store_true")
    mode.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db_path)
    series_path = Path(args.series_path)
    report_file = Path(args.report_file) if args.report_file is not None else None

    if args.migrate_only:
        return cmd_migrate_only(db_path, series_path, report_file)
    if args.rollback_last:
        return cmd_rollback_last(db_path, report_file)
    return cmd_report(db_path, report_file)


if __name__ == "__main__":
    raise SystemExit(main())
