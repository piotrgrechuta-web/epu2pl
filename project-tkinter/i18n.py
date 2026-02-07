#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

_HTTP = requests.Session()
LOG = logging.getLogger(__name__)


SUPPORTED_UI_LANGS: Dict[str, str] = {
    "pl": "Polski",
    "en": "English",
    "de": "Deutsch",
    "fr": "Francais",
    "es": "Espanol",
    "pt": "Portugues",
}

SUPPORTED_TEXT_LANGS: Dict[str, str] = {
    "en": "English",
    "pl": "Polish",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
}


class I18NManager:
    def __init__(self, locales_dir: Path, lang: str = "pl") -> None:
        self.locales_dir = locales_dir
        self.locales_dir.mkdir(parents=True, exist_ok=True)
        self.lang = (lang or "pl").strip().lower()
        if self.lang not in SUPPORTED_UI_LANGS:
            self.lang = "pl"
        self._cache: Dict[str, Dict[str, str]] = {}

    def set_lang(self, lang: str) -> None:
        code = (lang or "").strip().lower()
        if code in SUPPORTED_UI_LANGS:
            self.lang = code

    def clear_cache(self) -> None:
        self._cache.clear()

    def _load(self, code: str) -> Dict[str, str]:
        c = (code or "").strip().lower()
        if c in self._cache:
            return self._cache[c]
        p = self.locales_dir / f"{c}.json"
        if not p.exists():
            self._cache[c] = {}
            return self._cache[c]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception as e:
            LOG.warning("Failed to load locale file '%s': %s", p, e)
            data = {}
        out: Dict[str, str] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        self._cache[c] = out
        return out

    def t(self, key: str, default: Optional[str] = None, **fmt: Any) -> str:
        cur = self._load(self.lang)
        en = self._load("en")
        val = cur.get(key)
        if val is None:
            val = en.get(key, default if default is not None else key)
        if fmt:
            try:
                return str(val).format(**fmt)
            except Exception:
                return str(val)
        return str(val)

    def english_map(self) -> Dict[str, str]:
        return dict(self._load("en"))

    def locale_map(self, code: str) -> Dict[str, str]:
        return dict(self._load(code))

    def save_locale(self, code: str, mapping: Dict[str, str]) -> Path:
        c = (code or "").strip().lower()
        p = self.locales_dir / f"{c}.json"
        p.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache.pop(c, None)
        return p

    def save_draft(self, code: str, mapping: Dict[str, str]) -> Path:
        c = (code or "").strip().lower()
        p = self.locales_dir / f"{c}.draft.json"
        p.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        return p


def _extract_json_object(text: str) -> Dict[str, str]:
    s = (text or "").strip()
    if not s:
        return {}
    try:
        raw = json.loads(s)
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return {}
    try:
        raw = json.loads(m.group(0))
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        return {}
    return {}


def _build_ai_prompt(base_map: Dict[str, str], target_lang_name: str) -> str:
    payload = json.dumps(base_map, ensure_ascii=False, indent=2)
    return (
        f"Translate JSON values to {target_lang_name}. "
        "Keep keys unchanged. Return ONLY valid JSON object with same keys.\n\n"
        f"{payload}"
    )


def ai_translate_gui_labels(
    *,
    base_map: Dict[str, str],
    target_lang_code: str,
    provider: str,
    model: str,
    ollama_host: str,
    google_api_key: str,
    timeout_s: int = 60,
) -> Tuple[bool, Dict[str, str], str]:
    target_name = SUPPORTED_UI_LANGS.get(target_lang_code, target_lang_code)
    prompt = _build_ai_prompt(base_map, target_name)
    try:
        if provider == "google":
            key = (google_api_key or "").strip()
            if not key:
                return False, {}, "Missing Google API key."
            m = model if model.startswith("models/") else f"models/{model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent"
            headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0},
            }
            r = _HTTP.post(url, headers=headers, data=json.dumps(body, ensure_ascii=False), timeout=timeout_s)
            if r.status_code < 200 or r.status_code >= 300:
                return False, {}, f"HTTP {r.status_code}: {r.text[:300]}"
            data = r.json()
            txt = ""
            for c in data.get("candidates", []) or []:
                parts = ((c.get("content") or {}).get("parts") or [])
                for p in parts:
                    if isinstance(p, dict) and isinstance(p.get("text"), str):
                        txt += p["text"] + "\n"
            out = _extract_json_object(txt)
            if not out:
                return False, {}, "Could not parse JSON from Google response."
            return True, out, "ok"

        url = (ollama_host or "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }
        r = _HTTP.post(url, data=json.dumps(body, ensure_ascii=False), timeout=timeout_s)
        if r.status_code < 200 or r.status_code >= 300:
            return False, {}, f"HTTP {r.status_code}: {r.text[:300]}"
        data = r.json()
        txt = str(data.get("response", ""))
        out = _extract_json_object(txt)
        if not out:
            return False, {}, "Could not parse JSON from Ollama response."
        return True, out, "ok"
    except Exception as e:
        return False, {}, str(e)
