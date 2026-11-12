#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d upstream ]; then bash scripts/prepare.sh; fi
command -v idf.py >/dev/null || { echo 'ESP-IDF 5.3.2 environment not activated'; exit 1; }
(cd upstream && idf.py -B build_gamma -D SDKCONFIG=build_gamma/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.gamma' build)
python3 verify_image.py upstream/build_gamma/axeforge.bin
esptool.py --chip esp32s3 image_info upstream/build_gamma/axeforge.bin
mkdir -p dist
cp upstream/build_gamma/axeforge.bin dist/axeforge-gamma-RU-fix10-btc-hunter.bin
(cd dist && sha256sum *.bin > SHA256SUMS.txt)
