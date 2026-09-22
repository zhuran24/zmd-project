#!/usr/bin/env python3
"""只读体检：活动Rust函数物理行数、重复快照及哈希；不遍历target或Git。"""
from pathlib import Path
import json,re,hashlib,os,collections
from pygments import lex
from pygments.lexers import RustLexer
from pygments.token import Comment,String
R=Path.cwd();O=R/'内核维护/2026-09-22'
def save(name,d):(O/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
functions=[]
for crate in ['kernel','topology']:
 for part in ['src','tests']:
  for p in sorted((R/f'crates/{crate}/{part}').glob('*.rs')):
   s=p.read_text();masked=''.join(re.sub(r'[^\n]',' ',v) if t in Comment or t in String else v for t,v in lex(s,RustLexer()))
   for m in re.finditer(r'\bfn\s+([A-Za-z_][A-Za-z_0-9]*)\s*(?:<|\()',masked):
    pos=masked.find('{',m.end());semi=masked.find(';',m.end())
    if pos<0 or 0<=semi<pos:continue
    depth=1;end=pos+1
    while end<len(masked) and depth:
     depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
    assert depth==0,(p,m.group(1))
    startline=masked.count('\n',0,m.start())+1;endline=masked.count('\n',0,end)+1
    functions.append(dict(file=str(p.relative_to(R)),function=m.group(1),start=startline,end=endline,lines=endline-startline+1,test=part=='tests' or p.name.startswith('tests')))
save('functions.json',{'method':'Pygments Rust lexer strips comments/strings preserving newlines; count fn keyword to balanced closing brace inclusive; includes blank/comment lines; excludes archived and legacy crates','functions':functions,'over_80':[r for r in functions if r['lines']>80]})
# Cargo.toml位置和sha逐文件记录快照树，重复按内容相等统计。
base_manifest=json.loads((O/'before.json').read_text())['files'];groups=collections.defaultdict(list)
for p,m in base_manifest.items():groups[m['sha256']].append(p)
dups=[dict(sha256=h,bytes=base_manifest[ps[0]]['bytes'],paths=ps) for h,ps in groups.items() if len(ps)>1]
roots=['数据/复核','规格/复核','crates/kernel/复核'];summary=[]
for root in roots:
 rows={p:m for p,m in base_manifest.items() if p.startswith(root+'/')}
 manifests=[p for p in rows if Path(p).name=='Cargo.toml']
 summary.append(dict(root=root,files=len(rows),bytes=sum(x['bytes'] for x in rows.values()),cargo_manifests=manifests))
save('archive-inventory.json',{'roots':summary,'duplicates':dups,'manifest_source':'before.json; byte hashes only, no copies'})
print('functions',len(functions),'over80',sum(x['lines']>80 for x in functions),'duplicate_hash_groups',len(dups))
for x in functions:
 if x['lines']>80:print(x['file'],x['function'],x['start'],x['end'],x['lines'])
