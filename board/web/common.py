"""Shared on-board web files and geometry; no robot control imports."""
import json, math, os, struct, time, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'board/web-state'
CACHE=STATE/'cache'

def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return {} if default is None else default

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    temp.write_bytes(data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False,allow_nan=False).encode())
    temp.replace(path)

def fresh(d,seconds=2):
    return bool(d.get('ready') and 0<=time.time()-d.get('updated',0)<seconds)

def pose(value):
    if not isinstance(value,list) or len(value)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in value):raise ValueError('位置需为有限的 x、y、朝向')
    if abs(value[0])>10000 or abs(value[1])>10000:raise ValueError('位置超出允许范围')
    return [float(value[0]),float(value[1]),math.atan2(math.sin(value[2]),math.cos(value[2]))]

def name(value):
    if not isinstance(value,str) or not value.strip() or len(value)>64 or any(ord(c)<32 for c in value):raise ValueError('请输入1–64字符的点名称')
    return value.strip()

def png(width,height,raw):
    """8-bit grayscale, top row first."""
    def chunk(k,v):return struct.pack('!I',len(v))+k+v+struct.pack('!I',zlib.crc32(k+v)&0xffffffff)
    scan=b''.join(b'\0'+raw[y*width:(y+1)*width] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(scan,2))+chunk(b'IEND',b'')
