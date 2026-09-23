"""Read-only Git object/index decoder; invokes no Git command and writes no Git data."""
import bisect, functools, hashlib, struct, zlib
from pathlib import Path
from audit_files import ROOT
DB=ROOT/'.git'
PACKS=[]
for p in sorted((DB/'objects/pack').glob('*.idx')):
 b=p.read_bytes(); assert b[:8]==b'\xfftOc\x00\x00\x00\x02'
 n=struct.unpack_from('>I',b,8+255*4)[0]; start=8+256*4
 ids=[b[start+20*i:start+20*(i+1)] for i in range(n)]
 offsets=struct.unpack_from('>'+str(n)+'I',b,start+24*n)
 PACKS.append((p.with_suffix('.pack'),b,ids,offsets,start+28*n))

def apply_delta(base,delta):
 pos=0
 def varint():
  nonlocal pos
  value=shift=0
  while True:
   c=delta[pos];pos+=1;value|=(c&127)<<shift
   if not c&128:return value
   shift+=7
 assert varint()==len(base); expected=varint(); out=bytearray()
 while pos<len(delta):
  op=delta[pos];pos+=1
  if op&128:
   off=size=0
   for i in range(4):
    if op&(1<<i):off|=delta[pos]<<(8*i);pos+=1
   for i in range(3):
    if op&(16<<i):size|=delta[pos]<<(8*i);pos+=1
   size=size or 0x10000;out.extend(base[off:off+size])
  else:
   assert op;out.extend(delta[pos:pos+op]);pos+=op
 assert len(out)==expected;return bytes(out)

@functools.lru_cache(maxsize=1024)
def packed(path,off):
 with path.open('rb') as f:
  f.seek(off);c=f.read(1)[0];typ=(c>>4)&7;size=c&15;shift=4
  while c&128:
   c=f.read(1)[0];size|=(c&127)<<shift;shift+=7
  parent=None
  if typ==6:
   c=f.read(1)[0];distance=c&127
   while c&128:c=f.read(1)[0];distance=((distance+1)<<7)+(c&127)
   parent=(path,off-distance)
  elif typ==7:parent=f.read(20).hex()
  z=zlib.decompressobj();chunks=[]
  while not z.eof:
   chunk=f.read(65536);assert chunk
   chunks.append(z.decompress(chunk))
 data=b''.join(chunks);assert len(data)==size
 if typ in (6,7):
  kind,base=packed(*parent) if typ==6 else obj(parent)
  return kind,apply_delta(base,data)
 return {1:'commit',2:'tree',3:'blob',4:'tag'}[typ],data

@functools.lru_cache(maxsize=2048)
def obj(oid):
 loose=DB/'objects'/oid[:2]/oid[2:]
 if loose.exists():
  raw=zlib.decompress(loose.read_bytes());hdr,data=raw.split(b'\0',1);kind,size=hdr.decode().split();assert len(data)==int(size)
 else:
  key=bytes.fromhex(oid)
  for path,b,ids,offsets,longstart in PACKS:
   i=bisect.bisect_left(ids,key)
   if i<len(ids) and ids[i]==key:
    off=offsets[i]
    if off&0x80000000:off=struct.unpack_from('>Q',b,longstart+8*(off&0x7fffffff))[0]
    kind,data=packed(path,off);break
  else:raise FileNotFoundError(oid)
 assert hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid
 return kind,data

def resolve(prefix):
 if len(prefix)==40:return prefix
 hits=set()
 for _,_,ids,_,_ in PACKS:hits.update(o.hex() for o in ids if o.hex().startswith(prefix))
 d=DB/'objects'/prefix[:2]
 if d.is_dir():hits.update(prefix[:2]+p.name for p in d.iterdir() if (prefix[:2]+p.name).startswith(prefix))
 assert len(hits)==1,(prefix,hits);return hits.pop()

def tree(oid,prefix=''):
 kind,data=obj(oid);assert kind=='tree';pos=0;rows={}
 while pos<len(data):
  end=data.index(b'\0',pos);mode,name=data[pos:end].split(b' ',1);child=data[end+1:end+21].hex();pos=end+21
  path=prefix+name.decode()
  if mode==b'40000':rows.update(tree(child,path+'/'))
  else:rows[path]={'mode':int(mode,8),'oid':child}
 return rows

def commit(oid):
 oid=resolve(oid);kind,data=obj(oid);assert kind=='commit'
 return oid,data,tree(data.splitlines()[0].split()[1].decode())

def index():
 b=(DB/'index').read_bytes();assert hashlib.sha1(b[:-20]).digest()==b[-20:]
 sig,version,n=struct.unpack_from('>4sII',b);assert sig==b'DIRC' and version==2
 pos=12;rows={}
 for _ in range(n):
  start=pos;values=struct.unpack_from('>10I20sH',b,pos);flags=values[-1];assert not flags&0x4000
  pos+=62;end=b.index(b'\0',pos);name=b[pos:end].decode();pos=start+((end+1-start+7)//8)*8
  assert not flags&0x3000,'unmerged entry';rows[name]={'mode':values[6],'oid':values[10].hex()}
 return rows

def head():
 s=(DB/'HEAD').read_text().strip()
 if s.startswith('ref: '):
  ref=s[5:];p=DB/ref
  if p.exists():return p.read_text().strip()
  for line in (DB/'packed-refs').read_text().splitlines():
   if line.endswith(' '+ref):return line.split()[0]
  raise ValueError(ref)
 return s
