#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -e upstream ]; then echo 'upstream exists; preserve any edits and use a fresh checkout for reapplying patches.' >&2; exit 1; fi
git clone --depth 1 --branch v1.4.10 https://github.com/IsSasoriDev/AxeForge.git upstream
python3 apply.py upstream
