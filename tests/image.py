#!/usr/bin/env python3
"""Exercise artifact gating with synthetic images; these are never firmware outputs."""
import hashlib
import importlib.util
import pathlib
import struct

spec = importlib.util.spec_from_file_location('image_gate', pathlib.Path(__file__).resolve().parents[1] / 'verify_image.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
header = bytearray(24)
header[0:2] = b'\xe9\x01'
struct.pack_into('<H', header, 12, 9)
header[23] = 1
payload = bytearray(65536)
struct.pack_into('<I', payload, 0, 0xabcd5432)
payload[16:48] = b'1.4.10-hunter-ultimate-2.0'.ljust(32, b'\0')
payload[48:80] = b'axeforge'.ljust(32, b'\0')
markers = b'AXEFORGE-BOARD:gamma;\0/api/hunter\0btc_hunter\0BLOCK CANDIDATE\0RU-FIX 10 NATIVE\0/api/intelligence\0/api/network\0/api/guardian\0intelligence: returned to prior measured point'
payload[256:256+len(markers)] = markers

def make(payload=payload, header=header):
    image = bytearray(header) + struct.pack('<II', 0x3c000020, len(payload)) + payload
    check = 0xef
    for x in payload:
        check ^= x
    image.extend(b'\0' * ((len(image) | 15) - len(image)))
    image.append(check)
    image.extend(hashlib.sha256(image).digest())
    return image

valid = make()
assert v.verify(valid)['size'] == len(valid)
cases = [b'', valid[:200], valid+b'\0', bytes([0])+valid[1:]]
corrupt = valid.copy(); corrupt[300] ^= 1; cases.append(corrupt)
corrupt = valid.copy(); corrupt[-1] ^= 1; cases.append(corrupt)
wrong_board = payload.replace(b'BOARD:gamma;', b'BOARD:supra;'); cases.append(make(wrong_board))
wrong_chip = header.copy(); wrong_chip[12] = 0; cases.append(make(header=wrong_chip))
wrong_version = payload.replace(b'1.4.10-hunter-ultimate-2.0', b'1.4.10-hunter-ultimat0'); cases.append(make(wrong_version))
for b in cases:
    try:
        v.verify(b)
    except ValueError:
        continue
    raise AssertionError('malformed/wrong-board artifact accepted')
print('Image gate: valid synthetic image + 9 rejection cases PASS')
