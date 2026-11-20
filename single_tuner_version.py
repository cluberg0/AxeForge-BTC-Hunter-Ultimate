#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
old='1.4.10-hunter-T1000-ONE-TUNER'
new='1.4.10-hunter-T1000-ONE-V3'
assert len(new.encode('ascii')) < 32, 'ESP app descriptor version must fit with NUL'
# Check every input before updating any of them; a stale/reordered patch must
# fail instead of producing a verifier for a different firmware version.
assert (root/'upstream/version.txt').read_text().strip() == old
updates=[]
for name in ('verify_image.py','tests/image.py'):
 p=root/name
 s=p.read_text()
 assert old in s,name
 updates.append((p,s.replace(old,new)))
for p,s in updates:
 p.write_text(s)
(root/'upstream/version.txt').write_text(new+'\n')
print(new)
