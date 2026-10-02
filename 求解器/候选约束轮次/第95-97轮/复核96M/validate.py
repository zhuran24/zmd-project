"""Cross-check independent outputs, then compare with submitted certificates.

Only JSON data is read from the deriving seat; none of its code is imported.
"""
from pathlib import Path
from fractions import Fraction
import json,hashlib
OUT=Path(__file__).resolve().parent;SUB=OUT.parent/'推导95M'
def read(p):return json.loads(p.read_text())
a=read(OUT/'arithmetic_a.json');b=read(OUT/'arithmetic_b.json')
keys=['machine_area','total_machines','input_ports','output_ports','interfaces','single_cost_twice','weights','omega',
      'fixed1110_pj','factors','outer','grade','startup_loss','startup_need','switch','increment_area_bound']
for key in keys:assert a[key]==b[key],(key,a[key],b[key])
assert list(a['counts'].values())==b['counts']
geometry={}
for name in ('corner','scope'):
    ca=read(OUT/(name+'_a.json'));cb=read(OUT/(name+'_b.json'))
    da={tuple(r['key']):(r.get('value'),r['d']) for r in ca['rows']}
    db={tuple(r['key']):(r.get('value'),r['d']) for r in cb['rows']}
    assert da==db
    cert=read(SUB/(name+'_a.json'))
    if name=='corner':
        submitted={(r['left_gap'],r['bottom_gap'],r['mode']):(r['bound'],0) for r in cert['cases']}
    else:
        submitted={(l,d,m,b,h):(value,overlap) for l,d,h,b,m,value,overlap,total in cert['cases']}
    assert da.keys()==submitted.keys()
    differences=[]
    for key,value in da.items():
        if value!=submitted[key]:
            # The audit keeps the second shaper inlet on the same usable edge.
            # At gap 3 the lower edge cannot carry steel; the submission used
            # a looser existence test, retaining one physically empty branch.
            assert name=='scope' and key==(3,0,2,5,6) and value==(None,2) and submitted[key]==(88,2)
            differences.append({'key':key,'audit':value,'submission':submitted[key],
                                'reason':'Upper shaper second inlet lies in the empty rectangle; lower edge has no steel approach.'})
    assert ca['fixed_conflicts']==cb['fixed_conflicts']
    # Directly recheck each CP-SAT selected machine certificate for overlap.
    for row in ca['rows']:
        if row['status']=='INFEASIBLE':continue
        used=set()
        for x,y in row.get('selected',[]):
            body={(i,j) for i in range(x,x+3) for j in range(y,y+3)}
            assert not used&body;used|=body
        assert row['value']==row['bound']
    geometry[name]={'checked_rows':len(da),'fixed_conflicts':ca['fixed_conflicts'],
                    'max':ca['max'],'matches_submission_except_safe_strengthening':True,'differences':differences,
                    'optimal':sum(r['status']=='OPTIMAL' for r in ca['rows']),
                    'infeasible':sum(r['status']=='INFEASIBLE' for r in ca['rows'])}
dyn=read(OUT/'dynamics.json');subdyn=read(SUB/'core_checks.json')
submitted={(r['n'],r['accept_mod']):(r['period_steps'],r['out'],r['occupied_cell_steps'],r['rate']) for r in subdyn['capacity']}
local={(r['n'],r['mod']):(r['K'],r['Q'],r['H'],r['rate']) for r in dyn['capacity']}
assert local==submitted
old_start=read(SUB/'startup_checks.json')['unrepaired'];u=dyn['unrepaired']
assert u['first_C_nonempty_steps']==old_start['first_C_nonempty_after_steps']
assert u['first_C_full_steps']==old_start['first_C_full_after_steps']
ss=old_start['stationary_inventory'];s=u['state6000']
assert s['stock']==ss['stock'] and s['out']==ss['output']
assert s['sent']==ss['sent'] and s['arr']==ss['arrivals'] and s['sink']==ss['sink'] and u['phi2']==ss['phi2']
result={'arithmetic_keys_matched':keys,'geometry':geometry,'capacity_rows_matched':len(local),
        'startup_submitted_numbers_matched':True,'startup_independent_cases':len(dyn['prepared']),
        'switch':dyn['switch'],'propagation':{k:v for k,v in read(OUT/'propagation.json').items() if k!='cases'},
        'order':{k:v for k,v in read(OUT/'order.json').items() if k not in ('triangle_formation','negative_shared_machine_sources')},
        'local_geometry':read(OUT/'local_geometry_check.json')}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
