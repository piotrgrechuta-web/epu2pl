# 02. Instalacja i konfiguracja

## 2.1. Narzedzia i wersje

Dla stabilnosci trzymaj porownywalne wersje na wszystkich maszynach.
Rekomendacja:
- Python 3.11.x
- Node.js LTS
- npm zgodny z Node LTS
- Git aktualny

## 2.2. Konfiguracja Git

Sprawdz i ustaw globalnie:

```powershell
git config --global user.name "Twoj Login"
git config --global user.email "twoj@email"
```

Warto tez wlaczyc:

```powershell
git config --global pull.rebase true
git config --global fetch.prune true
```

## 2.3. Provider AI

### Ollama

Instalacja i model:

```powershell
winget install Ollama.Ollama
ollama pull llama3.1:8b
```

W aplikacji ustaw:
- provider: `ollama`
- host: zwykle `http://127.0.0.1:11434`

### Google API

```powershell
setx GOOGLE_API_KEY "<YOUR_KEY>"
```

Po zmianie env var otworz nowa sesje terminala.

## 2.4. Struktura runtime i dane

W projekcie sa dane robocze (np. lokalne bazy, cache, locki).
Zasada:
- kod i konfiguracje trzymamy w Git,
- dane tymczasowe i lokalne artefakty nie powinny blokowac `pull`.

## 2.5. Ustawienia VS Code

- wlacz `Settings Sync`
- zainstaluj rozszerzenia Python/GitHub
- uzywaj terminala z aktywnym `.venv`

## 2.6. Bezpieczenstwo

- nigdy nie commituj kluczy API
- nie trzymamy tokenow w README ani wiki
- preferuj env vars i lokalne sekrety

## 2.7. Check po instalacji

1. `python --version`
2. `node --version`
3. `npm --version`
4. `git --version`
5. uruchomienie obu wariantow aplikacji bez bledu
