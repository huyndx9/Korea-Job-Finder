#!/usr/bin/env bash
#
# 백엔드만 실행합니다 (8000 포트).
#
#   ./run-backend.sh

set -uo pipefail
cd "$(dirname "$0")/backend"

if   [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python"        ]; then PY=".venv/bin/python"
else
  printf '\n[X] 가상환경이 없습니다. backend 폴더에서 먼저 실행하세요:\n' >&2
  printf '      python -m venv .venv\n' >&2
  printf '      .venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows\n' >&2
  printf '      .venv/bin/python -m pip install -r requirements.txt           # macOS/Linux\n' >&2
  exit 1
fi

printf '백엔드: http://127.0.0.1:8000   (API 문서: /docs)\n'
printf '종료하려면 Ctrl+C\n\n'

exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
