"""Check all completed receipts, record area cases and immutable input/output hashes."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import json,hashlib
out=Path(__file__).resolve().parent
def read(name):return json.loads((out/name).read_text())
for prefix in ('b','c'):
    records=read(f'power_{prefix}.json')
    assert len(records)==4 and all(r['status']=='INFEASIBLE' for r in records)
for edge in (False,True):
    assert read(f'power_a_domain_{edge}.json')==read(f'power_b_domain_{edge}.json')==read(f'power_c_domain_{edge}.json')
a=read('scope_a.json');b=read('scope_b.json')
assert a['cases']==b['cases'] and a['maximum']==b['maximum']==91
assert a['incompatible_fixed_machine']==b['incompatible_fixed_machine']==1042
tables=read('arithmetic_a.json')['weight_tables']
for n in range(32,49):assert F(tables['研磨机'][str(n)])==(F(379-8*n,2) if n<=47 else 0)
for n in range(6,13):assert F(tables['塑形机'][str(n)])==max(0,22-2*n)
for n,c in enumerate([24,18,10,6,2,0],3):assert F(tables['封装机'][str(n)])==c
for n,c in enumerate([14,6,2,0],3):assert F(tables['灌装机'][str(n)])==c
scalar=[]
for p in range(10,348):
    for j in range(p+1):
        if 23*p-10*j<217 or 54*p-25*j<520:continue
        scalar.append([p,j,str((F(4751)-16*p+2*j-F(287,2))/4)])
maxextra=max(F(s[2]) for s in scalar)
assert maxextra==F(8895,8) # 1111.875, before the 1110 boundary exclusion
assert str(maxextra)==read('arithmetic_b.json')['extra_global_area_upper']
extra1110=[]
for kind,increment in [('粉碎机',36),('精炼炉',36),('配件机',36),('协议储存箱',36),('塑形机',34),('研磨机',92),('封装机',88),('灌装机',88),('种植机',100),('采种机',100)]:
    allowed=[]
    for p,j,_ in scalar:
        allowance=F(4751-4440-16*p+2*j)-F(219,2)-increment
        if allowance>=0:allowed.append([p,j,str(allowance)])
    extra1110.append({'kind':kind,'increment':increment,'remaining_X0_Y0':allowed})
assert all((r['remaining_X0_Y0']==[[10,0,'15/2']] if r['kind']=='塑形机' else r['remaining_X0_Y0']==[[10,0,'11/2']] if r['increment']==36 else r['remaining_X0_Y0']==[]) for r in extra1110)
noextra=[(p,j,199-16*p+2*j) for p,j,_ in scalar if 199-16*p+2*j>=0]
assert max(p for p,j,xy in noextra)==13
assert min(j for p,j,xy in noextra if p==13)==5
assert next(xy for p,j,xy in noextra if p==12 and j==0)==7
unchanged={name:hashlib.sha256((out.parent/'前提快照'/name).read_bytes()).hexdigest()==digest for name,digest in read('arithmetic_a.json')['snapshot_sha256'].items()}
assert all(unchanged.values())
result={'completed_power_encodings':['power_b.py','power_c.py'],'power_domain_options':{'ordinary':len(read('power_b_domain_False.json')),'edge':len(read('power_b_domain_True.json'))},
 'power_CP_SAT_attempt':read('power_a.json'),'scope_cases_by_height':dict(Counter(row[2] for row in a['cases'])),'scope_total_completed':len(a['cases']),'scope_incompatible_fixed_machine':a['incompatible_fixed_machine'],
 'extra_machine_global_area_fraction':str(maxextra),'extra_1110_cases':extra1110,'no_extra_1110_scalar':noextra,'snapshot_hashes_unchanged':unchanged}
(out/'final_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'}
manifest['../复核93B.md']=hashlib.sha256((out.parent/'复核93B.md').read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'all_checks':'PASS','extra_A_upper':str(maxextra),'scope_completed':len(a['cases']),'scope_incompatible':a['incompatible_fixed_machine'],'snapshots_unchanged':all(unchanged.values())}))
