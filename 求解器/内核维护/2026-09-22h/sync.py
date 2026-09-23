from helpers import *
from guard import REPO, SOURCES, HISTORY, digest, save, guard
import sys, copy, re, subprocess
from pathlib import Path
sys.path.insert(0,str(ROOT/'数据/工具'))
from formal_catalog import source_snapshot, formal_projection, recipe_projection, unit_projection, quantity, verify
sys.path.insert(0,str(ROOT/'数据/样例'))
import check_examples as checker
from runtime_example import make_poll_memory, profile_projection

OLD_SHA='b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c'
VERSION='2026-09-22-r25-bridge-bidirectional'
CATALOG=ROOT/'数据/正式静态目录.json'

def scan(label):
    argv=['rg','--hidden','--no-ignore','-l','-0','-F',OLD_SHA,'-g','!.git/**','-g','!**/target/**','-g','!**/__pycache__/**','.']
    r=subprocess.run(argv,cwd=REPO,capture_output=True)
    assert r.returncode in (0,1)
    paths=sorted(p.removeprefix('./') for p in r.stdout.decode().split('\0') if p)
    save(label+'-old-sha-inventory.json',{'argv':argv,'paths':paths})
    return paths

guard('sync-before')
scan('before')
cat=json.loads(CATALOG.read_text());original=json.loads((OUT/'before/数据/正式静态目录.json').read_text()) if (OUT/'before/数据/正式静态目录.json').exists() else copy.deepcopy(cat)
cat['version']=VERSION;cat['sources']=source_snapshot();cat.update(formal_projection(cat['sources']))
text='\n'.join(cat['sources'][0]['lines'])
cat['recipes']=recipe_projection(text)
units=unit_projection(text,cat['constraints'],quantity)
cat['units']=[units[u['id']] for u in cat['units']]
verify(cat);write(CATALOG,dump(cat))
sha=digest(CATALOG)
config=json.loads((ROOT/'规格/内核配置-v1.json').read_text())
axes=['bridge.capacity','bridge.scheduling_scope','connection.bridge_first_contact','connection.bridge_tie','offline.direction_effect']
registry=ROOT/'规格/选择点参数轴.md'
inputs=[];bridge_inputs=[]
for base in [ROOT/'数据/样例',ROOT/'crates/kernel/tests/fixtures']:
    for p in sorted(base.rglob('*.json')):
        d=json.loads(p.read_text())
        if not isinstance(d,dict) or d.get('schema') not in ('kernel-input-v2','kernel-input-v3'):continue
        assert (p.parent/d['catalog']['path']).resolve()==CATALOG
        d['catalog']['sha256']=sha
        d['parameters']['axis_registry']['sha256']=digest(registry)
        for name in axes:
            decision=None
            for g in ['fixed','offline_mutable','fixedness_unproven']:
                if name in d['parameters'][g]:decision=d['parameters'][g].pop(name)
            assert decision is not None
            r=config['axes'][name];g='fixed' if r['lifetime']=='F' else 'fixedness_unproven'
            # Already explicit profiles become the new explicit rule; structural unresolved remains unresolved only for offline.
            if r['disposition']=='已定' or decision['status']!='unresolved':
                decision.update(status='specified',value=r['value'],basis=['规则L24、L59、L63；现行内核配置 r25'])
            d['parameters'][g][name]=decision
        bridge_ids={u['id'] for u in d['layout']['units'] if u['kind']=='桥接器'}
        for u in d['layout']['units']:
            u['bridge_axes']=None
        if bridge_ids:
            channels=checker.geometry(d,cat)[3]
            assert sorted(channels,key=lambda c:c['id'])==sorted(d['layout']['physical_channels'],key=lambda c:c['id']),p
            bridge_inputs.append(str(p.relative_to(ROOT)))
        state=d['initial_state']['nonwarehouse'].get('value')
        if isinstance(state,dict) and 'semantic_context' in state:
            state['semantic_context']['parameter_values']=[{'axis':a,'value':v,'lifetime':l}
                for g,l in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')]
                for a,v in d['parameters'][g].items()]
            if bridge_ids:
                # Build independent axis labels before computing current eligible levels.
                from polling_reference import build_sides
                k,u,pmap,ch,_,_=checker.geometry(d,cat)
                sides=build_sides(d,k,u,pmap,ch)['sides']
                old=state['semantic_context']['arbitration']['level_order']
                new=[l['id'] for s in sides for l in s['levels']]
                # Preserve non-bridge explicit relative order; insert split bridge labels at old label positions.
                order=[]
                for label in old:
                    if label in new:
                        order.append(label)
                    elif label.split('|')[1] in bridge_ids:
                        order.extend(x for x in new if x not in order and x.replace('|vertical|','|').replace('|horizontal|','|')==label)
                    else:order.append(label)
                assert set(order)==set(new),p
                state['semantic_context']['arbitration']['level_order']=order
                fresh=make_poll_memory(d,cat,state,only_units=bridge_ids)
                old_sides=state['logistics']['poll_memory']['value']['sides']
                state['logistics']['poll_memory']['value']['sides']=[s for s in old_sides if s['unit'] not in bridge_ids]+[s for s in fresh['sides'] if s['unit'] in bridge_ids]
        write(p,dump(d));inputs.append(str(p.relative_to(ROOT)))

for name,source in [('kernel_profile_v1参数赋值.json','混做粉碎机两下游.json'),('分流器三路轮询-参数赋值.json','分流器三路轮询.json')]:
    d=json.loads((ROOT/'数据/样例'/source).read_text())
    write(ROOT/'数据/样例'/name,dump(profile_projection(d)))
p=ROOT/'数据/样例/runtime_example.py'
t=re.sub(r"SUPPORTED_PROFILE_SHA256 = '[0-9a-f]+'",f"SUPPORTED_PROFILE_SHA256 = '{digest(ROOT/'规格/内核配置-v1.json')}'",p.read_text());write(p,t)
p=ROOT/'数据/样例/check_examples.py';t=p.read_text().replace(original['sources'][0]['sha256'],cat['sources'][0]['sha256']);write(p,t)
p=ROOT/'数据/候选B/来源清单.json';rows=json.loads(p.read_text())
for r in rows:r['sha256']=digest(Path(r['path']))
write(p,dump(rows))
for file in ['数据/候选B/校验报告.md','数据/候选B/验证记录.md']:
    p=ROOT/file;write(p,p.read_text().replace(original['version'],VERSION))
save('只读文件指纹.json',{str(REPO/p):digest(REPO/p) for p in SOURCES+['候选约束.txt']})
p=ROOT/'规格/check_revision.py';write(p,p.read_text().replace('内核维护/2026-09-22g/只读文件指纹.json','内核维护/2026-09-22h/只读文件指纹.json'))
save('sync-summary.json',{'catalog_version':VERSION,'catalog_sha256':sha,'inputs':inputs,'bridge_inputs':bridge_inputs,'sources':{s['path']:s['sha256'] for s in cat['sources']}})
remaining=scan('after')
active=[p for p in remaining if p.startswith(('求解器/数据/样例/','求解器/crates/kernel/tests/fixtures/'))]
save('active-old-sha.json',active)
guard('sync-after')
print(dump({'sha256':sha,'inputs':len(inputs),'bridge_inputs':bridge_inputs,'active_old_sha':active}))
