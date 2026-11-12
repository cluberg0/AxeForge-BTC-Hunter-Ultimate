#!/usr/bin/env bash
# Developer-only setup. iPhone OTA installation does not require this toolchain.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
IDF_CHECKOUT=${AXEFORGE_IDF_CHECKOUT:-"$ROOT/.tools/esp-idf"}
export IDF_TOOLS_PATH=${IDF_TOOLS_PATH:-"$ROOT/.tools/idf-tools"}
if [ ! -d "$IDF_CHECKOUT/.git" ]; then
  git clone --branch v5.3.2 --depth 1 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git "$IDF_CHECKOUT"
fi
[ "$(git -C "$IDF_CHECKOUT" describe --tags --exact-match)" = v5.3.2 ] || { echo 'Wrong ESP-IDF release'; exit 1; }
"$IDF_CHECKOUT/install.sh" esp32s3
printf 'Activate with: export IDF_TOOLS_PATH=%q; source %q\n' "$IDF_TOOLS_PATH" "$IDF_CHECKOUT/export.sh"
