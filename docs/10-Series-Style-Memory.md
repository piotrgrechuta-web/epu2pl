# 10. Series Style Memory + Batch Library (M7)

Status: `domkniete` (2026-02-09).

Dokument opisuje finalny zakres M7 po wdrozeniu warstwy stylu/lore i orchestratora batch serii.

## 10.1. Co zostalo wdrozone

1. Przypisanie projektu do serii:
- tabela `series` w `translator_studio.db`,
- pola `projects.series_id` i `projects.volume_no`.

2. Autodetekcja serii z EPUB:
- parser metadanych OPF (`calibre:series`, `belongs-to-collection`, indeks tomu),
- fallback po tytule (`Book/Vol/Tom`).

3. Per-seria magazyn danych:
- `project-tkinter/data/series/<slug>/series.db`,
- tabele: `terms`, `decisions`, `lore_entries`, `style_rules`, `change_log`.

4. Series Manager (GUI):
- zakladki: `Termy`, `Style rules`, `Lorebook`, `Historia`,
- approve/reject terminow, manual add, learn from TM, eksport glosariusza,
- edycja `style_rules` i `lore_entries`,
- import/export profilu serii (`series_profile.json`),
- historia zmian (audit/versioning) per wpis.

5. Runtime:
- przy runie budowany jest scalony glosariusz (seria + projekt),
- prompt jest augmentowany kontekstem serii (style rules + active lore + approved terms),
- po udanym runie TM projektu zasila propozycje terminow serii.

6. Batch Library (seria):
- queue calej serii dla kroku `translate` lub `edit`,
- uruchomienie batch serii jednym kliknieciem (`Run series batch`),
- raport zbiorczy serii `series_batch_report_*.json/.md`.

## 10.2. Dane i pliki

- GLOWNA baza: `project-tkinter/translator_studio.db`
- Baza serii: `project-tkinter/data/series/<slug>/series.db`
- Eksport serii: `project-tkinter/data/series/<slug>/generated/approved_glossary.txt`
- Merge glosariusza per run: `project-tkinter/data/series/<slug>/generated/merged_glossary_project_<id>.txt`
- Prompt augmentowany serii: `project-tkinter/data/series/<slug>/generated/prompt_<step>_project_<id>.txt`
- Eksport profilu: `project-tkinter/data/series/<slug>/generated/series_profile.json`
- Raport batch: `project-tkinter/data/series/<slug>/generated/series_batch_report_<timestamp>.json/.md`

## 10.3. Szybki workflow

1. Przypisz projekty do serii i ustaw `Tom`.
2. Otworz `Slownik serii` (Series manager).
3. Ustal `Style rules` i `Lorebook` (aktywny lore ustaw na `active`).
4. Zatwierdz kluczowe terminy (`approved`).
5. Uruchom `Run series batch` dla kroku `translate`, potem `edit`.
6. Sprawdz raport `series_batch_report_*.md`.

## 10.4. Zakres poza M7

- Eksperymentalny tor LoRA/QLoRA pozostaje opcjonalnym backlogiem R&D.
