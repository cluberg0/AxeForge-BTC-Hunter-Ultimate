#!/usr/bin/env python3
"""Independent, fail-closed validation of the Gamma OTA app (never a merged image)."""
import hashlib
import pathlib
import struct
import sys


def verify(b):
    def require(ok, msg):
        if not ok:
            raise ValueError(msg)
    require(0x10000 <= len(b) <= 4 * 1024 * 1024, 'outside stock 4 MiB app partition')
    require(b[0] == 0xe9 and 1 <= b[1] <= 16, 'invalid ESP image header')
    require(struct.unpack_from('<H', b, 12)[0] == 9, 'not ESP32-S3')
    require(b[23] == 1, 'missing appended digest')
    pos, checksum, segments = 24, 0xef, []
    for _ in range(b[1]):
        require(pos + 8 <= len(b), 'truncated segment header')
        addr, n = struct.unpack_from('<II', b, pos)
        pos += 8
        require(n > 0 and pos + n <= len(b), 'invalid segment length')
        segments.append((addr, n))
        for value in b[pos:pos+n]:
            checksum ^= value
        pos += n
    check = pos | 15
    require(check < len(b) and b[check] == checksum, 'segment XOR checksum mismatch')
    require(all(x == 0 for x in b[pos:check]), 'nonzero checksum padding')
    end = check + 1
    require(len(b) == end + 32, 'unexpected trailing bytes or truncated digest')
    require(b[end:] == hashlib.sha256(b[:end]).digest(), 'appended SHA-256 mismatch')
    require(struct.unpack_from('<I', b, 32)[0] == 0xabcd5432, 'missing app descriptor')
    require(b[80:112].split(b'\0', 1)[0] == b'axeforge', 'not AxeForge app')
    version = b[48:80].split(b'\0', 1)[0].decode('ascii')
    require(version == '1.4.10-hunter-ultimate-2.0', 'unexpected firmware version')
    require(b'AXEFORGE-BOARD:gamma;\0' in b, 'Gamma board tag missing')
    tags = [b'/api/hunter', b'btc_hunter', b'BLOCK CANDIDATE', b'RU-FIX 10 NATIVE',
            b'/api/intelligence', b'/api/network', b'/api/guardian', b'intelligence: returned to prior measured point']
    for tag in tags:
        require(tag in b, 'integration marker missing: ' + repr(tag))
    require(b'api.open-meteo.com' not in b and b'geocoding-api.open-meteo.com' not in b, 'weather TLS code remains')
    require(b'/api/v1/fees/mempool-blocks' not in b, 'automatic Mempool client remains')
    return {'version': version, 'size': len(b), 'segments': segments,
            'sha256': hashlib.sha256(b).hexdigest()}


if __name__ == '__main__':
    try:
        print('ESP32-S3 Gamma OTA image OK:', verify(pathlib.Path(sys.argv[1]).read_bytes()))
    except (ValueError, IndexError, OSError, struct.error) as exc:
        sys.exit('Image verification FAILED: ' + str(exc))
