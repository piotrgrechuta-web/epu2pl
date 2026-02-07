#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import start as base


base.APP_TITLE = "Translator Studio Horizon"


class HorizonGUI(base.TranslatorGUI):
    def _setup_theme(self) -> None:
        self.root.configure(bg="#e9eef4")
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TFrame", background="#e9eef4")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#e9eef4", foreground="#14202b", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#e9eef4", foreground="#0b1220", font=("Segoe UI Semibold", 26))
        style.configure("Sub.TLabel", background="#e9eef4", foreground="#5e6b78", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=8)
        style.configure("Accent.TButton", background="#0f766e", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#0d675f")])
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=7)
        style.configure("TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#0b1220", font=("Segoe UI Semibold", 10))
        style.configure("StatusReady.TLabel", background="#e9eef4", foreground="#4b5563", font=("Segoe UI", 10))
        style.configure("StatusRun.TLabel", background="#e9eef4", foreground="#b45309", font=("Segoe UI Semibold", 10))
        style.configure("StatusOk.TLabel", background="#e9eef4", foreground="#166534", font=("Segoe UI Semibold", 10))
        style.configure("StatusErr.TLabel", background="#e9eef4", foreground="#b91c1c", font=("Segoe UI Semibold", 10))
        style.configure("TNotebook", background="#e9eef4", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff"), ("!selected", "#dbe4ee")])

    def _build_ui(self) -> None:
        self.root.title("Translator Studio Horizon")
        outer = ttk.Frame(self.root, padding=18, style="TFrame")
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Card.TFrame", padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Translator Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Desktop UI w stylu web: czytelniejszy układ, większe sekcje i spójna typografia.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        tabs_wrap = ttk.Frame(outer, style="Card.TFrame", padding=10)
        tabs_wrap.pack(fill="both", expand=True, pady=(14, 0))
        tabs = ttk.Notebook(tabs_wrap)
        tabs.pack(fill="both", expand=True)

        files_tab = ttk.Frame(tabs, padding=8)
        engine_tab = ttk.Frame(tabs, padding=8)
        log_tab = ttk.Frame(tabs, padding=8)
        layout_tab = ttk.Frame(tabs, padding=8)

        tabs.add(files_tab, text="Pliki i Tryb")
        tabs.add(engine_tab, text="Silnik i Model")
        tabs.add(log_tab, text="Log")
        tabs.add(layout_tab, text="Układanie EPUB")

        self._build_project_card(files_tab)
        self._build_files_card(files_tab)
        self._build_run_card(files_tab)

        self._build_engine_card(engine_tab)
        self._build_model_card(engine_tab)
        self._build_advanced_card(engine_tab)

        self._build_log_card(log_tab)
        # Własna zakładka dla sekcji układania EPUB.
        old_tr = self.tr
        self.tr = lambda key, default, **fmt: old_tr(key, "Układanie EPUB" if key == "section.enhance" else default, **fmt)
        try:
            self._build_enhance_card(layout_tab)
        finally:
            self.tr = old_tr

        self.status_label = ttk.Label(outer, textvariable=self.status_var, style="StatusReady.TLabel")
        self.status_label.pack(anchor="w", pady=(10, 0))


def main() -> int:
    root = tk.Tk()
    HorizonGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
