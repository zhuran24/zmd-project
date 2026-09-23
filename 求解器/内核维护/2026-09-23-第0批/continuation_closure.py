import json,re
from pathlib import Path
def words(s):
 out=[];buf='';i=0
 while i<len(s):
  if s[i]=='\\':
   i+=1
   if i<len(s):
    if s[i]!='\n':buf+=s[i]
  elif s[i]=='$' and i+1<len(s) and s[i+1]=='$':buf+='$';i+=1
  elif s[i].isspace():
   if buf:out.append(buf);buf=''
  else:buf+=s[i]
  i+=1
 if buf:out.append(buf)
 return out
def dependencies(artifact,root):
 p=Path(artifact['filenames'][0]);d=p.with_name(p.stem.removeprefix('lib')+'.d') if artifact['target']['kind']==['lib'] else Path(artifact['executable']).with_suffix('.d')
 raw=d.read_text().replace('\\\n','');rows=[]
 for line in raw.splitlines():
  sep=re.search(r'(?<!\\):(?:\s|$)',line)
  if not sep:continue
  targets=words(line[:sep.start()]);deps=words(line[sep.start()+1:])
  if str(p) in targets:rows.append(deps)
 assert len(rows)==1,(str(p),str(d),len(rows))
 resolved=[str((root/x).resolve()) for x in rows[0]]
 assert len(resolved)==len(set(resolved)),('duplicate dependency',str(d))
 return d,set(resolved)
def compare_checker(closures,record,root):
 names=[str((root/'crates/kernel/src'/Path(x['path']).name).resolve()) for x in record['fingerprints'] if x['role']=='checker' and x['path'].endswith('.rs')]
 assert len(names)==len(set(names))
 rust=set(names);lib=closures['kernel:lib'];bin=closures['kernel:bin'];embed={str(root/'数据/正式静态目录.json'),str(root/'规格/内核配置-v1.json')}
 assert lib==rust-{str(root/'crates/kernel/src/main.rs')}|embed, {'lib_missing':sorted(lib-(rust|embed)),'uncompiled':sorted((rust-{str(root/'crates/kernel/src/main.rs')}|embed)-lib)}
 assert bin==rust|embed,{'bin_missing':sorted(bin-(rust|embed)),'uncompiled':sorted((rust|embed)-bin)}
 refs={str(Path(x['path']).resolve()) for x in record['fingerprints']}
 assert embed<=refs
 return True
