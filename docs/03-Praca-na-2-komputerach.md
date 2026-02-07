# 03. Praca na 2 komputerach

## Model pracy

Najprostszy i najbezpieczniejszy model:
- jedna aktywna galaz robocza: `ep2pl`,
- zawsze `pull` przed praca,
- zawsze `push` po zakonczonej sesji.

## Checklist start/stop

### Start sesji

```powershell
git checkout ep2pl
git pull --rebase
```

### Koniec sesji

```powershell
git add -A
git commit -m "krotki opis"
git push
```

## Co robic przy konflikcie

1. `git status`
2. rozwiaz konflikt lokalnie
3. `git add ...`
4. `git rebase --continue` albo commit po merge
5. `git push`

## Co najczesciej psuje synchronizacje

- lokalne pliki binarne (db/lock/cache)
- `node_modules` i duze artefakty
- praca na roznych branchach bez swiadomosci

## Dobre praktyki

- male, czeste commity
- jeden temat na commit
- opis PR z powodem zmiany i testami

## START/STOP scripts (opcjonalnie)

Mozesz zautomatyzowac rytm 2 skryptami:
- `START.ps1`: checkout + pull + open code
- `STOP.ps1`: add + commit + push

To ogranicza ryzyko "zapomnialem push".

## Recovery gdy lokalnie jest chaos

Jesli chcesz wyrownac lokalne repo do zdalnego i zachowac kopie zmian:

```powershell
git stash push -u -m "backup"
git fetch origin
git reset --hard origin/ep2pl
git clean -fd
```

Potem ewentualnie przywroc fragmenty:

```powershell
git stash list
git stash pop
```
