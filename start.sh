#!/usr/bin/env bash
# CodeLayer Forge starter: set up once, then start, stop and watch the local services.
#
#   ./start.sh              set up if needed, then start everything (same as: ./start.sh up)
#   ./start.sh up [--open]  start the web shell, the engineering workbench and the embeddyn Lab in the background
#   ./start.sh stop [name]  stop them (or one: web, workbench, lab); restart [--open] stops and starts again
#   ./start.sh status       what is running, on which port
#   ./start.sh logs [name]  follow a service's log (web, workbench, lab)
#   ./start.sh setup        Python environment with the embeddyn engine, git submodule, plugin catalog
#   ./start.sh lab [file]   the embeddyn Lab in the foreground (optionally with a project file)
#   ./start.sh broker       the capability broker in the foreground (JSON-RPC on stdin/stdout)
#   ./start.sh doctor       check the tools (Python, Node, Rust ...)
#   ./start.sh test         Forge's tests and the engine's mechatronics tests
#
# Environment:
#   FORGE_PYTHON     Python to use (default: .venv here, else engines/embeddyn/.venv, else a new .venv)
#   WEB_PORT=4173    web shell       WORKBENCH_PORT=8765   engineering workbench
#   LAB_PORT=8710    embeddyn Lab    LAB_PROJECT           project the Lab opens (engine-relative or absolute)
#   RENODE_BIN, NGSPICE_LIBRARY      passed through to the Lab (firmware and circuit simulators)
#
# Services bind to 127.0.0.1 only: the Lab's API runs simulators and writes files. State, PIDs and logs are in
# .codelayer/state/ (ignored by git).
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENGINE="$ROOT/engines/embeddyn"
STATE="$ROOT/.codelayer/state"
RUN="$STATE/run"
LOGS="$STATE/logs"
WEB_PORT=${WEB_PORT:-4173}
WORKBENCH_PORT=${WORKBENCH_PORT:-8765}
LAB_PORT=${LAB_PORT:-8710}
LAB_PROJECT=${LAB_PROJECT:-examples/mechatronics/rc-servo-lab.yaml}
SERVICES=(web workbench lab)

if [ -t 1 ]; then BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; OFF=$'\e[0m'
else BOLD=; DIM=; RED=; GREEN=; YELLOW=; OFF=; fi
say()  { printf '%s\n' "$*"; }
info() { printf '%s==>%s %s\n' "$BOLD" "$OFF" "$*"; }
warn() { printf '%swarning:%s %s\n' "$YELLOW" "$OFF" "$*" >&2; }
die()  { printf '%serror:%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }

# --- Python ---------------------------------------------------------------------------------------------------

system_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
      command -v "$candidate"; return 0
    fi
  done
  return 1
}

# The Python that runs the plugin hosts and the Lab: it must have the embeddyn engine and its dependencies.
forge_python() {
  if [ -n "${FORGE_PYTHON:-}" ]; then printf '%s\n' "$FORGE_PYTHON"; return 0; fi
  local venv
  for venv in "$ROOT/.venv" "$ENGINE/.venv"; do
    if [ -x "$venv/bin/python" ]; then printf '%s\n' "$venv/bin/python"; return 0; fi
  done
  return 1
}

engine_ready() {
  local py=$1
  ( cd "$ENGINE" && "$py" -c 'import embeddyn.mechatronics.gui.server, yaml, typer' ) >/dev/null 2>&1
}

# --- setup ------------------------------------------------------------------------------------------------------

ensure_submodule() {
  if [ ! -f "$ENGINE/pyproject.toml" ]; then
    info "Fetching the embeddyn engine (git submodule engines/embeddyn)"
    git -C "$ROOT" submodule update --init engines/embeddyn || die "could not fetch engines/embeddyn"
  fi
}

setup() {
  local py base
  ensure_submodule
  if py=$(forge_python) && engine_ready "$py"; then
    info "Python environment ready: $py"
  else
    if [ -z "${FORGE_PYTHON:-}" ] && [ ! -x "$ROOT/.venv/bin/python" ]; then
      base=$(system_python) || die "Python 3.11 or newer is needed (python3.11 / python3.12 / python3)"
      info "Creating the Python environment .venv (with $base)"
      "$base" -m venv "$ROOT/.venv"
    fi
    py=$(forge_python)
    info "Installing the embeddyn engine into $py (first run: downloads its dependencies)"
    "$py" -m pip install --upgrade pip >/dev/null
    "$py" -m pip install -e "$ENGINE" pytest pytest-asyncio httpx
    engine_ready "$py" || die "the engine does not import with $py: see the pip output above"
  fi
  # the catalog is checked in: rebuild it only when a plugin manifest changed (keeps the work tree clean)
  local catalog="$ROOT/apps/desktop/web/catalog.json"
  if [ ! -f "$catalog" ] || [ -n "$(find "$ROOT/plugins" -name plugin.toml -newer "$catalog" -print -quit)" ]; then
    info "Building the plugin catalog"
    ( cd "$ROOT" && "$py" scripts/build_catalog.py >/dev/null )
  fi
  mkdir -p "$RUN" "$LOGS"
}

# --- services ---------------------------------------------------------------------------------------------------

port_of() {
  case $1 in web) printf '%s' "$WEB_PORT";; workbench) printf '%s' "$WORKBENCH_PORT";; lab) printf '%s' "$LAB_PORT";; esac
}

pid_of() {
  local file="$RUN/$1.pid"
  [ -f "$file" ] || return 1
  local pid; pid=$(cat "$file")
  if kill -0 "$pid" 2>/dev/null; then printf '%s' "$pid"; return 0; fi
  rm -f "$file"; return 1
}

port_busy() {
  "$PY" - "$1" <<'EOF'
import socket, sys
s = socket.socket()
s.settimeout(0.3)
busy = s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0
s.close()
raise SystemExit(0 if busy else 1)
EOF
}

wait_http() {   # name port seconds
  local i
  for ((i = 0; i < $3 * 4; i++)); do
    if "$PY" - "$2" <<'EOF' 2>/dev/null
import sys, urllib.request
urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/", timeout=1).read(64)
EOF
    then return 0; fi
    pid_of "$1" >/dev/null || return 1
    sleep 0.25
  done
  return 1
}

start_service() {   # name, then the command (run from its directory)
  local name=$1 dir=$2; shift 2
  local port; port=$(port_of "$name")
  if pid=$(pid_of "$name"); then
    say "  ${GREEN}●${OFF} $name already running (pid $pid) on http://127.0.0.1:$port"; return 0
  fi
  if port_busy "$port"; then
    warn "$name: port $port is in use by another program (set ${name^^}_PORT to choose another)"; return 1
  fi
  : > "$LOGS/$name.log"
  ( cd "$dir" && exec setsid "$@" ) >>"$LOGS/$name.log" 2>&1 < /dev/null &
  printf '%s' "$!" > "$RUN/$name.pid"
  if wait_http "$name" "$port" 40; then
    say "  ${GREEN}●${OFF} $name  http://127.0.0.1:$port"
  else
    say "  ${RED}●${OFF} $name did not come up; last lines of $LOGS/$name.log:"
    tail -n 15 "$LOGS/$name.log" | sed 's/^/      /'
    stop_service "$name" quiet
    return 1
  fi
}

stop_service() {
  local name=$1 pid
  if pid=$(pid_of "$name"); then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -KILL -- "-$pid" 2>/dev/null || true
    rm -f "$RUN/$name.pid"
    [ "${2:-}" = quiet ] || say "  stopped $name (pid $pid)"
  else
    [ "${2:-}" = quiet ] || say "  ${DIM}$name was not running${OFF}"
  fi
}

up() {
  local open=0 failed=0
  [ "${1:-}" = "--open" ] && open=1
  setup
  info "Starting services"
  start_service web "$ROOT" "$PY" -m http.server "$WEB_PORT" --bind 127.0.0.1 --directory apps/desktop/web || failed=1
  if [ -d "$ROOT/engineering-workbench/standalone" ]; then
    start_service workbench "$ROOT/engineering-workbench" \
      "$PY" -m http.server "$WORKBENCH_PORT" --bind 127.0.0.1 --directory standalone || failed=1
  fi
  start_service lab "$ENGINE" "$PY" -m embeddyn mechatronics gui "$LAB_PROJECT" --port "$LAB_PORT" || failed=1
  say ""
  say "  Web shell              http://127.0.0.1:$WEB_PORT"
  say "  Engineering workbench  http://127.0.0.1:$WORKBENCH_PORT"
  say "  embeddyn Lab           http://127.0.0.1:$LAB_PORT"
  say "  ${DIM}logs: ./start.sh logs <web|workbench|lab>    stop: ./start.sh stop${OFF}"
  [ -n "${RENODE_BIN:-}" ] || say "  ${DIM}RENODE_BIN is not set: Renode parts in the Lab need it (or tick \"mock hardware\")${OFF}"
  if [ "$open" = 1 ] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:$WEB_PORT" >/dev/null 2>&1 || true
    xdg-open "http://127.0.0.1:$LAB_PORT" >/dev/null 2>&1 || true
  fi
  return "$failed"
}

status() {
  local name pid port
  for name in "${SERVICES[@]}"; do
    port=$(port_of "$name")
    if pid=$(pid_of "$name"); then
      say "  ${GREEN}●${OFF} $(printf '%-10s' "$name") pid $(printf '%-8s' "$pid") http://127.0.0.1:$port"
    else
      say "  ${DIM}○ $(printf '%-10s' "$name") stopped${OFF}"
    fi
  done
}

# --- commands ---------------------------------------------------------------------------------------------------

command=${1:-up}
[ $# -gt 0 ] && shift
mkdir -p "$RUN" "$LOGS"

case $command in
  up|start)
    ensure_submodule
    PY=$(forge_python || true)
    if [ -z "$PY" ]; then setup; PY=$(forge_python); fi
    up "$@" ;;
  stop)
    names=("$@"); [ ${#names[@]} -gt 0 ] || names=("${SERVICES[@]}")
    for name in "${names[@]}"; do
      case " ${SERVICES[*]} " in *" $name "*) stop_service "$name";; *) die "unknown service '$name' (${SERVICES[*]})";; esac
    done ;;
  restart)
    for name in "${SERVICES[@]}"; do stop_service "$name" quiet; done
    PY=$(forge_python || true); [ -n "$PY" ] || { setup; PY=$(forge_python); }
    up "$@" ;;
  status)
    status ;;
  logs)
    name=${1:-lab}
    [ -f "$LOGS/$name.log" ] || die "no log for '$name' (services: ${SERVICES[*]})"
    exec tail -n 50 -f "$LOGS/$name.log" ;;
  setup)
    setup; PY=$(forge_python)
    info "Ready. Start everything with: ./start.sh" ;;
  lab)
    PY=$(forge_python) || { setup; PY=$(forge_python); }
    project=${1:-$LAB_PROJECT}
    [ $# -gt 0 ] && shift
    case $project in /*) ;; *) [ -e "$ENGINE/$project" ] || project="$PWD/$project";; esac
    cd "$ENGINE" && exec "$PY" -m embeddyn mechatronics gui "$project" --port "$LAB_PORT" "$@" ;;
  broker)
    PY=$(forge_python) || { setup; PY=$(forge_python); }
    cd "$ROOT" && exec "$PY" hosts/plugin-broker/forge_broker.py --plugins-root plugins \
      --workspace "${1:-examples/demo-workspace}" ;;
  doctor)
    py=$(forge_python || system_python || true)
    [ -n "$py" ] || die "no Python 3.11+ found"
    "$py" "$ROOT/scripts/doctor.py"
    if engine_ready "$py"; then say "embeddyn   OK               $py"
    else say "embeddyn   MISSING          run ./start.sh setup"; fi ;;
  test)
    PY=$(forge_python) || { setup; PY=$(forge_python); }
    ( cd "$ROOT" && "$PY" -m unittest discover -s tests )
    ( cd "$ENGINE" && "$PY" -m pytest -q -p no:cacheprovider tests/mechatronics ) ;;
  -h|--help|help)
    sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)
    die "unknown command '$command' (try: ./start.sh help)" ;;
esac
