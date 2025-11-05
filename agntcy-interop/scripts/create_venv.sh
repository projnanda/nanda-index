#!/usr/bin/env bash
# Simple helper to create and activate a Python virtual environment for nanda-index
# Usage: source scripts/create_venv.sh

set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ -d "$VENV_DIR" ]; then
  echo "[venv] Directory $VENV_DIR already exists. Reusing it."
else
  echo "[venv] Creating virtual environment in $VENV_DIR using $PYTHON_BIN"
  $PYTHON_BIN -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[venv] Activated. Python: $(python --version)"
echo "[venv] Installing dependencies from requirements.txt"
pip install --upgrade pip
pip install -r requirements.txt

echo "[venv] Done. To deactivate: 'deactivate'"
