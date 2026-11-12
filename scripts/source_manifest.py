#!/usr/bin/env python3
"""Fingerprint build inputs to reject a build modified during compilation."""
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
files = set()
for directory in ['main', 'components', 'boards', 'managed_components']:
    files.update(p for p in (root / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.update(p for p in root.iterdir() if p.is_file() and (p.name.startswith('sdkconfig.defaults') or p.name in ['CMakeLists.txt', 'version.txt', 'partitions.csv', 'dependencies.lock']))
print(json.dumps({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}, indent=2, sort_keys=True))
