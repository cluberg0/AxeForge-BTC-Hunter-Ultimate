#!/usr/bin/env python3
import struct,sys,hashlib,pathlib
p=pathlib.Path(sys.argv[1]); b=p.read_bytes(); assert b[0]==0xe9; assert len(b)<4*1024*1024; assert struct.unpack_from('<H',b,12)[0]==9,'not ESP32-S3'; assert 1<=b[1]<=16
pos=24;c=0xef;segs=[]
for _ in range(b[1]):
 addr,n=struct.unpack_from('<II',b,pos);pos+=8;assert n and pos+n<=len(b);data=b[pos:pos+n];segs.append((addr,n));pos+=n
 for x in data:c^=x
check=pos|15;assert check<len(b) and b[check]==c,'checksum mismatch'
assert b[23]==1,'no appended digest';end=check+1;assert b[end:end+32]==hashlib.sha256(b[:end]).digest(),'app SHA mismatch';assert len(b)==end+32,'unexpected trailing bytes';assert struct.unpack_from('<I',b,32)[0]==0xabcd5432 and b[80:112].split(b'\0',1)[0]==b'axeforge','not AxeForge app';assert b'/api/hunter' in b and b'btc_hunter' in b and b'BLOCK CANDIDATE' in b,'Hunter integration missing';assert b'RU-FIX 10 NATIVE' in b,'native UI not linked';assert b'/api/intelligence' in b,'native API missing';assert b'intelligence: returned to prior measured point' in b,'native tuner integration missing'
print('ESP32-S3 image OK, segments',segs,'size',len(b),'SHA256',hashlib.sha256(b).hexdigest())
