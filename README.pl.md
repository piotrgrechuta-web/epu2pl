# EPUB Translator Studio

Jezyk: [English](README.md) | **Polski**

Desktopowy zestaw narzedzi do tlumaczenia i redakcji plikow EPUB z AI.

Slowa kluczowe: `EPUB translator`, `AI translation`, `Ollama`, `Google Gemini`, `Translation Memory`, `QA`, `Tkinter`, `Electron`, `FastAPI`, `Python`.

## Co to robi
- tlumaczenie EPUB (`translate`) i redakcja (`edit`)
- walidacja EPUB
- Translation Memory (TM) i cache segmentow
- workflow findings QA i QA gate
- operacje EPUB: wizytowka, usuwanie okladki/grafik, edytor segmentow
- praca kolejka projektow (`pending`, `run all`)

## Warianty aplikacji
- `project-tkinter/`
  - glowna aplikacja desktop w Python + Tkinter
  - najpelniejszy zestaw funkcji
- `project-web-desktop/`
  - wariant Electron + FastAPI
  - desktopowy interfejs webowy
- `legacy/`
  - zarchiwizowane skrypty z dawnego ukladu (`legacy/start.py`, `legacy/tlumacz_ollama.py`)
  - nie jest to zalecana sciezka uruchamiania

## Szybki start

### Tkinter (glowny)
```powershell
cd project-tkinter
python start.py
```

### Web desktop
```powershell
cd project-web-desktop
.\run-backend.ps1
.\run-desktop.ps1
```

## Architektura (Variant 0: shared core)
- wspolna logika runtime jest w `project-tkinter/runtime_core.py`
- backend web (`project-web-desktop/backend/app.py`) importuje ten sam core
- kanoniczny translator: `project-tkinter/tlumacz_ollama.py`
- fallback translatora dla web: `project-web-desktop/backend/engine/tlumacz_ollama.py`

Dzieki temu zachowanie logiki runtime jest synchronizowane miedzy wariantami.

## Dokumentacja
- manual użytkownika Tkinter (PL): `project-tkinter/MANUAL_PL.md`
- workflow Git na wielu komputerach: `project-tkinter/GIT_WORKFLOW_PL.md`
- informacje o wsparciu: `SUPPORT_PL.md`

## Wsparcie
- Sponsor: https://github.com/sponsors/piotrgrechuta-web
- link wsparcia jest tez bezposrednio w obu UI aplikacji (`Wesprzyj projekt`)

## Licencja
- Licencja: `PolyForm Noncommercial 1.0.0` (`LICENSE`)
- Mozna kopiowac i modyfikowac kod do celow niekomercyjnych.
- Przy kopiowaniu/forku trzeba zachowac informacje o autorze i Required Notice (`NOTICE`, `AUTHORS`).
- Proste przyklady dla uzytkownika: `LICENSE_EXAMPLES_PL.md`
