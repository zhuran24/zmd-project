"""复核证据核验。只向本目录写 JSON；不导入推导席代码。"""
from pathlib import Path
import hashlib,json,subprocess,sys,datetime,ast

HERE=Path(__file__).resolve().parent
def read(name):return json.loads((HERE/name).read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    for name in ['numbers_a.py','numbers_b.py']:
        subprocess.run([sys.executable,'-B',str(HERE/name)],check=True,capture_output=True,text=True)
    a=read('numbers_a.json');b=read('numbers_b.json')
    assert a==b,{k:[a[k],b.get(k)] for k in a if a[k]!=b.get(k)}
    compare={'equal':True,'fields':len(a),'keys_compared':list(a)}
    (HERE/'numbers_comparison.json').write_text(json.dumps(compare,ensure_ascii=False,indent=2)+'\n')
    fac=[read(f'factory_{seed}.json') for seed in range(108001,108005)]
    for r in fac:
        assert r['violations']==0 and r['period_steps']==480
        assert r['period_deliveries']=={'高容谷地电池':36,'精选荞愈胶囊':33}
        assert r['mine_per_route']==60 and r['shared_zero_reject_routes']==46
        assert r['closed_state_replayed'] and not r['is_layout']
    local=read('local_check.json');supply=read('supply_check.json');startup=read('startup_check.json')
    assert local['layers']['words']==2**13-2
    assert local['layers']['component_roots']==sum(2**n*(3*n+1)//4 for n in range(1,13))
    assert local['states']['transition_cases']==2*sum(8**n for n in range(1,6))
    assert local['states']['source_variants']==4*sum(8**n for n in range(1,6))
    assert local['crossing']['negative_whole_unit_first_difference']==0
    assert local['crossing']['wrong_provenance_detected']
    assert supply['event_closure']['deadline_violations']==0
    assert supply['physical_trials']['exact_head_recurrence_violations']==0
    for r in startup:
        assert r['startup_reached'] and r['violations']==0
        assert r['manual_cache_edits']==r['manual_transport_insertions']==0
    for p in HERE.glob('*.py'):ast.parse(p.read_text(),filename=p.name)
    # 收集实际读到的材料，不读本轮另一席复核或推导席脚本。
    rounddir=HERE.parent;root=rounddir.parent
    inputs=[rounddir/'推导107S2B.md',rounddir/'临时规则.md',
            *sorted((rounddir/'前提快照').glob('*.txt')),
            root/'第98-100轮/推导98S2.md',root/'三审-第92-106轮/三审报告.md',
            root/'第95-97轮/推导95M.md',root/'第92-94轮/推导92D.md']
    input_info=[{'path':str(p),'sha256':digest(p),'lines':len(p.read_text().splitlines())} for p in inputs]
    (HERE/'inputs.json').write_text(json.dumps(input_info,ensure_ascii=False,indent=2)+'\n')
    stats={'factory_cases':len(fac),'factory_steps':sum(r['steps_compared'] for r in fac),
           'factory_offline_rebuilds':sum(r['offline_rebuilds'] for r in fac),
           'inverse_checks_blocked':sum(r['inverse_checks_blocked'] for r in fac),
           'startup_cases':len(startup),'startup_steps':sum(r['steps_compared'] for r in startup),
           'startup_preparation_steps':sum(r['preparation_steps'] for r in startup),
           'startup_offline_rebuilds':sum(r['offline_rebuilds'] for r in startup)}
    res={'status':'passed','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'numeric_encodings_equal':True,'numeric_fields_compared':len(a),'stats':stats,
         'python_sources':{p.name:digest(p) for p in sorted(HERE.glob('*.py'))},
         'result_files':{p.name:digest(p) for p in sorted(HERE.glob('*.json')) if p.name not in ('validation.json','delivery_check.json')},
         'no_geometric_layout_certified':True}
    (HERE/'validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':res['status'],'stats':stats,'numeric_fields_compared':len(a)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
