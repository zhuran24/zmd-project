from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,re
OUT=Path(__file__).resolve().parent;REPORT=OUT.parent/'复核96M.md'
names=['分叉分支','取货分级','来源定序','面积预算','内带缺口','专用进路下缓存格不空的传递',
       '分流先判的首段带容量','研磨单路换主料步数余量','无分流网络的判定先后无关','全厂专用进路接法的调试办法']
reasons=['重建与数层量词符合临时规则。','单位重建可反转等层级序。','限定集合后实际周期收支成立。',
         '面积常数和增配排除独立复算成立。','近边方向重计有同分支补偿。',
         '纯带、正确物品及单出口前提足够。','完整元件占格步数上下界成立。',
         '九步间隔及周期余量计数成立。','所列结构子类内动作可交换。','关机准备可执行，终点Φ正确。']
result={'report_path':str(REPORT),'status':'完成：10条未否证',
        'verdicts':[{'name':n,'verdict':'未否证','reason':r,'revised_text':''} for n,r in zip(names,reasons)]}
(OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert len(result['verdicts'])==10 and [v['name'] for v in result['verdicts']]==names
frozen=json.loads((OUT/'inputs.json').read_text())
for item in frozen['files']:
    assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
python_files=list(OUT.glob('*.py'))
for p in python_files:ast.parse(p.read_text(),filename=str(p))
validation=json.loads((OUT/'validation.json').read_text())
assert validation['geometry']['corner']['checked_rows']==135
assert validation['geometry']['scope']['optimal']==15696
assert validation['geometry']['scope']['infeasible']==1
assert validation['capacity_rows_matched']==24
assert validation['order']['compared_transitions']==294912
assert validation['propagation']['compared_steps']==288000
assert validation['local_geometry']['channels']==72
assert (OUT/'reader_review.md').exists()
text=REPORT.read_text()
for i,n in enumerate(names,1):assert f'### 2.{i} {n}：未否证' in text
# Create manifest before checking its report link; the completed manifest is
# built below and intentionally excludes its own hash.
(OUT/'manifest.json').write_text('{}\n')
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
for target in links:
    assert not target.startswith(('http:','https:'))
    assert (REPORT.parent/target).exists(),target
qa={'finished_utc':datetime.now(timezone.utc).isoformat(),'report_bytes':REPORT.stat().st_size,
    'report_lines':len(text.splitlines()),'checked_local_links':len(links),
    'python_files_parse_checked':len(python_files),'frozen_inputs_unchanged':len(frozen['files']),
    'candidate_count':10,'verdict_counts':{'未否证':10,'修正':0,'已否证':0},
    'scope':'Ten candidate texts; local counterexample certificates and numeric audits; no global feasible layout.'}
(OUT/'delivery_check.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
files=[REPORT]+sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json')
manifest=[{'path':str(p.relative_to(REPORT.parent)),'bytes':p.stat().st_size,
           'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
(OUT/'manifest.json').write_text(json.dumps({'files':manifest},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(qa,ensure_ascii=False,indent=2))
