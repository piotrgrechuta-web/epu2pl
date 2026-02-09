from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_db import ProjectDB  # noqa: E402
from studio_suite import _safe_extract_zip  # noqa: E402


def test_recover_interrupted_runtime_state_marks_running_as_recoverable(tmp_path: Path) -> None:
    db_path = tmp_path / "studio.db"
    db = ProjectDB(db_path)
    try:
        pid = db.create_project("Recovery test")
        _ = db.start_run(pid, "translate", "python -u translation_engine.py ...")
    finally:
        db.close()

    db2 = ProjectDB(db_path, recover_runtime_state=True)
    try:
        row = db2.recent_runs(pid, limit=1)[0]
        assert str(row["status"]) == "error"
        assert int(row["finished_at"] or 0) > 0
        assert "interrupted recovery on startup" in str(row["message"] or "")

        project = db2.get_project(pid)
        assert project is not None
        assert str(project["status"]) == "pending"
    finally:
        db2.close()


def test_safe_extract_zip_allows_regular_entries(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    dest = tmp_path / "dest"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("folder/file.txt", "ok")

    with zipfile.ZipFile(archive, "r") as zf:
        _safe_extract_zip(zf, dest)

    assert (dest / "folder" / "file.txt").read_text(encoding="utf-8") == "ok"


def test_safe_extract_zip_blocks_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    dest = tmp_path / "dest"
    outside = tmp_path / "outside.txt"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../outside.txt", "owned")

    with zipfile.ZipFile(archive, "r") as zf:
        with pytest.raises(ValueError, match="Unsafe zip entry path"):
            _safe_extract_zip(zf, dest)

    assert not outside.exists()
