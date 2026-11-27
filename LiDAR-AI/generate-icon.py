import struct,zlib,math
from pathlib import Path
n=1024
p=[(512,145),(830,330),(830,695),(512,880),(194,695),(194,330),(512,510)]
edges=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,0),(5,6),(1,6),(6,3),(0,6),(4,6),(2,6)]
def distance(x,y,a,b):
    ax,ay=p[a]; bx,by=p[b]; dx=bx-ax; dy=by-ay
    t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
    return (x-ax-t*dx)**2+(y-ay-t*dy)**2
raw=bytearray()
for y in range(n):
    raw.append(0)
    for x in range(n):
        d=min(distance(x,y,a,b) for a,b in edges)
        raw.extend((44,226,208) if d<100 else (16,25,35))
def chunk(t,d):return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
out=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack(">2I5B",n,n,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')
Path("LiDARAI/Assets.xcassets/AppIcon.appiconset/Icon.png").write_bytes(out)
