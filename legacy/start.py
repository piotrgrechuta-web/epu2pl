#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
STARTER (Google vs Ollama) — wersja z podziałem mechanizmów per provider

Wymagania użytkownika:
- Zawsze możliwość WYBORU modelu AI (Google i Ollama) poprzez wyświetlenie dostępnych modeli
- Dla Ollama: NIE pytaj o host (traktujemy jako stały, ewentualnie nadpisywalny ENV)
- Uruchamia tłumacza, który pokazuje POSTĘP CAŁEGO PROJEKTU (globalny), a nie tylko pliku/segmentu

Zależności:
  pip install requests
"""

from __future__ import annotations

import os
import json
import subprocess
import platform
import shlex
from pathlib import Path
from typing import List, Optional

import requests


# ----------------------------
# Konfiguracje stałe / bezpieczniki
# ----------------------------

SESSION_FILE = Path(__file__).resolve().with_name(".last_session.json")

# Wklej tu swój klucz (jeśli chcesz mieć go jawnie w kodzie).
# Możesz też zostawić pusty i wkleić przy uruchomieniu — wtedy nadal jest jawnie przekazany jako --api-key.
GOOGLE_API_KEY = ""  # np. "AIza...." (nie commituj tego do repo)

# Stały host Ollamy (bez pytania). Możesz nadpisać env OLLAMA_HOST.
OLLAMA_HOST_DEFAULT = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


# ----------------------------
# Helpers
# ----------------------------

def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def q(arg: str) -> str:
    """Quote argument for copy/paste logging."""
    if is_windows():
        if any(ch in arg for ch in [' ', '\t', '"']):
            return '"' + arg.replace('"', '\\"') + '"'
        return arg
    return shlex.quote(arg)



def _maybe_rel(p: Path, base: Path) -> str:
    """
    Zwraca ścieżkę względną względem base, jeśli to możliwe.
    Dzięki temu sesja jest przenośna (zmiana litery dysku nie psuje wznowienia).
    """
    try:
        # działa tylko jeśli p jest "pod" base (typowe: wszystko w katalogu projektu)
        return str(p.resolve().relative_to(base.resolve()))
    except Exception:
        # fallback: relpath (obsłuży też przypadek absolutnej ścieżki na innym dysku)
        return os.path.relpath(str(p), str(base))

def _portableize_existing_cmd(cmd: List[str], workdir: Path) -> List[str]:
    """
    Naprawia STARE sesje, które zapisały absolutne ścieżki z literą dysku (np. H:\...).
    Jeśli plik o tej samej nazwie istnieje w workdir, podmienia argument na nazwę pliku.
    """
    def _fix_path_arg(arg: str) -> str:
        p = Path(arg)
        if p.exists():
            return arg
        # jeśli nie istnieje, spróbuj po nazwie w workdir
        cand = workdir / p.name
        if cand.exists():
            return cand.name  # względnie względem cwd=workdir
        return arg

    out = list(cmd)

    # cmd[1]=translator, cmd[2]=input_epub, cmd[3]=output_epub (patrz budowa komendy niżej)
    for i in (1, 2, 3):
        if i < len(out):
            out[i] = _fix_path_arg(out[i])

    # flagi, po których idzie ścieżka
    i = 0
    while i < len(out) - 1:
        if out[i] in ("--prompt", "--cache", "--glossary", "--debug-dir"):
            out[i + 1] = _fix_path_arg(out[i + 1])
            i += 2
        else:
            i += 1

    return out

def format_cmd_redacting_secrets(cmd: List[str]) -> str:
    """Formatuje komendę do logu, maskując wartości po --api-key."""
    out: List[str] = []
    redact_next = False
    for a in cmd:
        if redact_next:
            out.append("***")
            redact_next = False
            continue
        if a in ("--api-key", "--google-api-key"):
            out.append(a)
            redact_next = True
            continue
        out.append(q(a))
    return " ".join(out)


def pick_one(paths: List[Path], label: str) -> Optional[Path]:
    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]

    print(f"\nWykryto wiele {label}:")
    for i, p in enumerate(paths, 1):
        print(f"  [{i}] {p.name}")
    while True:
        s = input(f"Wybierz {label} (1-{len(paths)}): ").strip()
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(paths):
                return paths[idx - 1]
        print("  Podaj numer z listy (Enter nie wybiera domyślnie).")


def ask_yes_no(prompt: str, default_yes: bool) -> bool:
    d = "T/n" if default_yes else "t/N"
    while True:
        s = input(f"{prompt} ({d}): ").strip().lower()
        if not s:
            return default_yes
        if s in ("t", "tak", "y", "yes"):
            return True
        if s in ("n", "nie", "no"):
            return False
        print("  Wpisz t/n.")


def ask_required_int(prompt: str, min_v: int = 1, max_v: int = 10**9) -> int:
    while True:
        s = input(prompt).strip()
        if not s:
            print("  Wymagane — wpisz wartość.")
            continue
        try:
            v = int(s)
            if min_v <= v <= max_v:
                return v
        except ValueError:
            pass
        print(f"  Podaj liczbę całkowitą w zakresie {min_v}..{max_v}.")


def ask_required_float(prompt: str, min_v: float = 0.0, max_v: float = 10**9) -> float:
    while True:
        s = input(prompt).strip()
        if not s:
            print("  Wymagane — wpisz wartość.")
            continue
        try:
            v = float(s.replace(",", "."))
            if min_v <= v <= max_v:
                return v
        except ValueError:
            pass
        print(f"  Podaj liczbę w zakresie {min_v}..{max_v}.")


def save_session(data: dict) -> None:
    with SESSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session() -> Optional[dict]:
    if not SESSION_FILE.exists():
        return None
    try:
        with SESSION_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_session() -> None:
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass


# ----------------------------
# Model listing
# ----------------------------

def list_ollama_models(host: str, timeout_s: int = 20) -> List[str]:
    url = host.rstrip("/") + "/api/tags"
    r = requests.get(url, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    models: List[str] = []
    for m in data.get("models", []) or []:
        name = m.get("name")
        if isinstance(name, str) and name.strip():
            models.append(name.strip())
    # stable unique
    return sorted(set(models))


def list_google_models(api_key: str, timeout_s: int = 20) -> List[str]:
    """Lista modeli widocznych dla klucza, filtrowanych do generateContent."""
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": api_key.strip()}
    r = requests.get(url, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    out: List[str] = []
    for m in data.get("models", []) or []:
        name = m.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        methods = m.get("supportedGenerationMethods") or []
        ok = isinstance(methods, list) and any(str(x).lower() == "generatecontent" for x in methods)
        if ok:
            out.append(name.strip())
    return sorted(set(out))


def pick_from_list(options: List[str], label: str) -> str:
    if not options:
        raise SystemExit(f"Brak opcji do wyboru: {label}")
    if len(options) == 1:
        print(f"\nDostępny jest tylko jeden {label}: {options[0]}")
        return options[0]

    print(f"\nDostępne {label}:")
    for i, m in enumerate(options, 1):
        print(f"  [{i}] {m}")

    while True:
        s = input(f"Wybierz {label} (1-{len(options)}): ").strip()
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        print("  Podaj numer z listy (Enter nie wybiera domyślnie).")


# ----------------------------
# Glossary auto-detect
# ----------------------------

def find_glossary(workdir: Path) -> Optional[Path]:
    exact = workdir / "SŁOWNIK.txt"
    if exact.exists():
        return exact
    for name in ("slownik.txt", "słownik.txt", "SLOWNIK.txt", "Słownik.txt"):
        p = workdir / name
        if p.exists():
            return p
    cand = sorted([p for p in workdir.glob("*.txt") if "slownik" in p.name.lower() or "słownik" in p.name.lower()])
    return cand[0] if cand else None


# ----------------------------
# Main
# ----------------------------

def main() -> int:
    workdir = Path(__file__).resolve().parent

    translator = workdir / "tlumacz_ollama_google_ollama.py"
    if not translator.exists():
        # fallback: jeśli użytkownik zachowa nazwę tlumacz_ollama.py
        translator = workdir / "tlumacz_ollama.py"
    if not translator.exists():
        raise SystemExit("Nie znaleziono skryptu tłumacza (tlumacz_ollama_google_ollama.py lub tlumacz_ollama.py).")

    # Resume
    session = load_session()
    if session:
        print("\n[!] WYKRYTO PRZERWANĄ SESJĘ:")
        print(f"    wejście:   {Path(session.get('input_epub','')).name}")
        print(f"    wyjście:   {Path(session.get('out_epub','')).name}")
        print(f"    provider:  {session.get('provider')}")
        print(f"    model:     {session.get('model')}")
        if ask_yes_no("Wznowić z tymi samymi ustawieniami?", default_yes=True):
            cmd = _portableize_existing_cmd(session["cmd"], workdir)
            # przy wznowieniu pozwól wybrać inny model (opcjonalnie)
            if ask_yes_no("Chcesz zmienić model przed wznowieniem?", default_yes=False):
                provider = session["provider"]
                if provider == "ollama":
                    models = list_ollama_models(OLLAMA_HOST_DEFAULT)
                    model = pick_from_list(models, "modele Ollama")
                else:
                    api_key = session.get("api_key") or GOOGLE_API_KEY.strip()
                    if not api_key:
                        api_key = input("Podaj Google API key (jawnie, zostanie przekazany jako --api-key): ").strip()
                    if not api_key:
                        raise SystemExit("Brak klucza Google API.")
                    models = list_google_models(api_key)
                    model = pick_from_list(models, "modele Google (generateContent)")
                # podmień w cmd wartość po --model
                new_cmd = []
                it = iter(cmd)
                for a in it:
                    if a == "--model":
                        new_cmd.append(a)
                        _old = next(it, None)
                        new_cmd.append(model)
                    else:
                        new_cmd.append(a)
                cmd = _portableize_existing_cmd(new_cmd, workdir)
                session["cmd"] = cmd
                session["model"] = model
                # nie zapisujemy sekretów, ale cmd ma --api-key jeśli google i użytkownik tak chce
                save_session(session)

            print("\nGotowa komenda (dla logu):\n")
            print(format_cmd_redacting_secrets(cmd))
            print("\nUruchamiam.\n")
            try:
                subprocess.run(cmd, cwd=str(workdir), check=True)
                clear_session()
                print("\nZakończono.")
                return 0
            except subprocess.CalledProcessError:
                print("\n[!] Błąd. Sesja została zachowana — możesz wznowić przy następnym uruchomieniu.")
                return 1

        print("\nOK — konfiguruję nową sesję (poprzednia zostanie nadpisana).\n")

    # Tryb
    print("Wybierz tryb pracy:")
    print("  [1] Tłumaczenie (EN → PL)  używa: prompt.txt")
    print("  [2] Redakcja (PL → PL)    używa: prompt_redakcja.txt")
    while True:
        mode = input("Tryb [1/2]: ").strip()
        if mode in ("1", "2"):
            break
        print("  Wpisz 1 lub 2.")

    prompt_path = workdir / ("prompt.txt" if mode == "1" else "prompt_redakcja.txt")
    if not prompt_path.exists():
        raise SystemExit(f"Brak pliku: {prompt_path.name}")

    # EPUB input
    input_epub = pick_one(sorted(workdir.glob("*.epub")), "EPUB")
    if input_epub is None:
        raise SystemExit("Nie znaleziono żadnego *.epub w katalogu.")

    # Output + cache
    if mode == "1":
        out_epub = workdir / f"{input_epub.stem}_pl.epub"
        cache_path = workdir / f"cache_{input_epub.stem}.jsonl"
    else:
        out_epub = workdir / f"{input_epub.stem}_pl_redakcja.epub"
        cache_path = workdir / f"cache_{input_epub.stem}_redakcja.jsonl"

    glossary = find_glossary(workdir)

    # Provider
    print("\nWybierz silnik LLM:")
    print("  [1] Ollama (lokalnie)")
    print("  [2] Google Gemini API")
    while True:
        engine = input("Silnik [1/2]: ").strip()
        if engine in ("1", "2"):
            break
        print("  Wpisz 1 lub 2.")

    provider = "ollama" if engine == "1" else "google"
    host = OLLAMA_HOST_DEFAULT

    # Model selection
    if provider == "ollama":
        print(f"\nOllama host (stały): {host}")
        models = list_ollama_models(host)
        model = pick_from_list(models, "modele Ollama")
        api_key = None
    else:
        api_key = GOOGLE_API_KEY.strip()
        if not api_key:
            api_key = input("Podaj Google API key (jawnie, zostanie przekazany jako --api-key): ").strip()
        if not api_key:
            raise SystemExit("Brak klucza Google API.")
        models = list_google_models(api_key)
        model = pick_from_list(models, "modele Google (generateContent)")

    # Batch params — wymagane (bez domyślnych)
    print("\nParametry batchowania (WYMAGANE):")
    print("  Wskazówka: dla Google zwykle większy batch zmniejsza liczbę requestów, ale nie przesadzaj jeśli masz 429/timeout.")
    batch_max_segs = ask_required_int("Maks. liczba segmentów na request (--batch-max-segs): ", min_v=1, max_v=100)
    batch_max_chars = ask_required_int("Maks. znaków na request (--batch-max-chars): ", min_v=500, max_v=500000)

    # Sleep
    sleep_s = ask_required_float("Pauza między requestami w sekundach (--sleep) [dla Ollama zwykle 0, dla Google np. 1-3]: ", min_v=0.0, max_v=60.0)

    # Cache + glossary
    use_cache = ask_yes_no("Użyć cache do wznawiania?", default_yes=True)
    use_glossary = False
    if glossary is not None:
        use_glossary = ask_yes_no(f"Użyć słownika {glossary.name}?", default_yes=True)
    else:
        print("\nNie wykryto słownika (SŁOWNIK.txt/slownik.txt).")

    # Extra: checkpoint frequency (global progress i tak pokazuje tłumacz)
    checkpoint_every_files = ask_required_int("Checkpoint: zapisuj co N plików spine (--checkpoint-every-files) [0=wyłącz]: ", min_v=0, max_v=9999)

    # Build command
    cmd: List[str] = [
        "python",
        translator.name,
        input_epub.name,
        out_epub.name,
        "--prompt", prompt_path.name,
        "--provider", provider,
        "--model", model,
        "--batch-max-segs", str(batch_max_segs),
        "--batch-max-chars", str(batch_max_chars),
        "--sleep", str(sleep_s),
        "--checkpoint-every-files", str(checkpoint_every_files),
        # debug dir zostawiamy stały dla łatwej diagnostyki
        "--debug-dir", "debug",
    ]

    if provider == "ollama":
        # host stały, ale nadal przekazujemy jawnie do tłumacza dla przejrzystości/diagnostyki
        cmd += ["--host", host]
    else:
        cmd += ["--api-key", api_key]

    if use_cache:
        cmd += ["--cache", cache_path.name]

    if glossary is not None and use_glossary:
        cmd += ["--glossary", glossary.name]
    else:
        cmd += ["--no-glossary"]

    # Session (resume) — zapisujemy CMD i parametry. UWAGA: jeśli provider=google, cmd zawiera --api-key (jawnie).
    session_data = {
        "input_epub": input_epub.name,
        "out_epub": out_epub.name,
        "provider": provider,
        "model": model,
        "cmd": cmd,
        "api_key": (api_key if provider == "google" else None),  # do listowania modeli przy wznowieniu
        "workdir": str(workdir),
    }
    save_session(session_data)

    print("\nGotowa komenda (dla logu):\n")
    print(format_cmd_redacting_secrets(cmd))
    print("\nUruchamiam.\n")

    try:
        subprocess.run(cmd, cwd=str(workdir), check=True)
        clear_session()
        print(f"\nZakończono. Wynik: {out_epub.name}")
        return 0
    except subprocess.CalledProcessError:
        print("\n[!] Wystąpił błąd. Sesja została zapisana — możesz wznowić przy następnym uruchomieniu.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
