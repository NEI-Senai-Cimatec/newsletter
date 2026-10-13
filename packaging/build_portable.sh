#!/usr/bin/env bash
# Builds the portable QuIIN artifact on Linux or macOS:
#   Linux: dist/QuIIN-Portable-Linux-x64.tar.gz  (smoke runs under xvfb-run)
#   macOS: dist/QuIIN-Portable-macOS-<arch>.zip  (QuIIN.app, symlinks preserved)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv-build
.venv-build/bin/python -m pip install --upgrade pip
.venv-build/bin/python -m pip install -r requirements.txt -r requirements-build.txt
.venv-build/bin/python -m PyInstaller --clean --noconfirm packaging/quiin.spec

if [[ "$(uname)" == "Darwin" ]]; then
    .venv-build/bin/python packaging/smoke_test.py
    ARCH="$(uname -m)"
    rm -f "dist/QuIIN-Portable-macOS-${ARCH}.zip"
    ditto -c -k --keepParent "dist/QuIIN.app" "dist/QuIIN-Portable-macOS-${ARCH}.zip"
    echo "Portable package ready: dist/QuIIN-Portable-macOS-${ARCH}.zip"
else
    xvfb-run -a .venv-build/bin/python packaging/smoke_test.py
    rm -f dist/QuIIN-Portable-Linux-x64.tar.gz
    tar -C dist -czf dist/QuIIN-Portable-Linux-x64.tar.gz QuIIN
    echo "Portable package ready: dist/QuIIN-Portable-Linux-x64.tar.gz"
fi
