#!/usr/bin/env python3
"""Delivery/schema/provenance verification; does not replace any proof."""
import ast
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'推导98S2.md'
ROOT=HERE.parents[3]

def get(name): return json.loads((HERE/name).read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

reply=get('reply.json')
assert set(reply)>={'report_path','candidates','summary'}
assert Path(reply['report_path'])==REPORT
assert reply['candidates']==get('candidates.json') and len(reply['candidates'])==1
for candidate in reply['candidates']:
    assert set(candidate)=={'name','kind','text','basis','derivation','relation'}
    assert candidate['kind'] in ('必要条件','简化','充分条件')
    assert all(isinstance(v,str) and v for v in candidate.values())
    for file in ('候选充分条件.txt','求解充分条件.txt'):
        assert candidate['name'] not in (ROOT/file).read_text()

text=REPORT.read_text()
assert reply['candidates'][0]['name'] in text
assert '多9台制造单位、192格机身' in text and '至多737格' in text
assert 'S16' not in text and 'S15' not in text and 'S14' not in text
assert '没有满足这一更强要求' in text and '采种单元内部允许拒收' in text
links=[]
for link in re.findall(r'\]\(([^)]+)\)',text):
    if '://' in link or link.startswith('#'): continue
    p=(REPORT.parent/link.split('#')[0]).resolve()
    assert p.exists() or (p.parent==HERE and p.name in ('validation.json','artifact_manifest.json')),link
    links.append(link)
assert get('arithmetic_a.json')==get('arithmetic_b.json')
a=get('arithmetic_a.json')['230']
assert (a['total'],a['routes'],a['body'],a['E'],a['extra_body'])==(230,325,3567,276,192)
assert a['pure_belt_rectangle']==[737,11,67]
assert a['general_rectangle']==[841,29,29]

expected_sand=[['铁研磨0','铁研磨1','源研磨0'],['源研磨1','源研磨2'],
               ['铁研磨2','铁研磨3','源研磨3'],['源研磨4','源研磨5'],
               ['铁研磨4','铁研磨5','源研磨6'],['源研磨7','源研磨8'],
               ['铁研磨6','铁研磨7','铁研磨8'],['铁研磨9','荞研磨0','荞研磨1'],
               ['铁研磨10','铁研磨11','铁研磨12'],['铁研磨13','荞研磨2','荞研磨3'],
               ['铁研磨14','铁研磨15','荞研磨4'],['铁研磨16'],['荞研磨5']]
primary=[]
for seed in (98040,98041,98042):
    c=get(f'cycle_{seed}.json'); g=get(f'graph_{seed}.json')
    assert c['status']=='closed_cycle' and c['period_steps']==480
    assert c['direct_state_equality_a'] and c['direct_state_equality_b']
    assert c['all_52_full'] and c['product_rates_pass']
    assert c['delivery']=={'高容谷地电池':36,'精选荞愈胶囊':33}
    assert c['ore_counts']==[60]*52 and c['critical_shared_refusals']==0
    assert c['critical_shared_routes']==46 and c['full_service_invariant_violations']==[]
    assert c['parameters']['initial']=='prepared' and c['parameters']['separate'] and not c['parameters']['core_mix']
    assert c['machine_count']==230 and c['route_count']==325
    for i,targets in enumerate(expected_sand):
        assert sorted(r['to'] for r in g['routes'] if r['from']==f'砂叶粉碎{i}')==sorted(targets)
    core=[r for r in g['routes'] if r['from']=='协议核心取货']
    assert len(core)==6 and all(r['item']=='源矿' for r in core)
    assert {r['to'] for r in core}=={f'源粉碎{i}' for i in range(6)}
    slow=[r for r in g['routes'] if r['to']=='灌装3']
    assert len(slow)==2 and slow[0]['length']==slow[1]['length']
    primary.append({k:c[k] for k in ('machine_count','route_count','cross_checked_steps','period_steps','critical_shared_refusals','all_refusals')})
assert sum(x['cross_checked_steps'] for x in primary)==62984
assert get('cycle_98042.json')['parameters']['history']=='keep'
common=get('common_rounds.json'); offset=get('offset_rounds.json')
assert common['all_cross_equal'] and offset['all_cross_equal']
assert common['case_count']==offset['case_count']==120
assert common['steps']==293972 and offset['steps']==293441
for c in offset['cases']:
    assert c['latest_fill_delay']<=c['outlets']+c['spread']<8
startup=get('startup_check.json')
assert startup['all_pass'] and startup['independent_step_engines_equal'] and startup['total_steps']==25303
assert all(c['rounds']==3 and c['cache_write_operations']==0 and c['within_proved_feedstock_budget'] for c in startup['cases'])
budget=get('startup_budget.json')
assert budget['independent_integer_recipe_expansion']=={'蓝铁矿':256352,'源矿':39858,'砂叶':53615,'砂叶种子':12187,'荞花':23508,'荞花种子':7836}
assert budget['largest_per_item_quota']==36622
unchanged=[]; changed=[]
changes={x['path']:x for x in get('input_changes.json')}
for entry in get('inputs.json'):
    p=Path(entry['path'])
    if sha(p)==entry['sha256']: unchanged.append(str(p))
    else:
        known=changes[str(p)]
        assert entry['sha256']==known['initial_sha256'] and sha(p)==known['current_sha256']
        assert sha(HERE/'临时规则-进入时.md')==known['initial_sha256']
        assert sha(HERE/'临时规则-交付时.md')==known['current_sha256']
        changed.append(known)
for p in HERE.glob('*.py'): ast.parse(p.read_text(),filename=str(p))
all_files=list(HERE.iterdir())
assert all(p.is_file() and p.suffix in ('.py','.log','.json','.md') and p.stat().st_size<100*1024*1024 for p in all_files)
cycles=[get(p.name) for p in HERE.glob('cycle_*.json')]
assert all(c['all_52_full'] and c['product_rates_pass'] for c in cycles)
validation={'status':'pass','candidate_count':1,'primary_cycles':primary,'all_factory_cases':len(cycles),
            'all_factory_cross_steps':sum(c['cross_checked_steps'] for c in cycles),
            'linked_paths_checked':len(links),'protected_input_hashes_unchanged':len(unchanged),
            'concurrent_input_changes_covered':changed,
            'python_files_parsed':len(list(HERE.glob('*.py'))),'allowed_file_types_only':True,
            'literal_all_shared_no_refusal_claimed':False,'geometry_certificate':False,
            'formal_L':0,'formal_U':1110}
(HERE/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False),flush=True)
manifest={'report':{'path':str(REPORT),'sha256':sha(REPORT)},'artifacts':[
    {'name':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='artifact_manifest.json']}
(HERE/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
assert all((REPORT.parent/link.split('#')[0]).resolve().exists() for link in links)
