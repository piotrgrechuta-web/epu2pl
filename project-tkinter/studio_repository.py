#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from project_db import ProjectDB


class StudioRepository(Protocol):
    def list_projects_with_stage_summary(self) -> List[Dict[str, Any]]: ...
    def list_projects_for_series(self, series_id: int, *, include_deleted: bool = False) -> List[Dict[str, Any]]: ...
    def mark_project_pending(self, project_id: int, step: str) -> None: ...
    def get_next_pending_project(self) -> Optional[Dict[str, Any]]: ...
    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]: ...
    def get_series(self, series_id: int) -> Optional[Dict[str, Any]]: ...
    def count_open_qa_findings(self, project_id: int) -> int: ...


class SQLiteStudioRepository:
    """SQLite-backed repository adapter for queue/batch workflows.

    This keeps GUI orchestration separate from storage implementation details.
    """

    def __init__(self, db: ProjectDB):
        self.db = db

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, dict):
            return dict(row)
        try:
            return dict(row)
        except Exception:
            return None

    def list_projects_with_stage_summary(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.db.list_projects_with_stage_summary()]

    def list_projects_for_series(self, series_id: int, *, include_deleted: bool = False) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.db.list_projects_for_series(series_id, include_deleted=include_deleted)]

    def mark_project_pending(self, project_id: int, step: str) -> None:
        self.db.mark_project_pending(int(project_id), str(step))

    def get_next_pending_project(self) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(self.db.get_next_pending_project())

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(self.db.get_project(int(project_id)))

    def get_series(self, series_id: int) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(self.db.get_series(int(series_id)))

    def count_open_qa_findings(self, project_id: int) -> int:
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS c FROM qa_findings WHERE project_id = ? AND status = 'open'",
            (int(project_id),),
        ).fetchone()
        return int(row["c"] or 0) if row else 0
