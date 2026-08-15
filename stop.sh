#!/usr/bin/env bash
#
# 8000 / 5173 포트를 쓰고 있는 서버를 확실히 종료합니다.
#
#   ./stop.sh
#
# Git Bash 에서 Ctrl+C 로 start.sh 를 멈춰도 uvicorn / node 가 살아남아 포트를
# 붙잡고 있는 경우가 있습니다. 그때 이 스크립트를 쓰면 됩니다.

set -uo pipefail

PORTS=(8000 5173)
killed=0

kill_windows_port() {
  local port="$1" found=0
  # NOTE: no "-p TCP" filter here on purpose. Vite listens on IPv6 ([::1]:5173),
  # and "netstat -ano -p TCP" only lists IPv4 - the frontend would be missed.
  while read -r pid; do
    [ -z "$pid" ] && continue
    [ "$pid" = "0" ] && continue
    if MSYS_NO_PATHCONV=1 taskkill /PID "$pid" /T /F >/dev/null 2>&1; then
      printf '  %s 포트: PID %s 종료\n' "$port" "$pid"
      found=1
    fi
  done < <(netstat -ano 2>/dev/null | awk -v p=":$port " '$0 ~ p && /LISTENING/ { print $NF }' | sort -u)
  return $((1 - found))
}

kill_unix_port() {
  local port="$1" pids
  pids=$(lsof -ti "tcp:$port" 2>/dev/null)
  [ -z "$pids" ] && return 1
  for pid in $pids; do
    kill -TERM "$pid" 2>/dev/null && printf '  %s 포트: PID %s 종료\n' "$port" "$pid"
  done
  sleep 1
  for pid in $pids; do
    kill -KILL "$pid" 2>/dev/null
  done
  return 0
}

printf '실행 중인 서버를 종료합니다...\n'

for port in "${PORTS[@]}"; do
  if command -v taskkill >/dev/null 2>&1; then
    kill_windows_port "$port" && killed=1
  else
    kill_unix_port "$port" && killed=1
  fi
done

sleep 1

# "localhost" 로 확인합니다. Vite 는 IPv6 에만 바인딩하므로 127.0.0.1 로 확인하면
# 아직 살아 있는데도 "종료됨" 으로 잘못 보고합니다.
still=""
for port in "${PORTS[@]}"; do
  if curl -s -o /dev/null -m 2 "http://localhost:$port" 2>/dev/null; then
    still="$still $port"
  fi
done

if [ -n "$still" ]; then
  printf '\n[!] 아직 응답하는 포트:%s\n' "$still"
  printf '    작업 관리자에서 python / node 를 직접 종료해 주세요.\n'
  exit 1
fi

if [ "$killed" -eq 1 ]; then
  printf '\n모두 종료되었습니다.\n'
else
  printf '\n실행 중인 서버가 없습니다.\n'
fi
