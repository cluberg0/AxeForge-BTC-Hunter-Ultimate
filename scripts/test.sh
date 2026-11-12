#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ -d upstream ]; then make -C upstream/test; fi
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ioverlay/main tests/math.cpp -o "$T/math"
"$T/math"
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Itests/stubs -Ioverlay/main tests/hunter.cpp -o "$T/hunter"
"$T/hunter"
python3 - <<'PY'
import re,pathlib,subprocess,tempfile
p=pathlib.Path('upstream/main/web/index.html')
if not p.exists(): p=pathlib.Path('overlay/main/web/index.html')
with tempfile.TemporaryDirectory() as d:
 for i,x in enumerate(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',p.read_text(),re.S)):
  f=pathlib.Path(d)/f'{i}.js'; f.write_text(x); subprocess.run(['node','--check',str(f)],check=True)
print('JavaScript syntax OK')
PY
