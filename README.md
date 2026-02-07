# EPUB Translator Studio

Language: **English** | [Polski](README.pl.md)

Desktop toolkit for translating and editing EPUB files with AI.

Keywords: `EPUB translator`, `AI translation`, `Ollama`, `Google Gemini`, `Translation Memory`, `QA`, `Tkinter`, `Electron`, `FastAPI`, `Python`.

## What it does
- EPUB translation (`translate`) and post-editing (`edit`)
- EPUB validation
- Translation Memory (TM) and segment cache
- QA findings workflow and QA gate
- EPUB operations: front card, cover/image removal, segment editor
- project queue workflow (`pending`, `run all`)

## App variants
- `project-tkinter/`
  - main desktop app in Python + Tkinter
  - fullest feature set
- `project-web-desktop/`
  - Electron + FastAPI variant
  - desktop web-style interface
- `legacy/`
  - archived root scripts from older layout (`legacy/start.py`, `legacy/tlumacz_ollama.py`)
  - not the recommended runtime path

## Quick start

### Tkinter (main)
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

## Architecture (Variant 0: shared core)
- shared runtime logic lives in `project-tkinter/runtime_core.py`
- web backend (`project-web-desktop/backend/app.py`) imports the same core
- canonical translator: `project-tkinter/tlumacz_ollama.py`
- web fallback translator: `project-web-desktop/backend/engine/tlumacz_ollama.py`

This keeps core runtime behavior synchronized across both variants.

## Documentation
- Tkinter user manual (PL): `project-tkinter/MANUAL_PL.md`
- multi-device Git workflow: `project-tkinter/GIT_WORKFLOW_PL.md`
- support info: `SUPPORT_PL.md`

## Support
- Sponsor: https://github.com/sponsors/piotrgrechuta-web
- a support link is also available directly in both app UIs (`Wesprzyj projekt`)

## License
- License: `PolyForm Noncommercial 1.0.0` (`LICENSE`)
- You can copy and modify the code for noncommercial purposes.
- Keep creator attribution and required notices in redistributions (`NOTICE`, `AUTHORS`).
- Practical examples (PL): `LICENSE_EXAMPLES_PL.md`
