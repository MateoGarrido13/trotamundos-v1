#!/usr/bin/env bash
# Levanta todo el prototipo para probarlo: bases (docker compose), bases de dev/test, datos de demo,
# y la app (API + cliente web en /web + cliente móvil en /movil).
#
# Uso: scripts/ejecutar_todo.sh [opciones]
#   --tests        corre la suite de pytest antes de arrancar (excluye carga y navegador)
#   --tests-todo   corre la suite completa (incluye carga y navegador; tarda más)
#   --solo-tests   corre la suite y termina, sin arrancar la app
#   --sin-demo     no siembra los datos de prueba
#   --parar        baja los contenedores y termina (conserva los datos)
#   --limpiar      baja los contenedores y borra sus volúmenes
#   -h, --help     muestra esta ayuda
# Datos de prueba: ver scripts/sembrar_datos.py (usuarios ana@demo.com, luis@demo.com, sofia@demo.com; clave demo1234).
# Variables: PUERTO (por defecto 8000), HOST (por defecto 127.0.0.1).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
PY="$RAIZ/.venv/bin/python"
HOST="${HOST:-127.0.0.1}"
PUERTO="${PUERTO:-8000}"

TESTS=""; SOLO_TESTS=0; DEMO=1
for arg in "$@"; do
  case "$arg" in
    --tests) TESTS="basico" ;;
    --tests-todo) TESTS="todo" ;;
    --solo-tests) SOLO_TESTS=1; [ -z "$TESTS" ] && TESTS="basico" ;;
    --sin-demo) DEMO=0 ;;
    --parar) docker compose down; exit 0 ;;
    --limpiar) docker compose down -v; exit 0 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opción desconocida: $arg (usá --help)" >&2; exit 1 ;;
  esac
done

paso() { printf '\n==> %s\n' "$*"; }

if [ ! -x "$PY" ]; then
  paso "Creando .venv e instalando dependencias"
  python3 -m venv .venv
  "$PY" -m pip install -q -e ".[dev]"
fi

paso "Levantando las bases PostgreSQL (docker compose)"
docker compose up -d --wait

paso "Creando trotamundos_dev y trotamundos_test"
"$PY" scripts/crear_bases.py

if [ -n "$TESTS" ]; then
  paso "Corriendo pytest ($TESTS)"
  if [ "$TESTS" = "todo" ]; then
    "$PY" -m pytest
  else
    "$PY" -m pytest -m "not carga and not navegador"
  fi
fi
[ "$SOLO_TESTS" -eq 1 ] && exit 0

paso "Arrancando la app"
"$PY" -m uvicorn trotamundos.app:app --host "$HOST" --port "$PUERTO" &
APP=$!
trap 'kill "$APP" 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 60); do
  curl -sf "http://$HOST:$PUERTO/salud" >/dev/null && break
  kill -0 "$APP" 2>/dev/null || { echo "la app no arrancó" >&2; exit 1; }
  sleep 1
done

if [ "$DEMO" -eq 1 ]; then
  paso "Sembrando datos de prueba (cuentas, viajes y reservas)"
  "$PY" scripts/sembrar_datos.py "http://$HOST:$PUERTO"
fi

cat <<MSG

  Cliente web:    http://$HOST:$PUERTO/web/
  Cliente móvil:  http://$HOST:$PUERTO/movil/
  (Ctrl+C para detener; las bases siguen arriba, bajalas con --parar)
MSG
wait "$APP"
