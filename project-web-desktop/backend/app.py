from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OLLAMA_HOST_DEFAULT = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
SUPPORTED_TEXT_LANGS = {"en", "pl", "de", "fr", "es", "pt"}

BASE_DIR = Path(__file__).resolve().parent
ENGINE_DIR = BASE_DIR / "engine"
TRANSLATOR = ENGINE_DIR / "tlumacz_ollama.py"
STATE_FILE = BASE_DIR / "ui_state.json"
DEFAULT_DB = BASE_DIR / "translator_studio.db"

app = FastAPI(title="Translator Studio API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UiState(BaseModel):
    provider: str = "ollama"
    input_epub: str = ""
    output_epub: str = ""
    prompt: str = ""
    glossary: str = ""
    cache: str = ""
    debug_dir: str = "debug"
    ollama_host: str = OLLAMA_HOST_DEFAULT
    google_api_key: str = ""
    model: str = ""
    batch_max_segs: str = "6"
    batch_max_chars: str = "12000"
    sleep: str = "0"
    timeout: str = "300"
    attempts: str = "3"
    backoff: str = "5,15,30"
    temperature: str = "0.1"
    num_ctx: str = "8192"
    num_predict: str = "2048"
    tags: str = "p,li,h1,h2,h3,h4,h5,h6,blockquote,dd,dt,figcaption,caption"
    use_cache: bool = True
    use_glossary: bool = True
    checkpoint: str = "0"
    source_lang: str = "en"
    target_lang: str = "pl"
    tm_db: str = str(DEFAULT_DB)
    tm_project_id: Optional[int] = None


class RunRequest(BaseModel):
    state: UiState


class ValidateRequest(BaseModel):
    epub_path: str
    tags: str = "p,li,h1,h2,h3,h4,h5,h6,blockquote,dd,dt,figcaption,caption"


class RunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.proc: Optional[subprocess.Popen[str]] = None
        self.mode: str = "idle"
        self.started_at: Optional[float] = None
        self.exit_code: Optional[int] = None
        self.log: List[str] = []
        self.max_log = 8000

    def _append(self, line: str) -> None:
        with self._lock:
            self.log.append(line)
            if len(self.log) > self.max_log:
                del self.log[: len(self.log) - self.max_log]

    def is_running(self) -> bool:
        with self._lock:
            return self.proc is not None

    def start(self, cmd: List[str], env: Dict[str, str], mode: str) -> None:
        with self._lock:
            if self.proc is not None:
                raise RuntimeError("Process already running")
            self.mode = mode
            self.started_at = time.time()
            self.exit_code = None
            self.log.clear()
            self.log.append("=== START ===\n")
            self.log.append("Command: " + " ".join(cmd) + "\n\n")
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        p: Optional[subprocess.Popen[str]] = None
        with self._lock:
            p = self.proc
        if p is None or p.stdout is None:
            return
        try:
            for line in p.stdout:
                self._append(line)
            code = p.wait()
            self._append(f"\n=== FINISH (exit={code}) ===\n")
            with self._lock:
                self.exit_code = code
                self.proc = None
                self.mode = "idle"
        except Exception as e:
            self._append(f"\n[runner-error] {e}\n")
            with self._lock:
                self.exit_code = -1
                self.proc = None
                self.mode = "idle"

    def stop(self) -> bool:
        with self._lock:
            p = self.proc
        if p is None:
            return False
        try:
            p.terminate()
            self._append("\n[stop] terminate sent\n")
            return True
        except Exception as e:
            self._append(f"\n[stop-error] {e}\n")
            return False

    def snapshot(self, tail: int = 400) -> Dict[str, Any]:
        with self._lock:
            lines = self.log[-tail:]
            return {
                "running": self.proc is not None,
                "mode": self.mode,
                "started_at": self.started_at,
                "exit_code": self.exit_code,
                "log": "".join(lines),
                "log_lines": len(self.log),
            }


RUNNER = RunManager()


def _load_state() -> UiState:
    if not STATE_FILE.exists():
        d = UiState()
        if (ENGINE_DIR / "prompt.txt").exists():
            d.prompt = str(ENGINE_DIR / "prompt.txt")
        return d
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return UiState(**raw)
    except Exception:
        pass
    return UiState()


def _save_state(state: UiState) -> None:
    STATE_FILE.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _translator_prefix() -> List[str]:
    if not TRANSLATOR.exists():
        raise RuntimeError(f"Missing translator script: {TRANSLATOR}")
    return ["python", "-u", str(TRANSLATOR)]


def _validate_state(s: UiState) -> None:
    if s.provider not in {"ollama", "google"}:
        raise ValueError("provider must be 'ollama' or 'google'")
    if not s.input_epub.strip():
        raise ValueError("input_epub is required")
    if not Path(s.input_epub).exists():
        raise ValueError(f"input_epub does not exist: {s.input_epub}")
    if not s.output_epub.strip():
        raise ValueError("output_epub is required")
    if not s.prompt.strip() or not Path(s.prompt).exists():
        raise ValueError("prompt file is required and must exist")
    if not s.model.strip():
        raise ValueError("model is required")
    if s.source_lang not in SUPPORTED_TEXT_LANGS:
        raise ValueError("invalid source_lang")
    if s.target_lang not in SUPPORTED_TEXT_LANGS:
        raise ValueError("invalid target_lang")


def _build_run_cmd(s: UiState) -> List[str]:
    cmd = _translator_prefix() + [
        s.input_epub.strip(),
        s.output_epub.strip(),
        "--prompt",
        s.prompt.strip(),
        "--provider",
        s.provider,
        "--model",
        s.model.strip(),
        "--batch-max-segs",
        s.batch_max_segs.strip(),
        "--batch-max-chars",
        s.batch_max_chars.strip(),
        "--sleep",
        s.sleep.strip().replace(",", "."),
        "--timeout",
        s.timeout.strip(),
        "--attempts",
        s.attempts.strip(),
        "--backoff",
        s.backoff.strip(),
        "--temperature",
        s.temperature.strip().replace(",", "."),
        "--num-ctx",
        s.num_ctx.strip(),
        "--num-predict",
        s.num_predict.strip(),
        "--tags",
        s.tags.strip(),
        "--checkpoint-every-files",
        s.checkpoint.strip(),
        "--debug-dir",
        s.debug_dir.strip() or "debug",
        "--source-lang",
        s.source_lang.strip().lower(),
        "--target-lang",
        s.target_lang.strip().lower(),
    ]
    if s.provider == "ollama":
        cmd += ["--host", (s.ollama_host.strip() or OLLAMA_HOST_DEFAULT)]
    if s.use_cache and s.cache.strip():
        cmd += ["--cache", s.cache.strip()]
    if s.use_glossary and s.glossary.strip():
        cmd += ["--glossary", s.glossary.strip()]
    else:
        cmd += ["--no-glossary"]
    cmd += ["--tm-db", s.tm_db.strip() or str(DEFAULT_DB)]
    if s.tm_project_id is not None:
        cmd += ["--tm-project-id", str(int(s.tm_project_id))]
    cmd += ["--tm-fuzzy-threshold", "0.92"]
    return cmd


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "running": RUNNER.is_running()}


@app.get("/config")
def get_config() -> Dict[str, Any]:
    return _load_state().model_dump()


@app.post("/config")
def set_config(state: UiState) -> Dict[str, Any]:
    _save_state(state)
    return {"ok": True}


@app.post("/run/start")
def run_start(req: RunRequest) -> Dict[str, Any]:
    try:
        _validate_state(req.state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    _save_state(req.state)
    cmd = _build_run_cmd(req.state)
    env = {**os.environ}
    if req.state.provider == "google":
        key = req.state.google_api_key.strip() or os.environ.get(GOOGLE_API_KEY_ENV, "").strip()
        if not key:
            raise HTTPException(status_code=400, detail="Google API key is missing")
        env[GOOGLE_API_KEY_ENV] = key
    try:
        RUNNER.start(cmd, env=env, mode="translate")
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@app.post("/run/validate")
def run_validate(req: ValidateRequest) -> Dict[str, Any]:
    p = Path(req.epub_path.strip()) if req.epub_path.strip() else None
    if p is None or not p.exists():
        raise HTTPException(status_code=400, detail="epub_path must exist")
    cmd = _translator_prefix() + ["--validate-epub", str(p), "--tags", req.tags.strip()]
    try:
        RUNNER.start(cmd, env={**os.environ}, mode="validate")
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@app.get("/run/status")
def run_status() -> Dict[str, Any]:
    return RUNNER.snapshot(tail=600)


@app.post("/run/stop")
def run_stop() -> Dict[str, Any]:
    return {"ok": RUNNER.stop()}


@app.get("/models/ollama")
def models_ollama(host: str = OLLAMA_HOST_DEFAULT) -> Dict[str, Any]:
    url = host.rstrip("/") + "/api/tags"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    out: List[str] = []
    for m in data.get("models", []) or []:
        name = m.get("name")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return {"models": sorted(set(out))}


@app.get("/models/google")
def models_google(api_key: str) -> Dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="api_key is required")
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": key}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    out: List[str] = []
    for m in data.get("models", []) or []:
        name = m.get("name")
        methods = m.get("supportedGenerationMethods") or []
        ok = isinstance(name, str) and isinstance(methods, list) and any(str(x).lower() == "generatecontent" for x in methods)
        if ok:
            out.append(name.strip())
    return {"models": sorted(set(out))}
