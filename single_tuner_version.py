#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
old='1.4.10-hunter-T1000-ONE-TUNER'
new='1.4.10-FASTSEARCH-FIXED'
for name in ('verify_image.py','tests/image.py'):
 p=root/name
 s=p.read_text()
 assert old in s,name
 p.write_text(s.replace(old,new))
(root/'upstream/version.txt').write_text(new+'\n')
print(new)
