# Git workflow na wielu komputerach (bez zgadywania)

Ten plik opisuje standard pracy dla tego repo, gdy pracujesz na kilku urzadzeniach.

Automatyzacja jest w skrypcie:
- `scripts/git_workflow.py`

## 1. Jednorazowo na kazdym komputerze

W katalogu `project-tkinter` uruchom:

```powershell
python scripts/git_workflow.py setup
```

To ustawia lokalnie (`.git/config`):
- `pull.ff=only`
- `fetch.prune=true`
- `rebase.autoStash=true`
- `push.default=simple`

Dodatkowo skrypt ustawia **dual-push**:
- konfiguruje `backup` (jesli brak, probuje utworzyc URL `...-private-backup.git`),
- ustawia `origin` tak, by `git push origin ...` wysylal jednoczesnie na `origin` i `backup`.

## 2. Start pracy (zawsze przed edycja)

```powershell
python scripts/git_workflow.py start --branch ep2pl
```

Skrypt zrobi:
1. `git fetch --prune origin`
2. `git switch ep2pl`
3. `git pull --ff-only origin ep2pl`

Czyli masz aktualna wersje online, bez merge-ow przypadkowych.

## 3. Koniec pracy (publikacja)

```powershell
python scripts/git_workflow.py publish --branch ep2pl -m "Twoj opis zmian"
```

Skrypt zrobi:
1. `fetch` + `switch`
2. sprawdzenie czy nie jestes za `origin/ep2pl`
3. `git add -A`
4. `git commit -m "..."`
5. `git push origin ep2pl` (po `setup`: automatycznie na `origin` i `backup`)

## 4. Szybki podglad statusu

```powershell
python scripts/git_workflow.py status --branch ep2pl --fetch
```

## 5. Minimalny rytm dnia

1. Na komputerze A: `start`
2. Pracujesz
3. `publish`
4. Na komputerze B: `start`
5. Pracujesz
6. `publish`

To wystarcza, zeby nie rozjezdzac wersji miedzy urzadzeniami.
