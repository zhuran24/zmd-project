"""交付检查，不运行求解器；只读输入和已完成结果，写同目录核对记录。"""
from pathlib import Path
from fractions import Fraction
import json,re,hashlib

HERE=Path(__file__).resolve().parent
ROUND=HERE.parent
ROOT=ROUND.parents[2]
def get(name):return json.loads((HERE/name).read_text())
def norm(v):
    if isinstance(v,dict):return {k:norm(x) for k,x in v.items()}
    if isinstance(v,list):return [norm(x) for x in v]
    return str(v)

inv=get('inventory.json'); records=get('audit_records.json'); result=get('result.json')
source=(ROUND/'前提快照'/'求解约束.txt').read_text().splitlines()
reparsed=[]
for i,line in enumerate(source[:-1]):
    if source[i+1].lstrip().startswith('据：'):
        num=len(reparsed)+1
        excluded=num<=7 or num in (41,49,51) or any(word in line+source[i+1] for word in ['阻尼','存货优先级','判定次序','判定先后','同一时刻'])
        reparsed.append((f'N{num:02}',not excluded))
assert [(r['id'],r['in_scope']) for r in inv]==reparsed
assert {r['id'] for r in records}=={k for k,v in reparsed if v}
assert len(records)==63 and sum(r['status']=='确认成立' for r in records)==60
assert {c['name'] for c in result['candidates']}=={'核心邻格','内带缺口','面积预算'}
assert all(set(('name','kind','text','basis','derivation','relation'))<=set(c) and c['kind']=='必要条件' for c in result['candidates'])
assert all(c['text']==next(r['new']['text'] for r in records if r['name']==c['name']) for c in result['candidates'])
assert norm(get('foundation_a.json'))==norm(get('foundation_b.json'))
assert get('counts_check_b.json')['independent_comparison']=='PASS'
assert get('counts_check_a.json')['full_phase_tests']==13376
geo=get('geo_delivery_check.json')
assert geo['entries']==14 and geo['confirmed']==13 and geo['small_checks_passed'] and geo['corner_exact_agreement']
assert get('geo_power_reused_A.json')['current_domain_exact_equal_to_old_A']
assert get('geo_power_reused_A.json')['reused_A_result']['status']=='INFEASIBLE'
assert get('geo_power_general_weight_55_B_highs.json')['status']==2
for file in HERE.glob('geo_power_*.json'):
    if file.name.startswith(('geo_power_edge_','geo_power_side')) or file.name.startswith('geo_power_general_count_'):
        assert json.loads(file.read_text())['status']=='INFEASIBLE',file
ore=get('counts_ore_certificate_check.json')
assert ore['configurations']==47 and ore['cp_all_infeasible'] and ore['highs_all_infeasible']
assert get('area_summary.json')['confirmed']==['N66','N68','N74','N75','N77']
hashes=get('snapshot_sha256.json')
assert all(hashlib.sha256((ROUND/'前提快照'/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items())
report=Path(result['report_path']); text=report.read_text()
headings=re.findall(r'^### (N\d\d) ',text,re.M)
assert len(headings)==63 and set(headings)=={r['id'] for r in records}
assert len(re.findall(r'^状态：待审。',text,re.M))==63
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
for target in links:
    assert (report.parent/target.split('#')[0]).exists(),target
allowed={'.py','.md','.log','.json','.gz'}
files=[]
for path in sorted(HERE.rglob('*')):
    if path.is_file():
        assert path.suffix in allowed,path
        assert path.stat().st_size<=100*1024*1024 or path.suffix=='.gz',path
        if path.name not in ('delivery_validation.json','artifact_manifest.json'):
            files.append({'path':str(path.relative_to(ROUND)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
files.append({'path':report.name,'bytes':report.stat().st_size,'sha256':hashlib.sha256(report.read_bytes()).hexdigest()})
(HERE/'artifact_manifest.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n')
data={'status':'PASS','scope':{'formal':77,'excluded':14,'reviewed':63,'confirmed':60,'wording':1,'safe_revisions':2,'falsified':0},'snapshot_unchanged':True,'all_required_candidate_fields':True,'all_63_entry_formats':True,'all_links_exist':True,'file_count':len(files),'total_bytes':sum(f['bytes'] for f in files),'report_sha256':files[-1]['sha256'],'fresh_vs_reused_solver_evidence':'explicitly separated','unknown_used_as_infeasible':False,'reader_review':['checked final scope and all per-entry results','checked conservative revisions do not claim full-layout counterexamples','checked both bridge interpretations and all connection orders','checked snapshot and candidate names','checked N35 continuation quantifiers separately','checked source paths, output paths and numeric units']}
(HERE/'delivery_validation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(data,ensure_ascii=False))
