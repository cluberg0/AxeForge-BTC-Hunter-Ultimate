#!/usr/bin/env python3
"""Package verified TURBO1000, rollback2.0, GPL source and validation evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_image import verify
OUT=ROOT/'dist/unlock'
APP=OUT/'axeforge-gamma-BTC-HUNTER-TURBO1000-UNLOCK.bin'
meta=verify(APP.read_bytes())
listed=(OUT/'SHA256SUMS.txt').read_text().split()[0]
assert meta['sha256']==listed
current=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/source_manifest.py'),str(ROOT/'upstream')],text=True))
assert current==json.loads((ROOT/'reports/build-inputs.before.json').read_text())==json.loads((ROOT/'reports/build-inputs.after.json').read_text()),'Sources differ from compiled image'
backup=OUT/'backup/axeforge-gamma-BTC-HUNTER-ultimate-2.0-TURBO1000.bin'
assert hashlib.sha256(backup.read_bytes()).hexdigest()==(backup.parent/'SHA256SUMS.txt').read_text().split()[0]
for name in ['README.md','LICENSE','CHANGELOG.md','TEST-REPORT.md','INSTALL-IPHONE.md','HARDWARE-TEST-PLAN.md','POOL-ARCHITECTURE.md']:
    shutil.copy2(ROOT/name,OUT/name)
(OUT/'debug').mkdir(exist_ok=True)
for name in ['axeforge.elf','axeforge.map','sdkconfig']:
    shutil.copy2(ROOT/'upstream/build_gamma'/name,OUT/'debug'/name)
shutil.copy2(ROOT/'upstream/build_gamma/esp-idf/main/board/core/board_config.h',OUT/'debug/board_config.h')
(OUT/'reports').mkdir(exist_ok=True)
for name in ['image-info.txt','image-verification.txt','size.txt','target-stack-usage.txt','build-inputs.before.json','build-inputs.after.json']:
    shutil.copy2(ROOT/'reports'/name,OUT/'reports'/name)
for name in ['TESTS.log','BUILD.log','REPRO.log','browser-chromium-final.log','browser-webkit-final.log','build-metadata.json']:
    shutil.copy2(ROOT/'reports/unlock'/name,OUT/'reports'/name)
shutil.copytree(ROOT/'dist/screenshots',OUT/'screenshots',dirs_exist_ok=True)
source=OUT/'AxeForge-BTC-HUNTER-TURBO1000-UNLOCK-source.zip'
release=OUT/'AxeForge-BTC-HUNTER-TURBO1000-UNLOCK-release.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
    for p in ROOT.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(ROOT);parts=rel.parts
        if parts[0]in ['dist','.venv','.tools','test-results']or '__pycache__'in parts:continue
        if parts[0]=='upstream'and(any(n.startswith('build')for n in parts[1:2])or 'worktrees'in parts or(len(parts)>2 and parts[1]=='test'and(parts[2]in['unit_tests','gen']or p.suffix=='.o'))):continue
        z.write(p,Path('axeforge')/rel)
with zipfile.ZipFile(release,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
    for p in OUT.rglob('*'):
        if p.is_file()and p!=release:z.write(p,p.relative_to(OUT),compress_type=zipfile.ZIP_STORED if p.suffix=='.zip'else zipfile.ZIP_DEFLATED)
for p in [source,release]:
    with zipfile.ZipFile(p)as z:assert z.testzip()is None
    print(p.name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
with zipfile.ZipFile(release)as z:assert hashlib.sha256(z.read(APP.name)).hexdigest()==listed
print('PASS ZIP CRC, packaged OTA and rollback checksums')
