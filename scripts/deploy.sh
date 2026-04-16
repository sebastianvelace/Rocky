#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# venv Python (rocky-engine)
python3.11 -m venv "${ROOT}/rocky-engine/.venv"
"${ROOT}/rocky-engine/.venv/bin/pip" install -r "${ROOT}/rocky-engine/requirements.txt"

# compilación Rust (rocky-ui / Tauri)
if command -v cargo >/dev/null 2>&1; then
  (cd "${ROOT}/rocky-ui/src-tauri" && cargo build --release)
else
  echo "cargo no encontrado; omite build de Rust" >&2
fi

echo "Listo: venv en rocky-engine/.venv y (si hay cargo) build en rocky-ui/src-tauri/target/release"
