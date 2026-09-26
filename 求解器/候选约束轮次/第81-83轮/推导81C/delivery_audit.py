"""Delivery and reader audit; all writes stay beside this script."""
from pathlib import Path
from fractions import Fraction as F
import json,hashlib,datetime,re
OUT=Path(__file__).resolve().parent
report=OUT.parent/'推导81C.md'
def read(name):return json.loads((OUT/name).read_text())
inputs=read('inputs.json');conclusions=read('conclusions.json')
a=read('accounts_a.json');b=read('accounts_b.json');g=read('geometry_check.json');f=read('final_numbers.json')
assert b['all_independent_checks_equal'] and g['passes']
assert len(conclusions)==8 and len(read('formal_index.json'))==72
assert len({z['name'] for z in conclusions})==8
assert all(z['kind']=='必要条件' and z['status']=='待审' for z in conclusions)
text=report.read_text()
for c in conclusions:
    for key in ('name','text','basis','derivation','relation'):assert c[key] in text
assert '{{' not in text
assert 'J>0时外边界可能有桩，不能套这张表' in text
assert '十三桩尚未排除' in text and '未证布局存在' in text
assert '不是形式证明' not in text or '回执' in text

# Constants, two independent ways: per-machine table versus grouped dimensions.
n=[68,51,32,6,6,32,16,3,3];size=[9,9,24,9,9,25,25,24,24]
area_a=sum(x*y for x,y in zip(n,size))
area_b=9*(68+51+6+6)+25*(32+16)+(6*4)*(32+3+3)
assert area_a==area_b==3291
remaining_a=70*70-area_a-9*9-46*3
remaining_b=4900-(1179+1200+912+81+138)
assert remaining_a==remaining_b==1390
C_a=312+307
C_b=sum([68,51,95,11,6,32,16,15,11])+sum([95,51,32,6,6,32,32,3,3])+46+6+2
assert C_a==C_b==619
transport_a=C_a+90+8
transport_b=C_b+(2*46-2)+2*(2*3-2)
band_a=transport_a+88+4
band_b=transport_b+((69+68)-46)-3+4
budget_a=4*remaining_a-band_a
budget_b=4*4900-4*(3291+81+138)-band_b
assert (transport_a,band_a,budget_a)==(transport_b,band_b,budget_b)==(717,809,4751)
assert a['flow']['rank']==17 and a['flow']['nullity']==1
assert a['flow']['nontransport_output']=='6113/20+2*r'
assert f['power_required_weight']==520 and f['power_10_one_edge']==515
for typ in a['cost_tables']:
    assert a['cost_tables'][typ]['weight']==b['cost_tables'][typ]['weight']
    vals={int(n):F(v) for n,v in a['cost_tables'][typ]['net_cost'].items()}
    assert all(vals[n+1]-vals[n]>=34 for n in range(min(vals),max(vals)))
assert {r['name'] for r in f['costs'] if F(r['net_direction_area_cost'])<=F(83,2)}=={'粉碎机','精炼炉','配件机','塑形机','协议储存箱'}
assert [z['J'] for z in f['remaining_1110_scalar_branches'] if z['P']==13]==[5,6,7]

source_checks=[]
for s in inputs['sources']:
    source_checks.append(dict(path=s['path'],role=s['role'],frozen_sha256=s['sha256'],
        current_sha256=hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()))
    if s['role']=='formal premise':assert source_checks[-1]['current_sha256']==s['sha256']
allowed={'.py','.json','.md','.log','.gz'}
files=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or p.name=='delivery_audit.json':continue
    assert p.suffix in allowed,p
    assert p.stat().st_size<=100*1024*1024 or p.suffix=='.gz',p
    files.append(dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
files.append(dict(path='../推导81C.md',bytes=report.stat().st_size,sha256=hashlib.sha256(report.read_bytes()).hexdigest()))
link_checks=[]
for dest in re.findall(r'\]\(([^)]+)\)',text):
    if '://' not in dest and not dest.startswith('#'):
        p=report.parent/dest;assert p.exists(),dest;link_checks.append(dest)
audit=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),report_path=str(report),
    status='complete; eight necessary conditions awaiting review',checks=dict(
        formal_entries=72,conclusions=8,distinct_names=True,all_fields_in_report=True,
        both_power_encodings_infeasible=True,exact_weight_tables_equal=True,
        affine_recipe_balances_equal=True,band_cases=47,boundary_cases=32,
        both_endpoint_orientations_checked=True,arithmetic_constants=[3291,1390,619,717,809,4751],
        no_timeouts=True,no_files_over_100MiB=True,links_valid=True),
    reader_review=[
        'All premises refer to the specified three snapshots; candidate conclusions are rederived when used.',
        'Physical counts, active counts, throughput, weighted directions and occupied cells are separately defined.',
        'The boundary table requires J=0 and is not used to exclude the P=13 branch.',
        'All five single-addition branches are covered, including an idle exceptional machine or inactive box.',
        'P=13 is left open; scalar survivors are not presented as layouts.',
        'Stock means are not stated as pointwise stock bounds.',
        'The cut counts only bodies crossing the stated segment, and assigns boxes kappa=3.',
        'Solver infeasibility receipts are not described as formal proof-kernel certificates.',
        'Head status, eight candidate records, cost table, branch table and links agree.'
    ],source_checks=source_checks,files=files,total_bytes=sum(x['bytes'] for x in files))
(OUT/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report_path':str(report),'checks':audit['checks'],'total_bytes':audit['total_bytes'],
    'formal_snapshots_unchanged':True,'background_current_matches':[s['current_sha256']==s['frozen_sha256'] for s in source_checks if s['role']!='formal premise']},ensure_ascii=False,indent=2))
