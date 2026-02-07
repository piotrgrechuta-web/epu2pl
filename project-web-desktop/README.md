# Translator Studio Desktop (Web)

Projekt web/desktop (Electron + FastAPI) z funkcjonalnością operacyjną zbliżoną do wersji Tkinter:
- konfiguracja parametrów runu,
- start tłumaczenia,
- start walidacji EPUB,
- stop procesu,
- status procesu i log live,
- zapis/odczyt konfiguracji,
- pobieranie list modeli (Ollama/Google).

## Struktura
- `backend/` API + runner procesu
- `backend/engine/` lokalna kopia `tlumacz_ollama.py`
- `desktop/` aplikacja Electron

## Szybki start
W katalogu `project-web-desktop`:

1. Backend:
```powershell
.\run-backend.ps1
```

2. Desktop:
```powershell
.\run-desktop.ps1
```

## Parametry
Frontend zapisuje config do `backend/ui_state.json`.
Domyślna baza TM: `backend/translator_studio.db`.

## Uwagi
To jest aktywnie rozwijany wariant webowy. Jeśli chcesz pełną 1:1 parytetową migrację wszystkich zakładek Studio/QA/TM z Tkintera, mogę kontynuować kolejne etapy bez zatrzymywania prac.
