#!/usr/bin/env python3
"""Fail build rather than publish the old two-tuner UI or wrong OTA."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
s=(root/"upstream/main/web/index.html").read_text()
assert s==(root/"overlay/main/web/index.html").read_text(), "Browser and firmware web asset mismatch"
cpp=(root/"upstream/main/net/web.cpp").read_text()
tuner=(root/"upstream/main/core/tuner.cpp").read_text()
turbo=(root/"upstream/main/core/turbo.cpp").read_text()
for name in ('turbo.cpp','turbo.h','turbo_math.h'):
 assert (root/'upstream/main/core'/name).read_bytes()==(root/'overlay/main/core'/name).read_bytes(), f"Native tests and firmware differ: {name}"
version='1.4.10-hunter-T1000-ONE-V3'
assert (root/'upstream/version.txt').read_text().strip()==version
for name in ('verify_image.py','tests/image.py'):
 assert version in (root/name).read_text(), f"Wrong image verifier version: {name}"
assert '#include "esp_log.h"' in turbo, 'ESP logging macros need their production header'
assert '#include <algorithm>' in turbo, 'std::min/max/clamp need their production header'
assert 'storage_error' in turbo and 'confirmed_point' in turbo
assert '128+(sizeof(archive)+31)/32+4' not in turbo, 'False NVS space rejection remains'
reference=json.loads((root/'overlay/docs/native-api.json').read_text())
schema=reference['paths']['/api/turbo']['get']['responses']['200']['content']['application/json']['schema']
assert schema['properties']['storageError']['type']=='integer'
assert schema['properties']['storageDirty']['type']=='boolean'
assert 'FASTSEARCH · управление' in s
assert 'FASTSEARCH · один автотюнер' in s
assert 'data-legacy-tuner="hidden"' in s
assert 'id="legacyMode" style="display:none"' in s
assert s.count('id="turboStart"')==1
assert s.count('id="turboStop"')==1
assert s.count('id="turboPower"')==1
assert 'Начать / перезапустить поиск' not in s
assert '<h3>Профили мощности' not in s
assert 'Остановить и вернуть штатный режим' not in s
assert 'ONE-TUNER: поиск' not in cpp
assert 'Only FASTSEARCH is available on Gamma' in cpp
assert 'if(turbo::supported()){if(turbo::unlocked())turbo::request_search();}' in cpp
assert 'if(turbo::supported() && cfg.autotune)' in tuner
assert 'gamma_network_retries<2' in tuner
assert 's_hold' in tuner
assert 'turbo::power_budget()' in tuner
assert 'WARMUP_S 120' in tuner and 'FAST_WINDOW_S 120' in tuner
assert 'current_limit=std::min(amps-.5f,6.5f)' in (root/"upstream/main/core/turbo_math.h").read_text()
assert 'user>30' in (root/"upstream/main/core/turbo_math.h").read_text()
class Parser(HTMLParser):
 def __init__(self):
  super().__init__();self.scripts=[];self.inscript=False
 def handle_starttag(self,t,attrs):
  if t=='script':self.inscript=True
 def handle_endtag(self,t):
  if t=='script':self.inscript=False
 def handle_data(self,data):
  if self.inscript:self.scripts.append(data)
p=Parser();p.feed(s)
assert p.scripts, "No inline scripts"
with tempfile.NamedTemporaryFile(mode="w",suffix=".js") as f:
 f.write("\n".join(p.scripts));f.flush()
 subprocess.run(["node","--check",f.name],check=True)
print("Verified one visible FASTSEARCH tuner, one cap, safety guards and valid JS")
