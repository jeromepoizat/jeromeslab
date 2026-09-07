#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_EXECUTABLE="$REPOSITORY_ROOT/.venv/bin/python"
FRONTEND_INDEX="$REPOSITORY_ROOT/frontend/dist/index.html"

if [ ! -x "$PYTHON_EXECUTABLE" ] || [ ! -f "$FRONTEND_INDEX" ]; then
    printf "Jerome's Laboratory is not installed yet.\n" >&2
    printf 'Run ./install.sh first.\n' >&2
    exit 1
fi

cd "$REPOSITORY_ROOT"
exec "$PYTHON_EXECUTABLE" -m jeromes_laboratory.launcher.main
