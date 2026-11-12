#!/usr/bin/env python3
"""Differential test of C++ compact-target math against Python exact integers."""
import os
from pathlib import Path
import random
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "core/hunter_math.h"
#include <iostream>
#include <iomanip>
int main() {
    uint32_t bits;
    while (std::cin >> std::hex >> bits) {
        uint8_t target[32];
        bool valid = hunter_math::target(bits, target);
        std::cout << valid << ' ' << hunter_math::btc_target_ok(bits) << ' ';
        if (valid) for (int i = 31; i >= 0; --i)
            std::cout << std::hex << std::setfill('0') << std::setw(2) << unsigned(target[i]);
        std::cout << '\n';
    }
}
'''


def main():
    rng = random.Random(1370)
    bits = [0, 0x1d00ffff, 0x207fffff, 0x01010000, 0x02000100, 0x2100ffff, 0x220000ff]
    bits += [rng.getrandbits(32) for _ in range(10000)]
    with tempfile.TemporaryDirectory(prefix='axeforge-target-') as directory:
        source = Path(directory) / 'target.cpp'
        binary = Path(directory) / 'target'
        source.write_text(HARNESS)
        subprocess.run(shlex.split(os.environ.get('CXX', 'g++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I' + str(ROOT / 'overlay/main'),
            str(source), '-o', str(binary)], check=True)
        output = subprocess.run([str(binary)], input=''.join(f'{b:08x}\n' for b in bits),
                                text=True, capture_output=True, check=True).stdout.splitlines()
    assert len(output) == len(bits), 'reference harness output truncated'
    pow_limit = 0xffff << (8 * (0x1d - 3))
    for compact, line in zip(bits, output):
        exponent, mantissa = compact >> 24, compact & 0x7fffff
        exact = (mantissa >> (8 * (3 - exponent)) if exponent <= 3
                 else mantissa << (8 * (exponent - 3)))
        expected_valid = not bool(compact & 0x800000) and 0 < exact < 2 ** 256
        valid, btc, *target = line.split()
        assert bool(int(valid)) == expected_valid, (hex(compact), line, exact)
        assert bool(int(btc)) == (expected_valid and exact <= pow_limit), (hex(compact), line, exact)
        if expected_valid:
            assert int(target[0], 16) == exact, (hex(compact), line, exact)
    print(f'Independent compact-target reference: {len(bits)} fixed/random vectors PASS; '
          'exact 256-bit value, zero/sign/overflow, BTC pow-limit')


if __name__ == '__main__':
    main()
