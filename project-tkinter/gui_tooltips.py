#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional, Union


TextSource = Union[str, Callable[[], str]]


class Tooltip:
    def __init__(self, widget: tk.Misc, text: TextSource, delay_ms: int = 450) -> None:
        self.widget = widget
        self._text_source = text
        self.delay_ms = delay_ms
        self._tip_win: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None
        self._bound = False
        self._bind()

    def _text(self) -> str:
        try:
            if callable(self._text_source):
                return str(self._text_source() or "").strip()
            return str(self._text_source or "").strip()
        except Exception:
            return ""

    def _bind(self) -> None:
        if self._bound:
            return
        self._bound = True
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
        self.widget.bind("<Destroy>", self._on_destroy, add="+")

    def _on_enter(self, _event: object = None) -> None:
        if not self._text():
            return
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event: object = None) -> None:
        self._cancel()
        self._hide()

    def _on_destroy(self, _event: object = None) -> None:
        self._cancel()
        self._hide()

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._tip_win is not None:
            return
        if not self.widget.winfo_exists():
            return
        text = self._text()
        if not text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(background="#0f172a")
        lbl = tk.Label(
            tw,
            text=text,
            justify="left",
            wraplength=420,
            background="#0f172a",
            foreground="#e2e8f0",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
        )
        lbl.pack(fill="both", expand=True)
        self._tip_win = tw

    def _hide(self) -> None:
        if self._tip_win is not None:
            try:
                self._tip_win.destroy()
            except Exception:
                pass
            self._tip_win = None


def install_tooltips(root: tk.Misc, resolver: Callable[[tk.Misc], Optional[str]]) -> List[Tooltip]:
    tips: List[Tooltip] = []
    stack: List[tk.Misc] = [root]
    while stack:
        w = stack.pop()
        try:
            children = list(w.winfo_children())
        except Exception:
            children = []
        stack.extend(children)
        tips.append(Tooltip(w, lambda x=w: resolver(x) or ""))
    return tips
