#!/usr/bin/env python3
"""Wire the optional observer after pinned Hunter integration, without changing flash/guards."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
changes = {
    'main/main.cpp': [('#include "core/hunter.h"', '#include "core/hunter.h"\n#include "core/guardian.h"'),
                      ('    hunter::start();', '    hunter::start();\n    guardian::start();')],
    'main/net/web.cpp': [('#include "core/hunter.h"', '#include "core/hunter.h"\n#include "core/guardian.h"'),
                         ('        {"/api/hunter", HTTP_GET, hunter::get, NULL},',
                          '        {"/api/hunter", HTTP_GET, hunter::get, NULL},\n        {"/api/guardian", HTTP_GET, guardian::get, NULL},\n        {"/api/guardian", HTTP_POST, guardian::set, NULL},'),
                         ('    cfg.max_uri_handlers = 40;', '    cfg.max_uri_handlers = 42;')],
}
for filename, edits in changes.items():
    path = root / filename
    source = path.read_text()
    for old, new in edits:
        assert source.count(old) == 1, (filename, old, source.count(old))
        source = source.replace(old, new)
    path.write_text(source)
print('Optional guardian observer hooked through stock API guard')
