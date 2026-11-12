#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "${AXEFORGE_HOST_SYSROOT:-}" ]; then
  export CPATH="$AXEFORGE_HOST_SYSROOT/usr/include:$AXEFORGE_HOST_SYSROOT/usr/include/cjson${CPATH:+:$CPATH}"
  export LIBRARY_PATH="$AXEFORGE_HOST_SYSROOT/usr/lib/x86_64-linux-gnu${LIBRARY_PATH:+:$LIBRARY_PATH}"
fi
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p reports/native-api
if [ -d upstream ]; then
  make -C upstream/test
  python3 upstream/scripts/api_contract.py
  python3 upstream/scripts/check_flasher.py
  python3 tests/api_safety.py upstream
  python3 tests/miner_pause.py upstream
fi
for module in math hunter intelligence; do
  g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -Itests/stubs -Ioverlay/main "tests/$module.cpp" -o "$T/$module"
  AXEFORGE_API_JSON=1 "$T/$module" | tee "reports/native-api/$module.log"
done
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -Ioverlay/main -I/usr/include/cjson tests/v1_wire.cpp -lcjson -o "$T/v1_wire"
"$T/v1_wire"
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -Ioverlay/main tests/uart_rx.cpp -o "$T/uart_rx"
"$T/uart_rx"
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -Itests/guardian-stubs -Itests/stubs -Ioverlay/main -Iupstream/main -I/usr/include/cjson tests/guardian.cpp -lcjson -o "$T/guardian"
AXEFORGE_API_JSON=1 "$T/guardian" | tee reports/native-api/guardian.log
python3 tests/image.py
python3 tests/target_reference.py
if [ -d upstream ]; then python3 scripts/check_native_api.py --json-dir reports/native-api; fi
python3 - <<'PY'
import re,pathlib,subprocess,tempfile
p=pathlib.Path('upstream/main/web/index.html')
if not p.exists(): p=pathlib.Path('overlay/main/web/index.html')
with tempfile.TemporaryDirectory() as d:
 for i,x in enumerate(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',p.read_text(),re.S)):
  f=pathlib.Path(d)/f'{i}.js'; f.write_text(x); subprocess.run(['node','--check',str(f)],check=True)
print('JavaScript syntax OK')
PY
