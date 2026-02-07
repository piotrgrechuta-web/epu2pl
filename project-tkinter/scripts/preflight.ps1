$ErrorActionPreference = "Stop"

Write-Host "== Preflight: py_compile =="
python -m py_compile start.py tlumacz_ollama.py project_db.py epub_enhancer.py studio_suite.py app_events.py

Write-Host "== Preflight: pytest =="
python -m pytest -q

Write-Host "== Preflight PASS =="
