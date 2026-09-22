#!/usr/bin/env python3
"""Read-only lexical candidate inventory; results require caller/type review."""
import bisect, json, os, re, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
SOLVER=OUT.parents[2]
REPO=SOLVER.parent
fields={}
for cls,file in [('Engine','engine.rs'),('Input','input.rs')]:
 text=(SOLVER/'crates/kernel/src'/file).read_text()
 m=re.search(r'pub struct '+cls+r' \{(.*?)\n\}',text,re.S)
 fields[cls]=[{'field':x[1],'type':x[2],'line':text.count('\n',0,m.start(1)+x.start())+1} for x in re.finditer(r'^    pub (\w+): (.*),$',m[1],re.M)]
(OUT/'public-fields.json').write_text(json.dumps(fields,ensure_ascii=False,indent=2)+'\n')
names={x['field'] for group in fields.values() for x in group}
pat=re.compile(r'//[^\n]*|/\*.*?\*/|r(?P<hash>\#*)".*?"(?P=hash)|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\'|[A-Za-z_][A-Za-z_0-9]*|\d+|::|->|=>|==|!=|<=|>=|\+=|-=|\*=|/=|&=|\|=|&&|\|\||[^\s]',re.S)
mut_methods={'insert','remove','clear','push','pop','extend','retain','get_mut','iter_mut','values_mut','as_array_mut','as_object_mut','entry','drain','sort','sort_by','sort_by_key','swap','truncate','append','retain_mut','borrow_mut','take','replace','fill','set','update','or_insert','or_default','and_modify'}
assign={'=','+=','-=','*=','/=','&=','|='}
files=subprocess.check_output(['git','ls-files','-z'],cwd=REPO,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode().split('\0')
rows=[]; all_refs=[]; inventory=[]
for filename in files:
 if not filename.endswith('.rs'):continue
 p=REPO/filename
 s=p.read_text(); newline=[i for i,c in enumerate(s) if c=='\n']
 ts=[(m[0],m.start(),m.end()) for m in pat.finditer(s) if not m[0].startswith(('//','/*'))]
 funcs=[(m.start(),m[1]) for m in re.finditer(r'\bfn\s+(\w+)\s*[(<]',s)]
 inventory.append(filename)
 pairs={}; stack=[]
 for i,(v,_,_) in enumerate(ts):
  if v in ['(','[','{']:stack.append(i)
  elif v in [')',']','}'] and stack:
   start=stack.pop(); pairs[start]=i
 for i in range(len(ts)-2):
  v,start,_=ts[i]
  if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',v):continue
  if i and ts[i-1][0]=='.':continue
  if ts[i+1][0]!='.' or ts[i+2][0] not in names:continue
  j=i+1; chain=[]; methods=[]
  while j<len(ts):
   if ts[j][0]=='.' and j+1<len(ts):
    name=ts[j+1][0]; j+=2
    if j<len(ts) and ts[j][0]=='(' and j in pairs:
     methods.append(name);j=pairs[j]+1
    else:chain.append(name)
   elif ts[j][0]=='[' and j in pairs:j=pairs[j]+1
   elif ts[j][0]=='?':j+=1
   else:break
  op=ts[j][0] if j<len(ts) else ''
  why=[]
  if op in assign:why.append('assignment '+op)
  why += ['method '+x for x in methods if x in mut_methods]
  if i>=2 and [x[0] for x in ts[i-2:i]]==['&','mut']:why.append('mutable borrow')
  funcs_before=[f for pos,f in funcs if pos<start]
  row={'path':filename,'line':bisect.bisect_left(newline,start)+1,'function':funcs_before[-1] if funcs_before else None,'root':v,'fields':chain,'methods':methods,'expression':s[start:ts[max(i,j-1)][2]],'reasons':why}
  all_refs.append(row)
  if why:rows.append(row)
for name,data in [('write-candidates.json',rows),('field-references.json',all_refs),('rust-files.json',inventory)]:
 (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Rust files:',len(inventory),'field references:',len(all_refs),'write candidates:',len(rows))
for r in rows:
 if r['root']=='self':continue
 print(f"{r['path']}:{r['line']} {r['function']} :: {' '.join(r['expression'].split())} [{', '.join(r['reasons'])}]")
