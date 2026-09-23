"""Input fingerprints, independent geometry cross-checks and failure injection."""
from geometry74 import *
from certificates74 import local_columns,exact_check
from model74 import get_units
import hashlib,copy,re,argparse

def fingerprint(p):return dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def manifest():
    paths=[ROOT/f for f in ('《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt')]
    for rel in ['第60-62轮/复核61.md','第60-62轮/复核62.md','第69-71轮/推导69.md','第69-71轮/复核70.md','第69-71轮/复核71.md',
                '第72-74轮/推导72.md','第66-68轮/推导66/power_certificates.json',
                '第69-71轮/推导69/wall0_certificate.json','第69-71轮/推导69/supply_strip_certificates.json',
                '第69-71轮/推导69/new_edge_local_certificate.json','第69-71轮/推导69/local_power.py',
                '第69-71轮/推导69/supply_scan.py']:
        paths.append(ROUNDS/rel)
    for file in ('cp72.py','mip72.py','witness185.json','cp_cap184.json','mip_J0_cap184.json','mip_J1_cap184.json',
                 'global_groups_cp.json','global_groups_cp_linear.json','global_groups_mip.json','global_J0.json','global_J1.json'):
        paths.append(ROUNDS/'第72-74轮/推导72'/file)
    return {str(p.relative_to(ROOT)):fingerprint(p) for p in paths}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args()
    current=manifest();expected=['6e64e3903a65536c530b363c9f3aef8c1bb2a1c1193e866799125dd047159924',
        '1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac',
        '0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f']
    assert [current[p]['sha256'] for p in ('《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt')]==expected
    if args.final:
        assert current==json.loads((OUT/'input_manifest.json').read_text())
        report=(OUT.parent/'复核74.md').read_text();links=re.findall(r'\]\(([^)]+)\)',report)
        for link in links:
            if '://' not in link and (OUT.parent/link)!=OUT/'delivery_audit.json':
                assert (OUT.parent/link).exists(),link
        outcomes={p:json.loads((OUT/p).read_text())['status'] for p in ['highs_J0_cap184.json','highs_J1_cap184.json','replay185.json']}
        assert list(outcomes.values())==[2,2,0]
        for p in ('highs_J0_cap184.json','highs_J1_cap184.json','replay185.json','cp_cap184.json'):
            if (OUT/p).exists():
                data=json.loads((OUT/p).read_text());assert data['source_sha256']==fingerprint(OUT/'model74.py')['sha256']
        dump('delivery_audit.json',dict(input_unchanged=True,links=len(links),outcomes=outcomes,
             reader_review=True,verdicts={'十七位置十桩边段下界':'未否证','共同格组供电并集界':'未否证'},
             outputs={p.name:fingerprint(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ('delivery_audit.json','delivery.log')},
             report=fingerprint(OUT.parent/'复核74.md')))
        assert all('://' in link or (OUT.parent/link).exists() for link in links)
        print('final audit passed');return
    dump('input_manifest.json',current)
    all_poles=json.loads((OUT/'capacities.json').read_text());centercount=0
    for d in all_poles:
        px,py=d['p'];formula=set()
        for x in range(2,69):
            if x+1<px-5 or x-1>px+6:continue
            for y in range(2,69):
                if y+1<py-5 or y-1>py+6:continue
                if x+1>=49 and y+1>=17:continue
                if x-1<=px+1 and x+1>=px and y-1<=py+1 and y+1>=py:continue
                formula.add((x,y))
        assert formula==centers((px,py));centercount+=len(formula)
    lemma_checks=0
    for kind,w,h,axis in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                # A powered body cell selected without any 3x3 assumption.
                tx=max(x,0);ty=max(y,0)
                cx=max(x+1,min(tx,x+w-2));cy=max(y+1,min(ty,y+h-2))
                small=rect(cx-1,cy-1,3,3)
                assert small<=rect(x,y,w,h) and (tx,ty) in small and 0<=tx<12 and 0<=ty<12
                lemma_checks+=1
    wall=json.loads((ROUNDS/'第69-71轮/推导69/wall0_certificate.json').read_text());cols=local_columns()
    mutations=[]
    bad=copy.deepcopy(wall);bad['integer_upper']=12
    mutations.append(bad);bad=copy.deepcopy(wall);bad['rows'].pop(0);mutations.append(bad)
    for bad in mutations:
        try:exact_check(bad,cols)
        except AssertionError:pass
        else:raise AssertionError('corrupt certificate accepted')
    units=get_units();full=get_units(False)
    assert (len(units),len(full))==(1945,3970)
    assert (sum(WEIGHT.values()),len(WEIGHT))==(138,136)
    dump('geometry_audit.json',dict(poles=len(all_poles),centers=centercount,small_block_cases=lemma_checks,
         projected_options=len(units),full_options=len(full),machines_and_cores=sum(u['kind']!='p' for u in units),
         projected_poles=sum(u['kind']=='p' for u in units),removed_poles=len(full)-len(units),
         weighted_cells=138,physical_cells=136,double_cells=[c for c,v in WEIGHT.items() if v==2],certificate_mutations_rejected=2))
    print('input and geometry audit passed')

if __name__=='__main__':main()
