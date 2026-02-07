#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import requests


def build_overdue_payload(project_name: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "event": "qa_overdue_alert",
        "project": project_name,
        "overdue_count": len(findings),
        "items": findings[:100],
    }


def send_webhook(url: str, payload: Dict[str, Any], timeout_s: int = 12) -> Tuple[bool, str]:
    u = (url or "").strip()
    if not u:
        return False, "Webhook URL empty."
    try:
        r = requests.post(u, data=json.dumps(payload, ensure_ascii=False), headers={"Content-Type": "application/json"}, timeout=timeout_s)
        if 200 <= r.status_code < 300:
            return True, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}: {r.text[:400]}"
    except Exception as e:
        return False, str(e)

