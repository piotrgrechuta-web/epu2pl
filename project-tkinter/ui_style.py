#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict
import tkinter as tk
from tkinter import ttk


BASE_TOKENS: Dict[str, Any] = {
    "app_bg": "#eef3f7",
    "card_bg": "#ffffff",
    "surface_bg": "#f8fafc",
    "border": "#cbd5e1",
    "text": "#0f172a",
    "muted": "#334155",
    "title": "#020617",
    "btn_primary_bg": "#0b766e",
    "btn_primary_active": "#0a5f59",
    "btn_primary_fg": "#ffffff",
    "btn_secondary_bg": "#e2e8f0",
    "btn_secondary_active": "#cbd5e1",
    "btn_secondary_fg": "#0f172a",
    "btn_danger_bg": "#b42318",
    "btn_danger_active": "#912018",
    "btn_danger_fg": "#ffffff",
    "status_ready": "#334155",
    "status_run": "#9a6700",
    "status_ok": "#166534",
    "status_err": "#b42318",
    "inline_info_bg": "#dbeafe",
    "inline_info_fg": "#1e3a8a",
    "inline_warn_bg": "#fef3c7",
    "inline_warn_fg": "#92400e",
    "inline_err_bg": "#fee2e2",
    "inline_err_fg": "#991b1b",
    "font": "Segoe UI",
    "font_semi": "Segoe UI Semibold",
    "title_size": 18,
}

HORIZON_PATCH: Dict[str, Any] = {
    "app_bg": "#e9eef4",
    "text": "#14202b",
    "muted": "#5e6b78",
    "title": "#0b1220",
    "btn_primary_bg": "#0f766e",
    "btn_primary_active": "#0d675f",
}

SPACING: Dict[str, int] = {
    "space_xs": 4,
    "space_sm": 8,
    "space_md": 12,
    "space_lg": 16,
    "space_xl": 20,
}


def _theme_tokens(variant: str) -> Dict[str, Any]:
    out = dict(BASE_TOKENS)
    if (variant or "").strip().lower() == "horizon":
        out.update(HORIZON_PATCH)
    out.update(SPACING)
    return out


def apply_app_theme(root: tk.Misc, *, variant: str = "base") -> Dict[str, Any]:
    tokens = _theme_tokens(variant)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=tokens["app_bg"])

    style.configure("TFrame", background=tokens["app_bg"])
    style.configure("Card.TFrame", background=tokens["card_bg"], relief="flat")

    style.configure("TLabel", background=tokens["app_bg"], foreground=tokens["text"], font=(tokens["font"], 10))
    style.configure(
        "Title.TLabel",
        background=tokens["app_bg"],
        foreground=tokens["title"],
        font=(tokens["font_semi"], int(tokens["title_size"])),
    )
    style.configure("Sub.TLabel", background=tokens["app_bg"], foreground=tokens["muted"], font=(tokens["font"], 10))
    style.configure("Helper.TLabel", background=tokens["app_bg"], foreground=tokens["muted"], font=(tokens["font"], 9))

    style.configure(
        "InlineInfo.TLabel",
        background=tokens["inline_info_bg"],
        foreground=tokens["inline_info_fg"],
        padding=(10, 6),
        font=(tokens["font_semi"], 10),
    )
    style.configure(
        "InlineWarn.TLabel",
        background=tokens["inline_warn_bg"],
        foreground=tokens["inline_warn_fg"],
        padding=(10, 6),
        font=(tokens["font_semi"], 10),
    )
    style.configure(
        "InlineErr.TLabel",
        background=tokens["inline_err_bg"],
        foreground=tokens["inline_err_fg"],
        padding=(10, 6),
        font=(tokens["font_semi"], 10),
    )

    style.configure("TButton", font=(tokens["font_semi"], 10), padding=8)
    style.configure("Primary.TButton", background=tokens["btn_primary_bg"], foreground=tokens["btn_primary_fg"])
    style.map(
        "Primary.TButton",
        background=[("active", tokens["btn_primary_active"]), ("pressed", tokens["btn_primary_active"])],
    )
    style.configure("Secondary.TButton", background=tokens["btn_secondary_bg"], foreground=tokens["btn_secondary_fg"])
    style.map(
        "Secondary.TButton",
        background=[("active", tokens["btn_secondary_active"]), ("pressed", tokens["btn_secondary_active"])],
    )
    style.configure("Danger.TButton", background=tokens["btn_danger_bg"], foreground=tokens["btn_danger_fg"])
    style.map(
        "Danger.TButton",
        background=[("active", tokens["btn_danger_active"]), ("pressed", tokens["btn_danger_active"])],
    )

    style.configure(
        "TEntry",
        padding=7,
        fieldbackground=tokens["surface_bg"],
        foreground=tokens["text"],
        bordercolor=tokens["border"],
    )
    style.configure(
        "TCombobox",
        padding=7,
        fieldbackground=tokens["surface_bg"],
        foreground=tokens["text"],
        bordercolor=tokens["border"],
        arrowsize=14,
    )

    style.configure("Card.TLabelframe", background=tokens["card_bg"], borderwidth=1, relief="solid")
    style.configure(
        "Card.TLabelframe.Label",
        background=tokens["card_bg"],
        foreground=tokens["title"],
        font=(tokens["font_semi"], 10),
    )
    style.configure("TLabelframe", background=tokens["card_bg"], borderwidth=1, relief="solid")
    style.configure(
        "TLabelframe.Label",
        background=tokens["card_bg"],
        foreground=tokens["title"],
        font=(tokens["font_semi"], 10),
    )

    style.configure("StatusReady.TLabel", background=tokens["app_bg"], foreground=tokens["status_ready"], font=(tokens["font"], 10))
    style.configure("StatusRun.TLabel", background=tokens["app_bg"], foreground=tokens["status_run"], font=(tokens["font_semi"], 10))
    style.configure("StatusOk.TLabel", background=tokens["app_bg"], foreground=tokens["status_ok"], font=(tokens["font_semi"], 10))
    style.configure("StatusErr.TLabel", background=tokens["app_bg"], foreground=tokens["status_err"], font=(tokens["font_semi"], 10))

    style.configure("TNotebook", background=tokens["app_bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 8), font=(tokens["font_semi"], 10))
    style.map("TNotebook.Tab", background=[("selected", tokens["card_bg"]), ("!selected", "#d7e0ea")])

    return tokens

