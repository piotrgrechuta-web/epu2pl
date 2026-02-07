#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import hashlib
import os
import posixpath
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from lxml import etree


XHTML_NS = "http://www.w3.org/1999/xhtml"
OPF_NS = "http://www.idpf.org/2007/opf"
LEGACY_SEGMENT_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "dd", "dt", "figcaption", "caption")
SEGMENT_EXCLUDED_TAGS = {"html", "body", "head", "script", "style", "svg", "math", "meta", "link", "title"}
SEGMENT_EXCLUDED_ANCESTORS = {"head", "script", "style", "svg", "math"}
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
FRONT_MATTER_TEMPLATE = Path(__file__).resolve().parent / "assets" / "templates" / "front_matter_card.xhtml"
FALLBACK_FRONT_MATTER_TEMPLATE = Path(__file__).resolve().parent / "assets" / "templates" / "front_matter_card.default.xhtml"
INLINE_FRONT_MATTER_TEMPLATE = '<html xmlns="__XHTML_NS__"><body><p><img src="../__IMG_HREF__" alt="__TITLE__"/></p></body></html>'


def _decode(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def _join_opf_path(opf_path: str, href: str) -> str:
    base = posixpath.dirname(opf_path)
    return posixpath.normpath(posixpath.join(base, href))


def _read_opf_path(zf: zipfile.ZipFile) -> str:
    c = _decode(zf.read("META-INF/container.xml"))
    root = etree.fromstring(c.encode("utf-8"))
    rp = root.xpath("//*[local-name()='rootfile']/@full-path")
    if not rp:
        raise RuntimeError("Brak OPF w container.xml")
    return str(rp[0])


@dataclass
class EpubModel:
    opf_path: str
    opf_root: etree._Element
    opf_tree: etree._ElementTree
    manifest: etree._Element
    spine: etree._Element
    metadata: etree._Element
    ns: Dict[str, str]


def _load_model(zf: zipfile.ZipFile) -> EpubModel:
    opf_path = _read_opf_path(zf)
    raw = _decode(zf.read(opf_path))
    parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
    root = etree.fromstring(raw.encode("utf-8"), parser=parser)
    ns = {"opf": OPF_NS}
    manifest = root.find(".//{*}manifest")
    spine = root.find(".//{*}spine")
    metadata = root.find(".//{*}metadata")
    if manifest is None or spine is None or metadata is None:
        raise RuntimeError("Niepoprawny OPF (manifest/spine/metadata)")
    return EpubModel(opf_path=opf_path, opf_root=root, opf_tree=root.getroottree(), manifest=manifest, spine=spine, metadata=metadata, ns=ns)


def _write_epub_with_changes(input_epub: Path, output_epub: Path, changed: Dict[str, bytes]) -> Path:
    output_epub.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_epub.with_suffix(output_epub.suffix + ".tmp")
    with zipfile.ZipFile(input_epub, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
        names = zin.namelist()
        if "mimetype" in names:
            mi = zin.getinfo("mimetype")
            zout.writestr(mi, zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name in names:
            if name == "mimetype":
                continue
            if name in changed:
                data = changed[name]
            else:
                data = zin.read(name)
            zout.writestr(name, data)
    os.replace(tmp, output_epub)
    return output_epub


def _next_manifest_id(model: EpubModel, prefix: str) -> str:
    ids = {str(i.get("id") or "") for i in model.manifest.findall("{*}item")}
    if prefix not in ids:
        return prefix
    idx = 2
    while f"{prefix}-{idx}" in ids:
        idx += 1
    return f"{prefix}-{idx}"


def _guess_media_type(image_path: Path) -> str:
    ext = image_path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "application/octet-stream"


def _render_front_matter_xhtml(title: str, img_href: str) -> str:
    tpl = INLINE_FRONT_MATTER_TEMPLATE
    for path in (FRONT_MATTER_TEMPLATE, FALLBACK_FRONT_MATTER_TEMPLATE):
        try:
            if path.exists():
                tpl = path.read_text(encoding="utf-8")
                break
        except Exception:
            continue
    safe_title = xml_escape(str(title or "Wizytowka"), {'"': "&quot;"})
    safe_img_href = xml_escape(str(img_href or ""), {'"': "&quot;"})
    return (
        tpl.replace("__XHTML_NS__", XHTML_NS)
        .replace("__TITLE__", safe_title)
        .replace("__IMG_HREF__", safe_img_href)
    )


def add_front_matter_card(
    input_epub: Path,
    output_epub: Path,
    image_path: Path,
    title: str = "Wizytowka",
) -> Path:
    if not image_path.exists():
        raise FileNotFoundError(f"Brak obrazka: {image_path}")
    changed: Dict[str, bytes] = {}
    with zipfile.ZipFile(input_epub, "r") as zin:
        model = _load_model(zin)
        opf_dir = posixpath.dirname(model.opf_path)
        img_item_id = _next_manifest_id(model, "vis-card-img")
        page_item_id = _next_manifest_id(model, "vis-card-page")
        img_name = f"vis-card{image_path.suffix.lower()}"
        page_name = "vis-card.xhtml"
        img_href = img_name if not opf_dir else posixpath.join("assets", img_name)
        page_href = page_name if not opf_dir else posixpath.join("text", page_name)

        item_img = etree.Element(f"{{{OPF_NS}}}item")
        item_img.set("id", img_item_id)
        item_img.set("href", img_href)
        item_img.set("media-type", _guess_media_type(image_path))
        model.manifest.append(item_img)

        item_page = etree.Element(f"{{{OPF_NS}}}item")
        item_page.set("id", page_item_id)
        item_page.set("href", page_href)
        item_page.set("media-type", "application/xhtml+xml")
        model.manifest.append(item_page)

        itemref = etree.Element(f"{{{OPF_NS}}}itemref")
        itemref.set("idref", page_item_id)
        if len(model.spine):
            model.spine.insert(0, itemref)
        else:
            model.spine.append(itemref)

        xhtml = _render_front_matter_xhtml(title=title, img_href=img_href)
        opf_bytes = etree.tostring(model.opf_root, encoding="utf-8", xml_declaration=True, pretty_print=True)
        changed[model.opf_path] = opf_bytes
        page_zip_path = _join_opf_path(model.opf_path, page_href)
        img_zip_path = _join_opf_path(model.opf_path, img_href)
        changed[page_zip_path] = xhtml.encode("utf-8")
        changed[img_zip_path] = image_path.read_bytes()
    return _write_epub_with_changes(input_epub, output_epub, changed)


def preview_add_front_matter(input_epub: Path, image_path: Path, title: str = "Wizytowka") -> Dict[str, Any]:
    if not image_path.exists():
        raise FileNotFoundError(f"Brak obrazka: {image_path}")
    with zipfile.ZipFile(input_epub, "r") as zin:
        model = _load_model(zin)
        opf_dir = posixpath.dirname(model.opf_path)
        img_name = f"vis-card{image_path.suffix.lower()}"
        page_name = "vis-card.xhtml"
        img_href = img_name if not opf_dir else posixpath.join("assets", img_name)
        page_href = page_name if not opf_dir else posixpath.join("text", page_name)
        return {
            "epub": str(input_epub),
            "title": title,
            "add_manifest_items": [img_href, page_href],
            "add_spine_first": page_href,
            "image_file": str(image_path),
            "opf_path": model.opf_path,
        }


def batch_add_front_matter(folder: Path, image_path: Path, title: str) -> List[Tuple[Path, Optional[str]]]:
    results: List[Tuple[Path, Optional[str]]] = []
    for epub in sorted(folder.glob("*.epub")):
        out = epub.with_name(f"{epub.stem}_wizytowka{epub.suffix}")
        try:
            add_front_matter_card(epub, out, image_path, title=title)
            results.append((out, None))
        except Exception as e:
            results.append((epub, str(e)))
    return results


def remove_images(
    input_epub: Path,
    output_epub: Path,
    remove_cover: bool,
    pattern: Optional[str],
) -> Path:
    changed: Dict[str, bytes] = {}
    pat = re.compile(pattern, re.IGNORECASE) if pattern else None
    with zipfile.ZipFile(input_epub, "r") as zin:
        model = _load_model(zin)
        manifest_items = list(model.manifest.findall("{*}item"))
        remove_item_ids: set[str] = set()
        remove_paths: set[str] = set()

        cover_id = None
        for meta in model.metadata.findall("{*}meta"):
            if (meta.get("name") or "").lower() == "cover":
                cover_id = meta.get("content")
                if remove_cover:
                    parent = meta.getparent()
                    if parent is not None:
                        parent.remove(meta)

        for item in manifest_items:
            media = (item.get("media-type") or "").lower()
            href = str(item.get("href") or "")
            iid = str(item.get("id") or "")
            is_img = media.startswith("image/")
            matches_pattern = bool(pat.search(href)) if pat else False
            matches_cover = remove_cover and ((cover_id and iid == cover_id) or ("cover" in href.lower()))
            if is_img and (matches_pattern or matches_cover):
                remove_item_ids.add(iid)
                remove_paths.add(_join_opf_path(model.opf_path, href))
                parent = item.getparent()
                if parent is not None:
                    parent.remove(item)

        # Remove cover pages in spine if requested
        if remove_cover:
            id_to_href: Dict[str, str] = {}
            for item in model.manifest.findall("{*}item"):
                iid = str(item.get("id") or "")
                href = str(item.get("href") or "")
                id_to_href[iid] = href
            for itemref in list(model.spine.findall("{*}itemref")):
                idref = str(itemref.get("idref") or "")
                href = id_to_href.get(idref, "")
                if "cover" in href.lower():
                    parent = itemref.getparent()
                    if parent is not None:
                        parent.remove(itemref)

        names = zin.namelist()
        parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
        for name in names:
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            try:
                raw = zin.read(name)
                root = etree.fromstring(raw, parser=parser)
            except Exception:
                continue
            changed_this = False
            for img in list(root.findall(".//{*}img")):
                src = str(img.get("src") or "")
                if not src:
                    continue
                local = posixpath.normpath(posixpath.join(posixpath.dirname(name), src))
                should_remove = local in remove_paths
                if not should_remove and pat is not None:
                    should_remove = bool(pat.search(src))
                if should_remove:
                    parent = img.getparent()
                    if parent is not None:
                        parent.remove(img)
                        changed_this = True
            if changed_this:
                changed[name] = etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=False)

        opf_bytes = etree.tostring(model.opf_root, encoding="utf-8", xml_declaration=True, pretty_print=True)
        changed[model.opf_path] = opf_bytes

    # Write new EPUB and skip removed assets
    output_epub.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_epub.with_suffix(output_epub.suffix + ".tmp")
    with zipfile.ZipFile(input_epub, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
        names = zin.namelist()
        if "mimetype" in names:
            mi = zin.getinfo("mimetype")
            zout.writestr(mi, zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name in names:
            if name == "mimetype":
                continue
            if name in remove_paths:
                continue
            data = changed[name] if name in changed else zin.read(name)
            zout.writestr(name, data)
    os.replace(tmp, output_epub)
    return output_epub


def preview_remove_images(
    input_epub: Path,
    remove_cover: bool,
    pattern: Optional[str],
) -> Dict[str, Any]:
    pat = re.compile(pattern, re.IGNORECASE) if pattern else None
    with zipfile.ZipFile(input_epub, "r") as zin:
        model = _load_model(zin)
        manifest_items = list(model.manifest.findall("{*}item"))
        remove_paths: set[str] = set()
        remove_item_ids: set[str] = set()
        cover_id = None
        for meta in model.metadata.findall("{*}meta"):
            if (meta.get("name") or "").lower() == "cover":
                cover_id = meta.get("content")
        for item in manifest_items:
            media = (item.get("media-type") or "").lower()
            href = str(item.get("href") or "")
            iid = str(item.get("id") or "")
            is_img = media.startswith("image/")
            matches_pattern = bool(pat.search(href)) if pat else False
            matches_cover = remove_cover and ((cover_id and iid == cover_id) or ("cover" in href.lower()))
            if is_img and (matches_pattern or matches_cover):
                remove_item_ids.add(iid)
                remove_paths.add(_join_opf_path(model.opf_path, href))

        affected_chapters: List[str] = []
        names = zin.namelist()
        parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
        for name in names:
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            try:
                raw = zin.read(name)
                root = etree.fromstring(raw, parser=parser)
            except Exception:
                continue
            for img in list(root.findall(".//{*}img")):
                src = str(img.get("src") or "")
                local = posixpath.normpath(posixpath.join(posixpath.dirname(name), src)) if src else ""
                should_remove = local in remove_paths
                if not should_remove and pat is not None:
                    should_remove = bool(pat.search(src))
                if should_remove:
                    affected_chapters.append(name)
                    break
        return {
            "epub": str(input_epub),
            "remove_cover": remove_cover,
            "pattern": pattern or "",
            "remove_paths_count": len(remove_paths),
            "remove_paths": sorted(remove_paths),
            "affected_chapters_count": len(affected_chapters),
            "affected_chapters": affected_chapters[:40],
            "remove_manifest_ids_count": len(remove_item_ids),
        }


def _find_spine_chapters(zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
    model = _load_model(zf)
    manifest = {str(i.get("id") or ""): str(i.get("href") or "") for i in model.manifest.findall("{*}item")}
    out: List[Tuple[str, str]] = []
    for itemref in model.spine.findall("{*}itemref"):
        rid = str(itemref.get("idref") or "")
        href = manifest.get(rid, "")
        if not href:
            continue
        path = _join_opf_path(model.opf_path, href)
        out.append((rid, path))
    return out


def list_chapters(epub_path: Path) -> List[Tuple[str, str]]:
    with zipfile.ZipFile(epub_path, "r") as zf:
        return _find_spine_chapters(zf)


def load_chapter_segments(
    epub_path: Path, chapter_path: str, segment_mode: str = "auto"
) -> Tuple[etree._Element, List[etree._Element], List[str], bytes]:
    with zipfile.ZipFile(epub_path, "r") as zf:
        raw = zf.read(chapter_path)
    parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
    root = etree.fromstring(raw, parser=parser)
    mode = (segment_mode or "auto").strip().lower()
    segs: List[etree._Element] = []
    segment_ids: List[str] = []
    selected_ids: set[int] = set()

    def _lname(el: etree._Element) -> str:
        tag = getattr(el, "tag", "")
        if not isinstance(tag, str):
            return ""
        return tag.split("}", 1)[-1].lower()

    def _has_excluded_ancestor(el: etree._Element) -> bool:
        p = el.getparent()
        while p is not None:
            if _lname(p) in SEGMENT_EXCLUDED_ANCESTORS:
                return True
            p = p.getparent()
        return False

    if mode == "legacy":
        for tag in LEGACY_SEGMENT_TAGS:
            for el in root.findall(f".//{{*}}{tag}"):
                segs.append(el)
                segment_ids.append(_stable_segment_id(chapter_path, el))
    else:
        for el in root.iter():
            name = _lname(el)
            if not name or name in SEGMENT_EXCLUDED_TAGS:
                continue
            if _has_excluded_ancestor(el):
                continue
            if not (el.text or "").strip():
                continue
            # Keep first translatable ancestor to avoid nested duplicate segments.
            p = el.getparent()
            skip = False
            while p is not None:
                if id(p) in selected_ids:
                    skip = True
                    break
                p = p.getparent()
            if skip:
                continue
            segs.append(el)
            segment_ids.append(_stable_segment_id(chapter_path, el))
            selected_ids.add(id(el))
    return root, segs, segment_ids, raw


def _stable_segment_id(chapter_path: str, el: etree._Element) -> str:
    tree = el.getroottree()
    try:
        xpath = tree.getpath(el)
    except Exception:
        xpath = ""
    txt = etree.tostring(el, encoding="unicode", method="text").strip()
    txt_hash = hashlib.sha1(txt.encode("utf-8", errors="replace")).hexdigest()
    raw = f"{chapter_path}|{xpath}|{txt_hash}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def save_chapter_changes(epub_path: Path, chapter_path: str, root: etree._Element) -> Tuple[Path, Path]:
    changed = {chapter_path: etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=False)}
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = epub_path.with_name(f"{epub_path.stem}.bak-edit-{ts}{epub_path.suffix}")
    shutil.copy2(epub_path, backup)
    out = _write_epub_with_changes(epub_path, epub_path, changed)
    return out, backup
