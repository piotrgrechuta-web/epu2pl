#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, Iterable


def choose_assignee(
    *,
    rule_code: str,
    severity: str,
    rules: Dict[str, Any],
    current_load: Dict[str, int],
) -> str:
    rule_map = rules.get("rule_code", {}) if isinstance(rules.get("rule_code"), dict) else {}
    sev_map = rules.get("severity", {}) if isinstance(rules.get("severity"), dict) else {}
    default_assignee = str(rules.get("default", "reviewer")).strip() or "reviewer"
    max_open = int(rules.get("max_open_per_assignee", 10_000))

    assignee = str(rule_map.get(rule_code, "")).strip()
    if not assignee:
        assignee = str(sev_map.get(severity, "")).strip()
    if not assignee:
        assignee = default_assignee

    if current_load.get(assignee, 0) < max_open:
        return assignee

    # Fallback to least loaded assignee among configured buckets.
    candidates = set([default_assignee])
    candidates.update(str(v).strip() for v in rule_map.values() if str(v).strip())
    candidates.update(str(v).strip() for v in sev_map.values() if str(v).strip())
    best = min(candidates, key=lambda a: current_load.get(a, 0))
    return best


def build_load_map(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        ass = str(r.get("assignee", "")).strip() or "unassigned"
        out[ass] = out.get(ass, 0) + 1
    return out

