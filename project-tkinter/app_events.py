#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import atexit
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict

_BUFFER_LIMIT = 20
_LOCK = threading.Lock()
_BUFFERS: Dict[Path, list[str]] = {}


def _write_lines(log_path: Path, lines: list[str]) -> None:
    if not lines:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.writelines(lines)


def flush_event_log(log_path: Path | None = None) -> None:
    with _LOCK:
        if log_path is None:
            pending = [(p, list(lines)) for p, lines in _BUFFERS.items() if lines]
            _BUFFERS.clear()
        else:
            path = Path(log_path)
            lines = list(_BUFFERS.get(path, []))
            _BUFFERS.pop(path, None)
            pending = [(path, lines)] if lines else []
    for p, lines in pending:
        _write_lines(p, lines)


def log_event_jsonl(log_path: Path, event_type: str, payload: Dict[str, Any]) -> None:
    path = Path(log_path)
    rec = {
        "ts": int(time.time()),
        "event": str(event_type),
        "payload": payload,
    }
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    to_flush: list[str] = []
    with _LOCK:
        bucket = _BUFFERS.setdefault(path, [])
        bucket.append(line)
        if len(bucket) >= _BUFFER_LIMIT:
            to_flush = list(bucket)
            bucket.clear()
    if to_flush:
        _write_lines(path, to_flush)


atexit.register(flush_event_log)
