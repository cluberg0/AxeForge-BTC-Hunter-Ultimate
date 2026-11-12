#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d upstream ]; then bash scripts/prepare.sh; fi
command -v idf.py >/dev/null || { echo 'ESP-IDF 5.3.2 environment not activated'; exit 1; }
[ "$(git -C "$IDF_PATH" describe --tags --exact-match)" = v5.3.2 ] || { echo 'ESP-IDF must be exactly v5.3.2'; exit 1; }
[ "$(git -C upstream rev-parse HEAD)" = e84c651c36a4b5f91c537577704245ded032592d ]
git -C upstream diff --exit-code HEAD -- partitions.csv sdkconfig.defaults sdkconfig.defaults.gamma boards/gamma.toml main/core/ota_guard.cpp main/core/ota_guard.h
mkdir -p reports
# Configure may download locked managed components; fingerprint after configure.
(cd upstream && idf.py -B build_gamma -D SDKCONFIG=build_gamma/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.gamma' reconfigure) > reports/configure.log 2>&1
python3 scripts/source_manifest.py upstream > reports/build-inputs.before.json
(cd upstream && idf.py -B build_gamma -D SDKCONFIG=build_gamma/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.gamma' build) 2>&1 | tee reports/build.log
python3 - <<'PYTHON'
from pathlib import Path
cfg = Path('upstream/build_gamma/sdkconfig').read_text().splitlines()
for expected in ['CONFIG_AF_BOARD_BITAXE_GAMMA=y', 'CONFIG_IDF_TARGET="esp32s3"', 'CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"', 'CONFIG_PARTITION_TABLE_OFFSET=0x8000', 'CONFIG_ESPTOOLPY_FLASHSIZE="16MB"', 'CONFIG_AF_MAX_FREQ_MHZ=800', 'CONFIG_AF_MAX_CORE_MV=1300', 'CONFIG_AF_MAX_CHIP_TEMP=68', 'CONFIG_AF_MAX_VR_TEMP=85']:
    assert expected in cfg, expected
board = Path('upstream/build_gamma/esp-idf/main/board/core/board_config.h').read_text().splitlines()
assert '#define AF_NUM_ASICS 1' in board and '#define AF_ASIC_BM1370 1' in board
PYTHON
(cd upstream && idf.py -B build_gamma size) > reports/size.txt 2>&1
python3 scripts/source_manifest.py upstream > reports/build-inputs.after.json
cmp reports/build-inputs.before.json reports/build-inputs.after.json || { echo 'Source changed during build; no export'; exit 1; }
python3 verify_image.py upstream/build_gamma/axeforge.bin | tee reports/image-verification.txt
esptool.py --chip esp32s3 image_info upstream/build_gamma/axeforge.bin | tee reports/image-info.txt
xtensa-esp32s3-elf-nm -C upstream/build_gamma/axeforge.elf > reports/symbols.txt
python3 - <<'PYTHON'
from pathlib import Path
s = Path('reports/symbols.txt').read_text()
for symbol in ['hunter::start()', 'intel::start()', 'guardian::start()', 'hunter::reply(', 'intel::rollback_point(', 'pools::submit(']:
    assert symbol in s, symbol
PYTHON
# Export only the app after every build/image check has succeeded.
mkdir -p dist
cp upstream/build_gamma/axeforge.bin dist/axeforge-gamma-BTC-HUNTER-ultimate.bin
(cd dist && sha256sum axeforge-gamma-BTC-HUNTER-ultimate.bin > SHA256SUMS.txt)
