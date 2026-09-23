import hashlib,json,re,subprocess
from pathlib import Path
v=Path(__file__).resolve().parent;r=v.parents[3];s=r/'求解器'
b=json.loads((v/'before.json').read_text());head=b['head']
def dump(n,x):(v/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=subprocess.check_output(['git','show',head+':求解器/数据/正式静态目录.json'],cwd=r)
oldsha=hashlib.sha256(old).hexdigest();newsha=sha(s/'数据/正式静态目录.json')
inputs=[];refs=[];other=[];all_schema={}
for name in b['work']:
    p=r/name
    if p.suffix!='.json':continue
    try:j=json.loads(p.read_text())
    except (ValueError,UnicodeError):continue
    if not isinstance(j,dict):continue
    if isinstance(j.get('catalog'),dict):
        row={'path':name,'schema':j.get('schema'),'sha256':j['catalog'].get('sha256'),'new':j['catalog'].get('sha256')==newsha}
        if name.startswith(('求解器/数据/样例/','求解器/crates/kernel/tests/fixtures/')) and j.get('schema') in ['kernel-input-v2','kernel-input-v3']:
            inputs.append(row)
            for field,reference in [('catalog',j['catalog']),('parameters.axis_registry',j['parameters']['axis_registry'])]:
                path=(p.parent/reference['path']).resolve()
                refs.append({'path':name,'field':field,'source':str(path.relative_to(r)),'match':sha(path)==reference['sha256']})
        else:other.append(row)
    if name.startswith('求解器/数据/样例/') and '参数赋值' in name:
        for field in ['profile_source','configuration_source','axis_source']:
            reference=j[field];source=(p.parent/reference['path']).resolve()
            refs.append({'path':name,'field':field,'source':str(source.relative_to(r)),'match':sha(source)==reference['sha256']})
    all_schema[name]=j.get('schema')
dump('active-inputs.json',inputs);dump('active-input-reference-check.json',refs);dump('archived-inputs.json',other)
oldhits=json.loads((v/'old-sha-outside-history.json').read_text())
groups={}
for hit in oldhits:
    name=hit['path']
    group='binary-index' if name.endswith('.db') else ('maintenance' if name.startswith('求解器/内核维护/') else 'specification')
    g=groups.setdefault(group,{'lines':0,'files':set()});g['lines']+=1;g['files'].add(name)
for g in groups.values():g['files']=sorted(g['files']);g['file_count']=len(g['files'])
dump('old-sha-classification.json',groups)
cmd=['rg','--hidden','--no-ignore','-n','-F',oldsha,'.','-g','!.git/**','-g','!**/target/**','-g','!**/__pycache__/**','-g','!求解器/crates/kernel/evidence/**','-g','!求解器/crates/kernel/复核/**','-g','!求解器/数据/复核/**','-g','!求解器/内核维护/2026-09-22h/verify/**']
p=subprocess.run(cmd,cwd=r,capture_output=True)
rg_lines=len(p.stdout.splitlines())
(v/'old-sha-rg.txt').write_bytes(p.stdout);(v/'old-sha-rg.stderr').write_bytes(p.stderr)
dump('old-sha-rg-command.json',{'argv':cmd,'exit':p.returncode,'text_lines':len(p.stdout.splitlines())})
spec=[]
for p in (s/'规格').glob('*.md'):
    for i,line in enumerate(p.read_text().splitlines(),1):
        if any(x in line for x in ['桥','last_unit']):spec.append({'path':str(p.relative_to(r)),'line':i,'text':line})
dump('spec-bridge-inventory.json',spec)
changes=[]
for row in b['status']:
    name=row[3:]
    if name.startswith('求解器/内核维护/2026-09-22h/'):continue
    path=r/name
    tracked=row[:2]!='??'
    scope=(name.startswith(('求解器/crates/kernel/src/','求解器/crates/kernel/tests/fixtures/','求解器/数据/样例/','求解器/规格/')) or name in ['求解器/crates/kernel/tests/reference.rs','求解器/crates/kernel/周期键读取审计.md','求解器/crates/topology/tests/validation.rs','求解器/数据/候选B/来源清单.json','求解器/数据/候选B/校验报告.md','求解器/数据/候选B/验证记录.md','求解器/数据/工具/formal_units.py','求解器/数据/正式静态目录.json','求解器/数据/规则覆盖表.md'])
    changes.append({'status':row[:2],'path':name,'in_sync_scope':scope,'sha256':sha(path)})
dump('status-scope.json',changes)
summary={'head':head,'old_catalog_sha256':oldsha,'new_catalog_sha256':newsha,'active_inputs':len(inputs),'bad_inputs':[x for x in inputs if not x['new']], 'reference_fields':len(refs),'bad_refs':[x for x in refs if not x['match']], 'sync_scope_files':sum(x['in_sync_scope'] for x in changes),'outside_scope':[x for x in changes if not x['in_sync_scope']], 'rg_lines':rg_lines}
dump('active-audit-result.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
