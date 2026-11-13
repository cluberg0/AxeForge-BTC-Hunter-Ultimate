#!/usr/bin/env python3
"""Recompile selected production units with the target toolchain to report stack frames.
No firmware output is changed. Call-chain/RTOS high-water measurements still need hardware.
"""
import json
import pathlib
import shlex
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
build = root / 'upstream/build_gamma'
commands = json.loads((build / 'compile_commands.json').read_text())
units = ['core/turbo.cpp','core/tuner.cpp','core/gates.cpp','asic/bm13xx.cpp','core/board_bitaxe.cpp','core/hunter.cpp', 'core/intelligence.cpp', 'core/guardian.cpp', 'core/net_health.cpp', 'net/weather.cpp', 'mining/miner.cpp', 'stratum/pools.cpp']
lines = ['Xtensa compiler -fstack-usage frames; static frame sizes, not full task call chains.']
with tempfile.TemporaryDirectory() as temp:
    temp = pathlib.Path(temp)
    for unit in units:
        entry = next(c for c in commands if c['file'].endswith('/main/' + unit))
        args = shlex.split(entry['command'])
        for flag, suffix in [('-o', '.o'), ('-MF', '.d')]:
            if flag in args:
                args[args.index(flag) + 1] = str(temp / (pathlib.Path(unit).stem + suffix))
        subprocess.run(args + ['-fstack-usage'], cwd=entry['directory'], check=True, capture_output=True, text=True)
        report = temp / (pathlib.Path(unit).stem + '.su')
        frames = report.read_text().splitlines()
        lines.append('\n' + unit)
        lines += sorted(frames, key=lambda s: int(s.split('\t')[-2]), reverse=True)[:20]
(root / 'reports/target-stack-usage.txt').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
