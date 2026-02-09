from __future__ import annotations

import sqlite3
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_db import ProjectDB  # noqa: E402
from series_store import SeriesStore, detect_series_hint  # noqa: E402


def _write_epub_with_series(epub_path: Path) -> None:
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>The Expanse - Tom 1</dc:title>
    <meta name="calibre:series" content="The Expanse"/>
    <meta name="calibre:series_index" content="1"/>
  </metadata>
  <manifest>
    <item id="chap1" href="Text/ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
  </spine>
</package>
"""
    with zipfile.ZipFile(epub_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OPS/content.opf", opf)
        zf.writestr("OPS/Text/ch1.xhtml", "<html xmlns='http://www.w3.org/1999/xhtml'><body><p>Hello</p></body></html>")


def test_project_db_series_assignment(tmp_path: Path) -> None:
    db_path = tmp_path / "studio.db"
    db = ProjectDB(db_path)
    sid = db.ensure_series("The Expanse", source="manual")
    pid = db.create_project(
        "Leviathan Wakes",
        {
            "series_id": sid,
            "volume_no": 1.0,
            "input_epub": str(tmp_path / "book.epub"),
            "output_translate_epub": str(tmp_path / "book_pl.epub"),
            "output_edit_epub": str(tmp_path / "book_pl_edit.epub"),
        },
    )
    row = db.get_project(pid)
    assert row is not None
    assert int(row["series_id"]) == sid
    assert str(row["series_name"]) == "The Expanse"
    assert float(row["volume_no"]) == 1.0
    db.close()


def test_detect_series_hint_from_epub_metadata(tmp_path: Path) -> None:
    epub_path = tmp_path / "expanse.epub"
    _write_epub_with_series(epub_path)
    hint = detect_series_hint(epub_path)
    assert hint is not None
    assert hint.name == "The Expanse"
    assert hint.volume_no == 1.0
    assert hint.source.startswith("meta:")


def test_series_store_terms_and_export(tmp_path: Path) -> None:
    store = SeriesStore(tmp_path / "series")
    store.ensure_series_db("the-expanse", display_name="The Expanse")
    term_id, created = store.add_or_update_term(
        "the-expanse",
        source_term="Ring Gate",
        target_term="Brama Pierscienia",
        status="proposed",
        confidence=0.8,
        origin="tm-quoted",
        project_id=123,
    )
    assert created is True
    assert term_id > 0

    rows = store.list_terms("the-expanse", status="proposed")
    assert len(rows) == 1

    store.set_term_status("the-expanse", term_id, "approved")
    approved = store.list_approved_terms("the-expanse")
    assert ("Ring Gate", "Brama Pierscienia") in approved

    out = store.export_approved_glossary("the-expanse")
    content = out.read_text(encoding="utf-8")
    assert "Ring Gate => Brama Pierscienia" in content


def test_series_store_learns_from_tm(tmp_path: Path) -> None:
    store = SeriesStore(tmp_path / "series")
    store.ensure_series_db("my-series", display_name="My Series")
    rows = [
        {
            "source_text": 'He crossed the "Ring Gate" and met High Consul Duarte.',
            "target_text": 'Przeszedl przez "Brame Pierscienia" i spotkal Wysokiego Konsula Duarte.',
        }
    ]
    added = store.learn_terms_from_tm("my-series", rows, project_id=77)
    assert added >= 1
    all_rows = store.list_terms("my-series")
    assert len(all_rows) >= 1


def test_project_db_repairs_schema_drift_on_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "drift.db"
    raw = sqlite3.connect(str(db_path))
    raw.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '8')")
    raw.execute(
        """
        CREATE TABLE projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          input_epub TEXT NOT NULL DEFAULT '',
          output_translate_epub TEXT NOT NULL DEFAULT '',
          output_edit_epub TEXT NOT NULL DEFAULT '',
          prompt_translate TEXT NOT NULL DEFAULT '',
          prompt_edit TEXT NOT NULL DEFAULT '',
          glossary_path TEXT NOT NULL DEFAULT '',
          cache_translate_path TEXT NOT NULL DEFAULT '',
          cache_edit_path TEXT NOT NULL DEFAULT '',
          profile_translate_id INTEGER,
          profile_edit_id INTEGER,
          active_step TEXT NOT NULL DEFAULT 'translate',
          status TEXT NOT NULL DEFAULT 'idle',
          notes TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )
    raw.commit()
    raw.close()

    db = ProjectDB(db_path)
    cols = {str(r["name"]) for r in db.conn.execute("PRAGMA table_info(projects)").fetchall()}
    assert "series_id" in cols
    assert "volume_no" in cols
    assert "source_lang" in cols
    assert "target_lang" in cols
    db.close()


def test_project_db_series_update_and_delete_detaches_projects(tmp_path: Path) -> None:
    db = ProjectDB(tmp_path / "studio.db")
    sid = db.ensure_series("Saga A", source="manual")
    pid = db.create_project(
        "Tom 1",
        {
            "series_id": sid,
            "volume_no": 1.0,
            "input_epub": str(tmp_path / "book.epub"),
            "output_translate_epub": str(tmp_path / "book_pl.epub"),
            "output_edit_epub": str(tmp_path / "book_pl_edit.epub"),
        },
    )
    assert db.count_projects_for_series(sid) == 1

    db.update_series(sid, name="Saga Alfa", regenerate_slug=False)
    row = db.get_series(sid)
    assert row is not None
    assert str(row["name"]) == "Saga Alfa"

    deleted = db.delete_series(sid)
    assert deleted == 1
    assert db.get_series(sid) is None
    updated_project = db.get_project(pid)
    assert updated_project is not None
    assert updated_project["series_id"] is None
    assert updated_project["volume_no"] is None
    db.close()


def test_series_store_style_lore_change_log_and_augmented_prompt(tmp_path: Path) -> None:
    store = SeriesStore(tmp_path / "series")
    store.ensure_series_db("saga-a", display_name="Saga A")

    rule_id, created = store.upsert_style_rule(
        "saga-a",
        rule_key="tone.formality",
        value={"instruction": "Use neutral, modern narration."},
    )
    assert created is True
    assert rule_id > 0

    _, created2 = store.upsert_style_rule(
        "saga-a",
        rule_key="tone.formality",
        value={"instruction": "Use warm and direct narration."},
    )
    assert created2 is False

    lore_id, lore_created = store.upsert_lore_entry(
        "saga-a",
        entry_key="hero-origin",
        title="Hero Origin",
        content="Arin comes from the northern city-state.",
        tags=["character", "origin"],
        status="active",
    )
    assert lore_created is True
    assert lore_id > 0
    store.set_lore_status("saga-a", lore_id, "active")

    logs = store.list_change_log("saga-a", limit=100)
    assert any(str(r["entity_type"]) == "style_rule" for r in logs)
    assert any(str(r["entity_type"]) == "lore" for r in logs)

    context_block = store.build_series_context_block("saga-a")
    assert "tone.formality" in context_block
    assert "Hero Origin" in context_block

    base_prompt = tmp_path / "prompt.txt"
    base_prompt.write_text("Translate faithfully.", encoding="utf-8")
    out_prompt = tmp_path / "prompt_augmented.txt"
    built = store.build_augmented_prompt(
        "saga-a",
        base_prompt_path=base_prompt,
        output_path=out_prompt,
        run_step="translate",
    )
    assert built.exists()
    merged = built.read_text(encoding="utf-8")
    assert "Translate faithfully." in merged
    assert "SERIES MEMORY CONTEXT" in merged
    assert "Hero Origin" in merged


def test_series_profile_export_import_roundtrip(tmp_path: Path) -> None:
    src_store = SeriesStore(tmp_path / "src_series")
    src_store.ensure_series_db("alpha", display_name="Alpha")
    src_store.add_or_update_term(
        "alpha",
        source_term="Void Gate",
        target_term="Brama Pustki",
        status="approved",
        confidence=1.0,
        origin="manual",
    )
    src_store.upsert_style_rule(
        "alpha",
        rule_key="dialog.quotes",
        value={"instruction": "Use Polish quotes style with em dash in dialogues."},
    )
    src_store.upsert_lore_entry(
        "alpha",
        entry_key="world-magic",
        title="World Magic",
        content="Magic relies on crystal resonance.",
        tags=["world", "magic"],
        status="active",
    )
    exported = src_store.export_series_profile("alpha")
    assert exported.exists()

    dst_store = SeriesStore(tmp_path / "dst_series")
    dst_store.ensure_series_db("beta", display_name="Beta")
    stats = dst_store.import_series_profile("beta", exported)
    assert int(stats["style_added"]) >= 1
    assert int(stats["lore_added"]) >= 1
    assert int(stats["terms_added"]) >= 1
    assert any(str(r["rule_key"]) == "dialog.quotes" for r in dst_store.list_style_rules("beta"))
    assert any(str(r["entry_key"]) == "world-magic" for r in dst_store.list_lore_entries("beta"))
    assert ("Void Gate", "Brama Pustki") in dst_store.list_approved_terms("beta")


def test_project_db_list_projects_for_series_sorted_by_volume(tmp_path: Path) -> None:
    db = ProjectDB(tmp_path / "studio.db")
    sid = db.ensure_series("Saga Sort", source="manual")
    db.create_project(
        "Tom 2",
        {
            "series_id": sid,
            "volume_no": 2.0,
            "input_epub": str(tmp_path / "b2.epub"),
            "output_translate_epub": str(tmp_path / "b2_pl.epub"),
            "output_edit_epub": str(tmp_path / "b2_pl_edit.epub"),
        },
    )
    db.create_project(
        "Tom 1",
        {
            "series_id": sid,
            "volume_no": 1.0,
            "input_epub": str(tmp_path / "b1.epub"),
            "output_translate_epub": str(tmp_path / "b1_pl.epub"),
            "output_edit_epub": str(tmp_path / "b1_pl_edit.epub"),
        },
    )
    db.create_project(
        "Tom ?",
        {
            "series_id": sid,
            "volume_no": None,
            "input_epub": str(tmp_path / "bx.epub"),
            "output_translate_epub": str(tmp_path / "bx_pl.epub"),
            "output_edit_epub": str(tmp_path / "bx_pl_edit.epub"),
        },
    )
    rows = db.list_projects_for_series(sid)
    names = [str(r["name"]) for r in rows]
    assert names[:2] == ["Tom 1", "Tom 2"]
    assert names[-1] == "Tom ?"
    db.close()
