#!/usr/bin/env bash
#
# 프론트엔드만 실행합니다 (5173 포트).
#
#   ./run-frontend.sh

set -uo pipefail
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
  printf '\n[X] 의존성이 설치되지 않았습니다. frontend 폴더에서 먼저 실행하세요:\n' >&2
  printf '      npm install\n' >&2
  exit 1
fi

printf '프론트엔드: http://localhost:5173\n'
printf '종료하려면 Ctrl+C\n\n'

exec npm run dev
