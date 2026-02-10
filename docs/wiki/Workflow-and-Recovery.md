# Workflow and Recovery

## English

This page summarizes safe daily operation and recovery after interruption.

### Recommended run flow

1. Select project and verify provider/model.
2. Run `translate`.
3. Review QA findings and gate status.
4. Run `edit` (or queue `edit` after `translate` when gate is green).
5. Validate final EPUB (`EPUBCheck` + QA severity gate).

### Safe resume model

- Segment state is persisted in SQLite ledger (`segment_ledger`).
- Cache + ledger reuse avoids re-paying for completed API work.
- After interruption/crash, restart the same project/step to resume safely.
- Run panel exposes live status strip: `done/processing/error/pending`.

### Provider reliability and health

- Async provider preflight is available in GUI (`Health check I/O`).
- Provider telemetry captures status, latency, model count, and failure streak.
- `M10#55` tracks UX-level silent wait-and-retry for transient provider failures.

### Prompt and startup updates

- Prompt presets are provider/mode-aware and can be applied from GUI.
- `M10#53` tracks segment-aware prompt routing.
- `M10#54` tracks no-config startup (`auto-pathing` + `auto-resume`).

### If run fails

1. Open run history and inspect last log entries.
2. Verify provider health and credentials.
3. Restart the same project and run step.
4. Re-check QA/EPUBCheck gates before final export.

## Polski

Ta strona podsumowuje bezpieczny workflow i odzyskiwanie po przerwaniu.

### Zalecany przebieg runu

1. Wybierz projekt i zweryfikuj provider/model.
2. Uruchom `translate`.
3. Przejrzyj findings QA i status gate.
4. Uruchom `edit` (lub kolejkuj `edit` po `translate`, gdy gate jest zielony).
5. Zweryfikuj finalny EPUB (`EPUBCheck` + QA severity gate).

### Model bezpiecznego wznawiania

- Stan segmentow jest trwale zapisywany w SQLite (`segment_ledger`).
- Reuzycie cache + ledgera ogranicza ponowne koszty API.
- Po przerwaniu/crashu wznow ten sam projekt i krok.
- Panel runu pokazuje pasek statusow: `done/processing/error/pending`.

### Niezawodnosc providera i health

- Asynchroniczny preflight providerow jest dostepny w GUI (`Health check I/O`).
- Telemetryka health zapisuje status, opoznienie, liczbe modeli i failure streak.
- `M10#55` obejmuje cichy wait-and-retry dla chwilowych bledow providera.

### Aktualizacje promptow i startupu

- Presety promptow sa zalezne od provider/mode i aplikowalne z GUI.
- `M10#53` obejmuje segment-aware prompt routing.
- `M10#54` obejmuje startup no-config (`auto-pathing` + `auto-resume`).

### Gdy run konczy sie bledem

1. Otworz historie runu i sprawdz koncowke logu.
2. Zweryfikuj health providera i credentials.
3. Wznow ten sam projekt i krok runu.
4. Przed exportem ponownie sprawdz QA/EPUBCheck gate.

## Detailed docs

- https://github.com/Piotr-Grechuta/epub-translator-studio/blob/main/docs/03-Praca-na-2-komputerach.md
- https://github.com/Piotr-Grechuta/epub-translator-studio/blob/main/docs/06-Troubleshooting.md
