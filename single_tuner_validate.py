#!/usr/bin/env python3
"""Fail build rather than publish the old two-tuner UI or wrong OTA."""
from pathlib import Path
import subprocess
import tempfile
from html.parser import HTMLParser
s=Path("upstream/main/web/index.html").read_text()
assert s==Path("overlay/main/web/index.html").read_text(), "Browser and firmware web asset mismatch"
cpp=Path("upstream/main/net/web.cpp").read_text()
tuner=Path("upstream/main/core/tuner.cpp").read_text()
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
assert 'gamma_network_retries<2' not in tuner
assert 'if(gamma_network_retries<5)++gamma_network_retries;' in tuner
assert 'pdMS_TO_TICKS(120000u * gamma_network_retries)' in tuner
assert 'turbo::reason()==turbo::Reason::Network' in tuner
assert 's_hold' in tuner
assert 'turbo::power_budget()' in tuner
assert 'WARMUP_S 120' in tuner and 'FAST_WINDOW_S 120' in tuner
assert 'current_limit=std::min(amps-.5f,6.5f)' in Path("upstream/main/core/turbo_math.h").read_text()
assert 'user>30' in Path("upstream/main/core/turbo_math.h").read_text()
class Parser(HTMLParser):
 def __init__(self):
  super().__init__();self._scripts=[];self.inscript=False
 def handle_starttag(self,t,attrs):
  if t=='script':self.inscript=True
 def handle_endtag(self,t):
  if t=='script':self.inscript=False
 def handle_data(self,data):
  if self.inscript:self._scripts.append(data)
 def javascript(self):
  assert self._scripts, "No inline scripts"
  return "\n".join(self._scripts)
p=Parser();p.feed(s);p.close()
with tempfile.NamedTemporaryFile(mode="w",suffix=".js") as f:
 f.write(p.javascript());f.flush()
 subprocess.run(["node","--check",f.name],check=True)
print("Verified one visible FASTSEARCH tuner, one cap, safety guards and valid JS")
