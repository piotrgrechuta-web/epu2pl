from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_db import ProjectDB, SCHEMA_META_ALIAS_KEY, SCHEMA_META_KEY  # noqa: E402
from studio_repository import SQLiteStudioRepository  # noqa: E402


def test_schema_version_alias_is_set_for_new_db(tmp_path: Path) -> None:
    db = ProjectDB(tmp_path / "studio.db")
    try:
        raw_schema = db._meta_get(SCHEMA_META_KEY)  # noqa: SLF001
        raw_alias = db._meta_get(SCHEMA_META_ALIAS_KEY)  # noqa: SLF001
        assert raw_schema is not None
        assert raw_alias is not None
        assert str(raw_schema) == str(raw_alias)
    finally:
        db.close()


def test_schema_version_alias_recovers_legacy_alias_only_db(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_alias.db"
    raw = sqlite3.connect(str(db_path))
    raw.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        (SCHEMA_META_ALIAS_KEY, "8"),
    )
    raw.commit()
    raw.close()

    db = ProjectDB(db_path, run_migrations=False)
    try:
        assert db._schema_version() == 8  # noqa: SLF001
        assert str(db._meta_get(SCHEMA_META_KEY)) == "8"  # noqa: SLF001
        assert str(db._meta_get(SCHEMA_META_ALIAS_KEY)) == "8"  # noqa: SLF001
    finally:
        db.close()


def test_sqlite_repository_queue_and_qa_counts(tmp_path: Path) -> None:
    db = ProjectDB(tmp_path / "studio.db")
    repo = SQLiteStudioRepository(db)
    try:
        sid = db.ensure_series("Repo Saga", source="manual")
        pid = db.create_project(
            "Repo Book 1",
            {
                "series_id": sid,
                "volume_no": 1.0,
                "input_epub": str(tmp_path / "book.epub"),
                "output_translate_epub": str(tmp_path / "book_pl.epub"),
                "output_edit_epub": str(tmp_path / "book_pl_edit.epub"),
            },
        )

        series_projects = repo.list_projects_for_series(sid)
        assert len(series_projects) == 1
        assert int(series_projects[0]["id"]) == pid

        repo.mark_project_pending(pid, "translate")
        nxt = repo.get_next_pending_project()
        assert nxt is not None
        assert int(nxt["id"]) == pid

        assert repo.count_open_qa_findings(pid) == 0
        inserted = db.replace_qa_findings(
            project_id=pid,
            step="translate",
            findings=[
                {
                    "chapter_path": "OPS/ch1.xhtml",
                    "segment_index": 1,
                    "segment_id": "OPS/ch1.xhtml#1",
                    "severity": "error",
                    "rule_code": "TEST",
                    "message": "example",
                }
            ],
        )
        assert inserted == 1
        assert repo.count_open_qa_findings(pid) == 1
    finally:
        db.close()
