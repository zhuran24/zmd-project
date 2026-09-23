from guard import ROOT,REPO,OUT,SOURCES,HISTORY,digest,save,guard,active_snapshot,difference
from helpers import dump
from pathlib import Path
from collections import Counter
import json,subprocess,sys,re,copy
guard('audit-final-before')
load=lambda p:json.loads(p.read_text())
sync=load(OUT/'sync-summary.json');cat=load(ROOT/'数据/正式静态目录.json')
sys.path.insert(0,str(ROOT/'数据/工具'))
from formal_catalog import verify,source_snapshot,formal_projection,recipe_projection,unit_projection,quantity
verify(cat)
oldcat=load(OUT/'before/数据/正式静态目录.json')
assert [u['id'] for u,v in zip(oldcat['units'],cat['units']) if u!=v]==['桥接器']
for key in ['constraints','recipes','task','static_checks']:
    assert oldcat[key]==cat[key],key
assert [i+1 for i,(a,b) in enumerate(zip(oldcat['sources'][0]['lines'],cat['sources'][0]['lines'])) if a!=b]==[24,59,63]
expected=copy.deepcopy(cat);expected['sources']=source_snapshot();expected.update(formal_projection(expected['sources']))
rules='\n'.join(expected['sources'][0]['lines']);units=unit_projection(rules,expected['constraints'],quantity)
expected['units']=[units[u['id']] for u in expected['units']];expected['recipes']=recipe_projection(rules)
assert dump(expected).encode()==(ROOT/'数据/正式静态目录.json').read_bytes()

refs=[];inputs=[]
changed_axes={'bridge.capacity','bridge.scheduling_scope','connection.bridge_first_contact','connection.bridge_tie','offline.direction_effect'}
def stripped(d):
    d=copy.deepcopy(d);d['catalog'].pop('sha256');d['parameters']['axis_registry'].pop('sha256')
    bridges={u['id'] for u in d['layout']['units'] if u['kind']=='桥接器'}
    for u in d['layout']['units']:
        if u['id'] in bridges:u['bridge_axes']=None
    for group in ['fixed','offline_mutable','fixedness_unproven']:
        for axis in changed_axes:d['parameters'][group].pop(axis,None)
    state=d['initial_state']['nonwarehouse'].get('value')
    if isinstance(state,dict) and 'semantic_context' in state:
        sem=state['semantic_context']
        sem['parameter_values']=[r for r in sem['parameter_values'] if r['axis'] not in changed_axes]
        sem['arbitration']['level_order']=[r for r in sem['arbitration']['level_order'] if r.split('|')[1] not in bridges]
        memory=state['logistics']['poll_memory']['value']
        memory['sides']=[r for r in memory['sides'] if r['unit'] not in bridges]
    return d

def ref(path,name,row):
    actual=(path.parent/row['path']).resolve()
    assert actual.is_file() and digest(actual)==row['sha256'],(path,name,actual)
    refs.append({'input':str(path.relative_to(ROOT)),'field':name,'resolved':str(actual),'sha256':row['sha256']})
for rel in sync['inputs']:
    path=ROOT/rel;d=load(path);old=load(OUT/'before'/rel)
    assert stripped(old)==stripped(d),rel
    ref(path,'catalog',d['catalog']);ref(path,'parameters.axis_registry',d['parameters']['axis_registry'])
    inputs.append(rel)
for path in [ROOT/'数据/样例/kernel_profile_v1参数赋值.json',ROOT/'数据/样例/分流器三路轮询-参数赋值.json']:
    d=load(path)
    for key in ['profile_source','configuration_source','axis_source']:ref(path,key,d[key])
sources=load(ROOT/'数据/候选B/来源清单.json')
assert all(digest(Path(r['path']))==r['sha256'] for r in sources)
assert len(inputs)==54 and len(refs)==114
assert len([r for r in inputs if r.startswith('数据/样例/')])==45

for file,headings in [('规格/规则覆盖表.md',['## 1. 游戏规则逐行','## 2. 求解任务逐行','## 3. 正式约束条目登记']),('数据/规则覆盖表.md',['## 《明日方舟：终末地》游戏规则.txt','## 求解任务.txt','## 正式约束'])]:
    text=(ROOT/file).read_text()
    for index in [0,1]:
        block=text.split(headings[index],1)[1].split('## ',1)[0]
        rows=[l for l in block.splitlines() if re.match(r'^\| \d+ \|',l)]
        original=(REPO/SOURCES[index]).read_text().splitlines()
        assert len(rows)==len(original),(file,index)
        for row,formal in zip(rows,original):
            assert row.split('|')[2].strip()==(formal.strip() or '（空行）'),(file,row,formal)
    block=text.split(headings[2],1)[1].split('## ',1)[0]
    rows=[l for l in block.splitlines() if (re.match(r'^\| \d+ \|',l) if file.startswith('规格') else '`constraints[' in l)]
    assert len(rows)==72
    if file.startswith('规格'):
        for i,(row,constraint) in enumerate(zip(rows,cat['constraints']),1):
            cols=[c.strip() for c in row.split('|')]
            assert cols[1]==str(i) and cols[2]==constraint['source_line'] and cols[3]=='约束·'+constraint['name'],row

protected={}
for relative in SOURCES+['游戏理解.txt','候选约束.txt','候选简化.txt','候选充分条件.txt']:
    p=REPO/relative
    original=subprocess.check_output(['git','show',(OUT/'initial-head.txt').read_text().strip()+':'+relative],cwd=REPO)
    assert original==p.read_bytes(),relative
    protected[relative]=digest(p)
assert {s:digest(REPO/s) for s in SOURCES}==load(OUT/'formal-sources.json')
cfg=load(ROOT/'规格/内核配置-v1.json');oldcfg=load(OUT/'before/规格/内核配置-v1.json')
for axis in ['transfer.partial_acceptance','gate.identity_recovery']:
    assert cfg['axes'][axis]==oldcfg['axes'][axis]
    get=lambda t:next(l for l in t.splitlines() if l.startswith(f'| `{axis}` |'))
    assert get((ROOT/'规格/受限模型声明.md').read_text())==get((OUT/'before/规格/受限模型声明.md').read_text())
before=(OUT/'before/规格/check_revision.py').read_text()
assert before.replace('内核维护/2026-09-22g/只读文件指纹.json','内核维护/2026-09-22h/只读文件指纹.json')==(ROOT/'规格/check_revision.py').read_text()

oldsha='b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c'
argv=['rg','--hidden','--no-ignore','-l','-0','-F',oldsha,'-g','!.git/**','-g','!**/target/**','-g','!**/__pycache__/**','.']
r=subprocess.run(argv,cwd=REPO,capture_output=True);assert r.returncode in (0,1)
hits=sorted(p.removeprefix('./') for p in r.stdout.decode().split('\0') if p)
unclassified=[p for p in hits if not p.startswith('求解器/内核维护/') and p!='求解器/规格/修订记录.md']
assert unclassified==[],unclassified
save('final-old-sha-inventory.json',{'argv':argv,'hits':hits,'unclassified':unclassified,'active_remaining':0})
check=subprocess.run(['git','diff','--check'],cwd=REPO,capture_output=True)
(OUT/'git-diff-check.log').write_bytes(check.stdout+check.stderr);assert check.returncode==0
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=REPO)
changed=difference(load(OUT/'initial-active.json'),active_snapshot())
assert not changed['deleted']
for name in ['混做粉碎机两下游-参考运行记录.json','分流器三路轮询-参考运行记录.json']:
    path='求解器/数据/样例/'+name
    assert digest(REPO/path)==load(OUT/'initial-active.json')[path]
audit={'status':'pass','catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'catalog_version':cat['version'],
    'catalog_changed_rule_lines':[24,59,63],'catalog_changed_units':['桥接器'],'constraints':72,
    'input_count':54,'sample_inputs':45,'fixture_inputs':9,'bridge_input_count':len(sync['bridge_inputs']),
    'reference_documents':56,'reference_fields':114,'references':refs,'candidate_sources':len(sources),
    'unrelated_input_fields_unchanged':True,'protected_files':protected,'configuration_dispositions':dict(Counter(r['disposition'] for r in cfg['axes'].values())),
    'coverage_tables':'114/16 source lines and 72 constraints agree','old_sha_active_remaining':0,
    'out_of_scope_items_unchanged':True,'reference_archives_unchanged':True,'changes':changed,'mismatches':[]}
save('audit.json',audit)
guard('audit-final-after')
print(dump({k:audit[k] for k in ['status','input_count','reference_fields','old_sha_active_remaining','mismatches']}))
