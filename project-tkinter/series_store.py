#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from lxml import etree

SERIES_DB_FILE = "series.db"
APPROVED_GLOSSARY_FILE = "approved_glossary.txt"
GENERATED_DIR = "generated"
SERIES_PROFILE_FILE = "series_profile.json"


def _now_ts() -> int:
    return int(time.time())


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "series"


@dataclass(frozen=True)
class SeriesHint:
    name: str
    volume_no: Optional[float]
    source: str
    confidence: float


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def _extract_title_fallback(title: str) -> Optional[SeriesHint]:
    raw = str(title or "").strip()
    if not raw:
        return None
    m = re.match(
        r"^(.*?)(?:\s*[-:,(]\s*(?:tom|t\.|vol\.?|volume|book)\s*([0-9]+(?:[.,][0-9]+)?).*)$",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    series_name = m.group(1).strip(" -:,()")
    if not series_name:
        return None
    return SeriesHint(
        name=series_name,
        volume_no=_parse_float(m.group(2)),
        source="title-pattern",
        confidence=0.45,
    )


def detect_series_hint(epub_path: Path) -> Optional[SeriesHint]:
    if not epub_path.exists():
        return None
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container = etree.fromstring(zf.read("META-INF/container.xml"))
            rootfile = container.find(".//{*}rootfile")
            if rootfile is None:
                return None
            opf_path = str(rootfile.get("full-path") or "").replace("\\", "/")
            if not opf_path:
                return None
            opf_root = etree.fromstring(zf.read(opf_path))
    except Exception:
        return None

    metadata = opf_root.find(".//{*}metadata")
    if metadata is None:
        return None

    title = ""
    title_el = metadata.find(".//{*}title")
    if title_el is not None:
        title = (title_el.text or "").strip()

    best_name = ""
    best_source = ""
    best_conf = 0.0
    volume_no: Optional[float] = None

    for meta in metadata.findall(".//{*}meta"):
        name_attr = (meta.get("name") or "").strip().lower()
        prop_attr = (meta.get("property") or "").strip().lower()
        content_attr = (meta.get("content") or "").strip()
        text_value = (meta.text or "").strip()
        value = content_attr or text_value
        if not value:
            continue
        if name_attr in {"calibre:series", "series"}:
            best_name = value
            best_source = f"meta:{name_attr}"
            best_conf = 0.95
        elif prop_attr == "belongs-to-collection" and best_conf < 0.9:
            best_name = value
            best_source = "meta:belongs-to-collection"
            best_conf = 0.85
        elif name_attr in {"calibre:series_index", "series_index"} and volume_no is None:
            volume_no = _parse_float(value)
        elif prop_attr in {"group-position", "series-index"} and volume_no is None:
            volume_no = _parse_float(value)

    if best_name:
        return SeriesHint(name=best_name, volume_no=volume_no, source=best_source, confidence=best_conf)

    fallback = _extract_title_fallback(title)
    if fallback is not None:
        return fallback
    return None


class SeriesStore:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def series_dir(self, slug: str) -> Path:
        return self.root_dir / slugify(slug)

    def series_db_path(self, slug: str) -> Path:
        return self.series_dir(slug) / SERIES_DB_FILE

    def _connect(self, slug: str) -> sqlite3.Connection:
        series_dir = self.series_dir(slug)
        series_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(series_dir / SERIES_DB_FILE), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        self._init_schema(conn)
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terms (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_term TEXT NOT NULL,
              target_term TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'proposed',
              confidence REAL NOT NULL DEFAULT 0.0,
              origin TEXT NOT NULL DEFAULT '',
              project_id INTEGER,
              source_hash TEXT NOT NULL DEFAULT '',
              source_example TEXT NOT NULL DEFAULT '',
              target_example TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              approved_at INTEGER
            )
            """
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_terms_pair ON terms(source_term, target_term)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_terms_status ON terms(status, updated_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_terms_source ON terms(source_term)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              segment_hash TEXT NOT NULL UNIQUE,
              project_id INTEGER,
              chapter_path TEXT NOT NULL DEFAULT '',
              segment_id TEXT NOT NULL DEFAULT '',
              source_excerpt TEXT NOT NULL DEFAULT '',
              approved_translation TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id, updated_at DESC)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lore_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              entry_key TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              content TEXT NOT NULL DEFAULT '',
              tags_json TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'draft',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lore_entry_key ON lore_entries(entry_key)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS style_rules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              rule_key TEXT NOT NULL UNIQUE,
              value_json TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS change_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              entity_type TEXT NOT NULL,
              entity_key TEXT NOT NULL,
              action TEXT NOT NULL,
              payload_json TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_change_log_created ON change_log(created_at DESC, id DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_change_log_entity ON change_log(entity_type, entity_key, created_at DESC)")
        conn.commit()

    def ensure_series_db(self, slug: str, *, display_name: str = "") -> Path:
        clean_slug = slugify(slug)
        with self._connect(clean_slug) as conn:
            now = _now_ts()
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("series_slug", clean_slug),
            )
            if display_name.strip():
                conn.execute(
                    "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    ("series_name", display_name.strip()),
                )
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("updated_at", str(now)),
            )
            conn.commit()
        return self.series_db_path(clean_slug)

    @staticmethod
    def _json_dumps(payload: Any) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            return json.dumps({"value": str(payload)}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _json_loads(value: str, default: Any) -> Any:
        try:
            return json.loads(str(value or ""))
        except Exception:
            return default

    def _log_change(
        self,
        conn: sqlite3.Connection,
        *,
        entity_type: str,
        entity_key: str,
        action: str,
        payload: Dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO change_log(entity_type, entity_key, action, payload_json, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                str(entity_type or "").strip(),
                str(entity_key or "").strip(),
                str(action or "").strip(),
                self._json_dumps(payload),
                _now_ts(),
            ),
        )

    def add_or_update_term(
        self,
        slug: str,
        *,
        source_term: str,
        target_term: str,
        status: str = "proposed",
        confidence: float = 0.0,
        origin: str = "",
        project_id: Optional[int] = None,
        source_example: str = "",
        target_example: str = "",
        notes: str = "",
    ) -> Tuple[int, bool]:
        src = str(source_term or "").strip()
        dst = str(target_term or "").strip()
        if not src or not dst:
            raise ValueError("source_term and target_term are required")
        now = _now_ts()
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT id, status, confidence FROM terms WHERE source_term = ? AND target_term = ?",
                (src, dst),
            ).fetchone()
            if row is None:
                approved_at = now if status == "approved" else None
                cur = conn.execute(
                    """
                    INSERT INTO terms(
                      source_term, target_term, status, confidence, origin, project_id, source_hash,
                      source_example, target_example, notes, created_at, updated_at, approved_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        src,
                        dst,
                        status,
                        float(confidence),
                        str(origin or ""),
                        project_id,
                        "",
                        str(source_example or ""),
                        str(target_example or ""),
                        str(notes or ""),
                        now,
                        now,
                        approved_at,
                    ),
                )
                term_id = int(cur.lastrowid)
                self._log_change(
                    conn,
                    entity_type="term",
                    entity_key=f"{src} => {dst}",
                    action="create",
                    payload={
                        "term_id": term_id,
                        "status": str(status),
                        "confidence": float(confidence),
                        "origin": str(origin or ""),
                        "project_id": project_id,
                    },
                )
                conn.commit()
                return term_id, True

            current_status = str(row["status"] or "proposed")
            final_status = current_status
            if status == "approved":
                final_status = "approved"
            elif current_status not in {"approved", "rejected"}:
                final_status = status
            approved_at = now if final_status == "approved" else None
            final_conf = max(float(row["confidence"] or 0.0), float(confidence))
            conn.execute(
                """
                UPDATE terms
                SET status = ?, confidence = ?, origin = CASE WHEN ? <> '' THEN ? ELSE origin END,
                    project_id = COALESCE(?, project_id),
                    source_example = CASE WHEN ? <> '' THEN ? ELSE source_example END,
                    target_example = CASE WHEN ? <> '' THEN ? ELSE target_example END,
                    notes = CASE WHEN ? <> '' THEN ? ELSE notes END,
                    updated_at = ?, approved_at = COALESCE(?, approved_at)
                WHERE id = ?
                """,
                (
                    final_status,
                    final_conf,
                    str(origin or ""),
                    str(origin or ""),
                    project_id,
                    str(source_example or ""),
                    str(source_example or ""),
                    str(target_example or ""),
                    str(target_example or ""),
                    str(notes or ""),
                    str(notes or ""),
                    now,
                    approved_at,
                    int(row["id"]),
                ),
            )
            self._log_change(
                conn,
                entity_type="term",
                entity_key=f"{src} => {dst}",
                action="update",
                payload={
                    "term_id": int(row["id"]),
                    "status": str(final_status),
                    "confidence": float(final_conf),
                    "origin": str(origin or ""),
                    "project_id": project_id,
                },
            )
            conn.commit()
            return int(row["id"]), False

    def set_term_status(self, slug: str, term_id: int, status: str, *, notes: str = "") -> None:
        now = _now_ts()
        approved_at = now if status == "approved" else None
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT source_term, target_term FROM terms WHERE id = ?",
                (int(term_id),),
            ).fetchone()
            conn.execute(
                """
                UPDATE terms
                SET status = ?, notes = CASE WHEN ? <> '' THEN ? ELSE notes END,
                    updated_at = ?, approved_at = COALESCE(?, approved_at)
                WHERE id = ?
                """,
                (status, str(notes or ""), str(notes or ""), now, approved_at, int(term_id)),
            )
            if row is not None:
                self._log_change(
                    conn,
                    entity_type="term",
                    entity_key=f"{str(row['source_term'] or '').strip()} => {str(row['target_term'] or '').strip()}",
                    action="status",
                    payload={
                        "term_id": int(term_id),
                        "status": str(status or ""),
                        "notes": str(notes or ""),
                    },
                )
            conn.commit()

    def list_terms(self, slug: str, *, status: Optional[str] = None, limit: int = 300) -> List[sqlite3.Row]:
        with self._connect(slug) as conn:
            if status is None:
                return list(conn.execute("SELECT * FROM terms ORDER BY updated_at DESC LIMIT ?", (int(limit),)))
            return list(
                conn.execute(
                    "SELECT * FROM terms WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, int(limit)),
                )
            )

    def list_approved_terms(self, slug: str, limit: int = 5000) -> List[Tuple[str, str]]:
        with self._connect(slug) as conn:
            rows = conn.execute(
                """
                SELECT source_term, target_term
                FROM terms
                WHERE status = 'approved'
                ORDER BY source_term COLLATE NOCASE, target_term COLLATE NOCASE
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [(str(r["source_term"]), str(r["target_term"])) for r in rows]

    def list_style_rules(self, slug: str, *, limit: int = 500) -> List[sqlite3.Row]:
        with self._connect(slug) as conn:
            return list(
                conn.execute(
                    "SELECT * FROM style_rules ORDER BY updated_at DESC, id DESC LIMIT ?",
                    (max(1, int(limit)),),
                )
            )

    def upsert_style_rule(
        self,
        slug: str,
        *,
        rule_key: str,
        value: Any,
    ) -> Tuple[int, bool]:
        key = str(rule_key or "").strip()
        if not key:
            raise ValueError("rule_key is required")
        payload: Dict[str, Any]
        if isinstance(value, dict):
            payload = dict(value)
        elif isinstance(value, str):
            payload = {"instruction": value}
        else:
            payload = {"value": value}
        now = _now_ts()
        value_json = self._json_dumps(payload)
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT id, value_json FROM style_rules WHERE rule_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    """
                    INSERT INTO style_rules(rule_key, value_json, created_at, updated_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (key, value_json, now, now),
                )
                rule_id = int(cur.lastrowid)
                self._log_change(
                    conn,
                    entity_type="style_rule",
                    entity_key=key,
                    action="create",
                    payload={"rule_id": rule_id, "value": payload},
                )
                conn.commit()
                return rule_id, True
            rule_id = int(row["id"])
            conn.execute(
                "UPDATE style_rules SET value_json = ?, updated_at = ? WHERE id = ?",
                (value_json, now, rule_id),
            )
            old_payload = self._json_loads(str(row["value_json"] or "{}"), {})
            self._log_change(
                conn,
                entity_type="style_rule",
                entity_key=key,
                action="update",
                payload={"rule_id": rule_id, "before": old_payload, "after": payload},
            )
            conn.commit()
            return rule_id, False

    def delete_style_rule(self, slug: str, rule_id: int) -> bool:
        rid = int(rule_id)
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT rule_key, value_json FROM style_rules WHERE id = ?",
                (rid,),
            ).fetchone()
            if row is None:
                return False
            cur = conn.execute("DELETE FROM style_rules WHERE id = ?", (rid,))
            if int(cur.rowcount or 0) > 0:
                self._log_change(
                    conn,
                    entity_type="style_rule",
                    entity_key=str(row["rule_key"] or ""),
                    action="delete",
                    payload={
                        "rule_id": rid,
                        "value": self._json_loads(str(row["value_json"] or "{}"), {}),
                    },
                )
                conn.commit()
                return True
            conn.commit()
            return False

    @staticmethod
    def _normalize_lore_status(status: str) -> str:
        raw = str(status or "").strip().lower()
        if raw in {"published", "active", "approved"}:
            return "active"
        if raw in {"archived", "inactive"}:
            return "archived"
        return "draft"

    def list_lore_entries(
        self,
        slug: str,
        *,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[sqlite3.Row]:
        with self._connect(slug) as conn:
            if status is None:
                return list(
                    conn.execute(
                        "SELECT * FROM lore_entries ORDER BY updated_at DESC, id DESC LIMIT ?",
                        (max(1, int(limit)),),
                    )
                )
            return list(
                conn.execute(
                    "SELECT * FROM lore_entries WHERE status = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                    (self._normalize_lore_status(status), max(1, int(limit))),
                )
            )

    def upsert_lore_entry(
        self,
        slug: str,
        *,
        entry_key: str,
        title: str,
        content: str,
        tags: Optional[Sequence[str]] = None,
        status: str = "draft",
    ) -> Tuple[int, bool]:
        clean_title = str(title or "").strip()
        clean_content = str(content or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        if not clean_content:
            raise ValueError("content is required")
        key = slugify(str(entry_key or "").strip() or clean_title)
        clean_tags = sorted(
            {
                str(tag).strip()
                for tag in (tags or [])
                if str(tag).strip()
            }
        )
        tags_json = self._json_dumps(clean_tags)
        final_status = self._normalize_lore_status(status)
        now = _now_ts()
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT id, title, content, tags_json, status FROM lore_entries WHERE entry_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    """
                    INSERT INTO lore_entries(entry_key, title, content, tags_json, status, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, clean_title, clean_content, tags_json, final_status, now, now),
                )
                lore_id = int(cur.lastrowid)
                self._log_change(
                    conn,
                    entity_type="lore",
                    entity_key=key,
                    action="create",
                    payload={
                        "lore_id": lore_id,
                        "title": clean_title,
                        "status": final_status,
                        "tags": clean_tags,
                    },
                )
                conn.commit()
                return lore_id, True

            lore_id = int(row["id"])
            before = {
                "title": str(row["title"] or ""),
                "content": str(row["content"] or ""),
                "status": str(row["status"] or ""),
                "tags": self._json_loads(str(row["tags_json"] or "[]"), []),
            }
            conn.execute(
                """
                UPDATE lore_entries
                SET title = ?, content = ?, tags_json = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_title, clean_content, tags_json, final_status, now, lore_id),
            )
            self._log_change(
                conn,
                entity_type="lore",
                entity_key=key,
                action="update",
                payload={
                    "lore_id": lore_id,
                    "before": before,
                    "after": {
                        "title": clean_title,
                        "content": clean_content,
                        "status": final_status,
                        "tags": clean_tags,
                    },
                },
            )
            conn.commit()
            return lore_id, False

    def set_lore_status(self, slug: str, lore_id: int, status: str) -> None:
        lid = int(lore_id)
        final_status = self._normalize_lore_status(status)
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT entry_key, status FROM lore_entries WHERE id = ?",
                (lid,),
            ).fetchone()
            if row is None:
                return
            conn.execute(
                "UPDATE lore_entries SET status = ?, updated_at = ? WHERE id = ?",
                (final_status, _now_ts(), lid),
            )
            self._log_change(
                conn,
                entity_type="lore",
                entity_key=str(row["entry_key"] or ""),
                action="status",
                payload={
                    "lore_id": lid,
                    "before_status": str(row["status"] or ""),
                    "status": final_status,
                },
            )
            conn.commit()

    def delete_lore_entry(self, slug: str, lore_id: int) -> bool:
        lid = int(lore_id)
        with self._connect(slug) as conn:
            row = conn.execute(
                "SELECT entry_key, title, content, tags_json, status FROM lore_entries WHERE id = ?",
                (lid,),
            ).fetchone()
            if row is None:
                return False
            cur = conn.execute("DELETE FROM lore_entries WHERE id = ?", (lid,))
            deleted = int(cur.rowcount or 0) > 0
            if deleted:
                self._log_change(
                    conn,
                    entity_type="lore",
                    entity_key=str(row["entry_key"] or ""),
                    action="delete",
                    payload={
                        "lore_id": lid,
                        "title": str(row["title"] or ""),
                        "status": str(row["status"] or ""),
                        "tags": self._json_loads(str(row["tags_json"] or "[]"), []),
                    },
                )
            conn.commit()
            return deleted

    def list_change_log(
        self,
        slug: str,
        *,
        entity_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[sqlite3.Row]:
        with self._connect(slug) as conn:
            if entity_type is None:
                return list(
                    conn.execute(
                        "SELECT * FROM change_log ORDER BY id DESC LIMIT ?",
                        (max(1, int(limit)),),
                    )
                )
            return list(
                conn.execute(
                    "SELECT * FROM change_log WHERE entity_type = ? ORDER BY id DESC LIMIT ?",
                    (str(entity_type).strip(), max(1, int(limit))),
                )
            )

    def export_series_profile(self, slug: str, *, output_path: Optional[Path] = None) -> Path:
        clean_slug = slugify(slug)
        terms = [
            {"source_term": src, "target_term": dst}
            for src, dst in self.list_approved_terms(clean_slug, limit=10000)
        ]
        style_rules: List[Dict[str, Any]] = []
        for row in self.list_style_rules(clean_slug, limit=2000):
            style_rules.append(
                {
                    "rule_key": str(row["rule_key"] or ""),
                    "value": self._json_loads(str(row["value_json"] or "{}"), {}),
                    "updated_at": int(row["updated_at"] or 0),
                }
            )
        lore_entries: List[Dict[str, Any]] = []
        for row in self.list_lore_entries(clean_slug, limit=5000):
            lore_entries.append(
                {
                    "entry_key": str(row["entry_key"] or ""),
                    "title": str(row["title"] or ""),
                    "content": str(row["content"] or ""),
                    "status": str(row["status"] or "draft"),
                    "tags": self._json_loads(str(row["tags_json"] or "[]"), []),
                    "updated_at": int(row["updated_at"] or 0),
                }
            )
        payload = {
            "schema_version": 1,
            "series_slug": clean_slug,
            "generated_at": _now_ts(),
            "terms": terms,
            "style_rules": style_rules,
            "lore_entries": lore_entries,
        }
        out = output_path or (self.series_dir(clean_slug) / GENERATED_DIR / SERIES_PROFILE_FILE)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    def import_series_profile(self, slug: str, profile_path: Path) -> Dict[str, int]:
        p = Path(profile_path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        raw = self._json_loads(p.read_text(encoding="utf-8", errors="replace"), {})
        if not isinstance(raw, dict):
            raise ValueError("Invalid series profile JSON")

        style_added = 0
        lore_added = 0
        terms_added = 0

        for row in raw.get("style_rules", []) or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("rule_key", "")).strip()
            if not key:
                continue
            _, created = self.upsert_style_rule(slug, rule_key=key, value=row.get("value", {}))
            if created:
                style_added += 1

        for row in raw.get("lore_entries", []) or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("entry_key", "")).strip() or slugify(str(row.get("title", "")))
            title = str(row.get("title", "")).strip()
            content = str(row.get("content", "")).strip()
            if not title or not content:
                continue
            _, created = self.upsert_lore_entry(
                slug,
                entry_key=key,
                title=title,
                content=content,
                tags=[str(x) for x in (row.get("tags", []) or []) if str(x).strip()],
                status=str(row.get("status", "draft")),
            )
            if created:
                lore_added += 1

        for row in raw.get("terms", []) or []:
            if not isinstance(row, dict):
                continue
            src = str(row.get("source_term", "")).strip()
            dst = str(row.get("target_term", "")).strip()
            if not src or not dst:
                continue
            _, created = self.add_or_update_term(
                slug,
                source_term=src,
                target_term=dst,
                status="approved",
                confidence=1.0,
                origin="series-profile-import",
            )
            if created:
                terms_added += 1

        return {
            "style_added": style_added,
            "lore_added": lore_added,
            "terms_added": terms_added,
        }

    def build_series_context_block(
        self,
        slug: str,
        *,
        max_rules: int = 24,
        max_lore: int = 24,
        max_terms: int = 80,
        max_chars: int = 8000,
    ) -> str:
        clean_slug = slugify(slug)
        out: List[str] = []
        used = 0

        def _append(line: str) -> None:
            nonlocal used
            if used >= max_chars:
                return
            part = str(line or "")
            if not part:
                return
            budget = max_chars - used
            if len(part) > budget:
                part = part[: max(0, budget - 3)] + "..."
            out.append(part)
            used += len(part) + 1

        style_rows = self.list_style_rules(clean_slug, limit=max_rules)
        lore_rows = self.list_lore_entries(clean_slug, status="active", limit=max_lore)
        term_rows = self.list_approved_terms(clean_slug, limit=max_terms)

        if style_rows:
            _append("Style rules (series-level):")
            for row in style_rows:
                data = self._json_loads(str(row["value_json"] or "{}"), {})
                if isinstance(data, dict):
                    text = str(data.get("instruction") or data.get("value") or data.get("text") or "").strip()
                    if not text:
                        text = self._json_dumps(data)
                else:
                    text = str(data).strip()
                _append(f"- {str(row['rule_key'] or '').strip()}: {text}")

        if lore_rows:
            if out:
                _append("")
            _append("Lorebook (active facts):")
            for row in lore_rows:
                tags = self._json_loads(str(row["tags_json"] or "[]"), [])
                tags_text = ""
                if isinstance(tags, list):
                    clean_tags = [str(t).strip() for t in tags if str(t).strip()]
                    if clean_tags:
                        tags_text = f" [tags: {', '.join(clean_tags)}]"
                title = str(row["title"] or "").strip()
                content = str(row["content"] or "").strip().replace("\n", " ")
                _append(f"- {title}: {content}{tags_text}")

        if term_rows:
            if out:
                _append("")
            _append("Terminology (approved):")
            for src, dst in term_rows:
                _append(f"- {src} => {dst}")

        return "\n".join(out).strip()

    def build_augmented_prompt(
        self,
        slug: str,
        *,
        base_prompt_path: Path,
        output_path: Path,
        run_step: str = "translate",
    ) -> Path:
        base = Path(base_prompt_path)
        if not base.exists():
            raise FileNotFoundError(str(base))
        context = self.build_series_context_block(slug)
        base_prompt = base.read_text(encoding="utf-8", errors="replace")
        if not context:
            final = base_prompt
        else:
            final = (
                base_prompt.rstrip()
                + "\n\n"
                + "### SERIES MEMORY CONTEXT (DO NOT TRANSLATE THIS BLOCK)\n"
                + f"Run step: {str(run_step or 'translate').strip()}\n"
                + context
                + "\n### END OF SERIES MEMORY CONTEXT\n"
            )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(final + ("\n" if final and not final.endswith("\n") else ""), encoding="utf-8")
        return out

    def add_decision(
        self,
        slug: str,
        *,
        segment_hash: str,
        approved_translation: str,
        source_excerpt: str = "",
        project_id: Optional[int] = None,
        chapter_path: str = "",
        segment_id: str = "",
    ) -> None:
        key = str(segment_hash or "").strip()
        if not key:
            return
        now = _now_ts()
        with self._connect(slug) as conn:
            conn.execute(
                """
                INSERT INTO decisions(
                  segment_hash, project_id, chapter_path, segment_id, source_excerpt, approved_translation, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(segment_hash) DO UPDATE SET
                  project_id = COALESCE(excluded.project_id, decisions.project_id),
                  chapter_path = excluded.chapter_path,
                  segment_id = excluded.segment_id,
                  source_excerpt = excluded.source_excerpt,
                  approved_translation = excluded.approved_translation,
                  updated_at = excluded.updated_at
                """,
                (
                    key,
                    project_id,
                    str(chapter_path or ""),
                    str(segment_id or ""),
                    str(source_excerpt or ""),
                    str(approved_translation or ""),
                    now,
                    now,
                ),
            )
            conn.commit()

    def export_approved_glossary(self, slug: str, *, output_path: Optional[Path] = None) -> Path:
        terms = self.list_approved_terms(slug)
        out = output_path or (self.series_dir(slug) / GENERATED_DIR / APPROVED_GLOSSARY_FILE)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{src} => {dst}" for src, dst in terms]
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return out

    def build_merged_glossary(
        self,
        slug: str,
        *,
        project_glossary: Optional[Path],
        output_path: Optional[Path] = None,
    ) -> Path:
        out = output_path or (self.series_dir(slug) / GENERATED_DIR / "merged_glossary.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        merged: List[str] = []
        seen: set[str] = set()

        approved_lines = [f"{src} => {dst}" for src, dst in self.list_approved_terms(slug)]
        for line in approved_lines:
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                merged.append(line)

        if project_glossary is not None and project_glossary.exists():
            for raw in project_glossary.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line:
                    continue
                key = line.lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(line)

        out.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
        return out

    def learn_terms_from_tm(
        self,
        slug: str,
        tm_rows: Sequence[Dict[str, Any]],
        *,
        project_id: Optional[int] = None,
        max_rows: int = 2000,
    ) -> int:
        count = 0
        for row in tm_rows[: max(0, int(max_rows))]:
            src = str(row.get("source_text", "")).strip()
            dst = str(row.get("target_text", "")).strip()
            if not src or not dst:
                continue
            pairs = _extract_term_pairs(src, dst)
            for source_term, target_term, confidence, origin in pairs:
                _, created = self.add_or_update_term(
                    slug,
                    source_term=source_term,
                    target_term=target_term,
                    status="proposed",
                    confidence=confidence,
                    origin=origin,
                    project_id=project_id,
                    source_example=src[:240],
                    target_example=dst[:240],
                )
                if created:
                    count += 1
        return count


_QUOTED_RE = re.compile(r"[\"“”„']([^\"“”„']{2,80})[\"“”„']")
_TITLECASE_RE = re.compile(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-z0-9ĄĆĘŁŃÓŚŹŻąćęłńóśźż'’_-]{1,}(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-z0-9ĄĆĘŁŃÓŚŹŻąćęłńóśźż'’_-]{1,}){0,2}\b")


def _looks_term_like(text: str) -> bool:
    val = str(text or "").strip()
    if not val:
        return False
    if len(val) > 80:
        return False
    if re.search(r"[.!?]\s*$", val):
        return False
    words = re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9'’_-]+", val)
    return 1 <= len(words) <= 6


def _extract_term_pairs(source_text: str, target_text: str) -> List[Tuple[str, str, float, str]]:
    out: List[Tuple[str, str, float, str]] = []
    seen: set[Tuple[str, str]] = set()

    src_quotes = [s.strip() for s in _QUOTED_RE.findall(source_text)]
    dst_quotes = [s.strip() for s in _QUOTED_RE.findall(target_text)]
    for src, dst in zip(src_quotes, dst_quotes):
        if _looks_term_like(src) and _looks_term_like(dst):
            key = (src.lower(), dst.lower())
            if key not in seen:
                seen.add(key)
                out.append((src, dst, 0.85, "tm-quoted"))

    src_titles = [s.strip() for s in _TITLECASE_RE.findall(source_text)]
    dst_titles = [s.strip() for s in _TITLECASE_RE.findall(target_text)]
    for src, dst in zip(src_titles, dst_titles):
        if _looks_term_like(src) and _looks_term_like(dst):
            key = (src.lower(), dst.lower())
            if key not in seen:
                seen.add(key)
                out.append((src, dst, 0.65, "tm-titlecase"))

    if _looks_term_like(source_text) and _looks_term_like(target_text):
        src = source_text.strip()
        dst = target_text.strip()
        key = (src.lower(), dst.lower())
        if key not in seen:
            out.append((src, dst, 0.55, "tm-short-segment"))
    return out
