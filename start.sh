#!/usr/bin/env bash
#
# Korea Job Finder - 백엔드 + 프론트엔드를 한 번에 실행합니다.
#
#   ./start.sh
#
# Ctrl+C 를 누르면 두 서버가 함께 종료됩니다.
# Windows(Git Bash), macOS, Linux 모두 동작합니다.

set -uo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=8000
FRONTEND_PORT=5173

say()  { printf '%s\n' "$*"; }
fail() { printf '\n[X] %s\n' "$*" >&2; exit 1; }

# --- 파이썬 실행 파일 찾기 (Windows 는 Scripts/, Unix 는 bin/) ---------------
if   [ -x "backend/.venv/Scripts/python.exe" ]; then PY="$PWD/backend/.venv/Scripts/python.exe"
elif [ -x "backend/.venv/bin/python"        ]; then PY="$PWD/backend/.venv/bin/python"
else
  fail "가상환경이 없습니다. 먼저 아래를 실행하세요:
      cd backend
      python -m venv .venv
      .venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
      .venv/bin/python -m pip install -r requirements.txt           # macOS/Linux"
fi

[ -d "frontend/node_modules" ] || fail "프론트엔드 의존성이 없습니다. 먼저 실행하세요:
      cd frontend && npm install"

# --- 포트가 이미 사용 중인지 확인 -------------------------------------------
# "localhost" 로 확인합니다 — Vite 는 IPv6 에만 바인딩하므로 127.0.0.1 만 보면 놓칩니다.
port_busy() {
  curl -s -o /dev/null -m 2 "http://localhost:$1" 2>/dev/null
}

busy=""
port_busy "$BACKEND_PORT"  && busy="$busy $BACKEND_PORT"
port_busy "$FRONTEND_PORT" && busy="$busy $FRONTEND_PORT"
if [ -n "$busy" ]; then
  fail "이미 사용 중인 포트:$busy
      먼저 ./stop.sh 를 실행하거나, 열려 있는 서버 창을 닫아 주세요."
fi

# --- 종료 시 두 서버 모두 정리 ----------------------------------------------
# Windows(Git Bash)에서는 uvicorn/node 가 네이티브 프로세스라서 bash 의 kill 만으로는
# 살아남는 경우가 있습니다. 그러면 포트를 계속 점유해 다음 실행이 "포트 사용 중"으로
# 실패합니다. 그래서 WINPID 를 찾아 프로세스 트리째 종료합니다.
kill_tree() {
  local pid="${1:-}"
  [ -z "$pid" ] && return 0

  if command -v taskkill >/dev/null 2>&1; then
    local winpid
    winpid=$(ps -p "$pid" 2>/dev/null | awk -v p="$pid" '$1 == p { print $4 }')
    if [ -n "$winpid" ]; then
      MSYS_NO_PATHCONV=1 taskkill /PID "$winpid" /T /F >/dev/null 2>&1 && return 0
    fi
  fi
  kill "$pid" 2>/dev/null
}

PIDS=()
cleaned=0
cleanup() {
  [ "$cleaned" -eq 1 ] && return 0
  cleaned=1
  printf '\n서버를 종료하는 중...\n'
  for pid in "${PIDS[@]:-}"; do
    kill_tree "$pid"
  done
  wait 2>/dev/null

  # 정말 내려갔는지 확인 — 남아 있으면 조용히 넘어가지 않고 알려줍니다
  sleep 1
  local stuck=""
  curl -s -o /dev/null -m 2 "http://127.0.0.1:$BACKEND_PORT"  2>/dev/null && stuck="$stuck $BACKEND_PORT"
  curl -s -o /dev/null -m 2 "http://127.0.0.1:$FRONTEND_PORT" 2>/dev/null && stuck="$stuck $FRONTEND_PORT"
  if [ -n "$stuck" ]; then
    printf '[!] 아직 살아 있는 포트:%s\n' "$stuck"
    printf '    ./stop.sh 를 실행하면 확실하게 종료됩니다.\n'
  else
    printf '종료되었습니다.\n'
  fi
}
trap cleanup EXIT INT TERM

say "=========================================="
say "   Korea Job Finder"
say "=========================================="
say ""

# --- 백엔드 -----------------------------------------------------------------
say "[1/2] 백엔드 시작 -> http://127.0.0.1:$BACKEND_PORT"
(
  cd backend || exit 1
  exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
PIDS+=($!)

# 헬스체크가 통과할 때까지 최대 30초 대기
say "      백엔드 준비를 기다리는 중..."
ready=0
for _ in $(seq 1 30); do
  if curl -s -m 2 "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -eq 1 ]; then
  say "      백엔드 준비 완료"
else
  say "      [!] 백엔드가 30초 안에 응답하지 않았습니다. 아래 로그를 확인하세요."
fi

# --- 프론트엔드 -------------------------------------------------------------
say "[2/2] 프론트엔드 시작 -> http://localhost:$FRONTEND_PORT"
(
  cd frontend || exit 1
  exec npm run dev
) &
PIDS+=($!)

sleep 3

# --- 브라우저 열기 (가능한 경우) --------------------------------------------
URL="http://localhost:$FRONTEND_PORT"
if   command -v cmd.exe   >/dev/null 2>&1; then cmd.exe /c start "" "$URL" >/dev/null 2>&1 &
elif command -v open      >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 &
elif command -v xdg-open  >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 &
fi

say ""
say "------------------------------------------"
say "  화면    : $URL"
say "  API 문서: http://127.0.0.1:$BACKEND_PORT/docs"
say ""
say "  종료하려면 이 창에서 Ctrl+C 를 누르세요."
say "------------------------------------------"
say ""

# 어느 한 쪽이라도 죽을 때까지 대기
wait
