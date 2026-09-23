#!/usr/bin/env python3
"""交付物一致性与读者自审记录；不重新求解、不把文档检查当布局认证。"""
import ast,hashlib,json,re,datetime
from pathlib import Path
from collections import Counter
E=Path(__file__).resolve().parent;B=E.parent;report=B/'闸门-第3轮.md'
read=lambda n:json.loads((E/n).read_text())
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=read('输入哈希.json')
changed={p:h(Path(p)) for p,v in manifest['files'].items() if h(Path(p))!=v['sha256']}
assert not changed
same=(B/'生成/候选.json').read_bytes()==(E/'候选只读快照.json').read_bytes()
assert same
(E/'输入稳定性.json').write_text(json.dumps({'files_checked':len(manifest['files']),'changed':changed,'live_candidate_matches_snapshot':same,'checked_at':datetime.datetime.now().astimezone().isoformat()},ensure_ascii=False,indent=2)+'\n')
text=report.read_text();summary=read('闸门结论.json')
blocks=re.findall(r'```json\n(.*?)\n```',text,re.S)
assert len(blocks)==1 and json.loads(blocks[0])==summary
assert set(summary)=={'pass','checkerA','checkerB','lp','disagreements','area','report_path'}
assert summary['pass'] is False and summary['report_path']==str(report)
assert all(type(v)is str and v for k,v in summary.items() if k!='pass')
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
assert all((report.parent/url).exists() for url in links)
formal=text.split('**当前72条逐条台账**')[1].split('**area**')[0]
nums=[int(v) for v in re.findall(r'^\|(\d+)\|',formal,re.M)]
assert nums==list(range(1,73))
diff=read('分歧逐项裁定.json')
assert len(diff['formal_differences'])==20 and not diff['unresolved_disagreements']
assert set(x['number'] for x in diff['formal_differences'])==set(read('逐条对照.json')['normalized_status_difference_numbers'])
groups=[];current=[]
for line in text.splitlines()+['']:
    if line.startswith('|'):current.append(line)
    elif current:groups.append(current);current=[]
assert len(groups)==8
assert all(len(set(len(line.split('|')) for line in group))==1 for group in groups)
lp=read('独立LP.json');a=read('A适配复核.json');b=read('B适配复核.json')
assert lp['candidate_sha256']==a['candidate_sha256']==b['candidate_sha256']==h(E/'候选只读快照.json')
assert lp['strict']['status']==lp['strict_without_presolve']['status']==lp['source_relaxed_with_targets']['status']==2
assert (lp['strict']['variables'],lp['strict']['rows'])==(774,18583)
assert Counter(x['status'] for x in a['checks'])=={'checked':47,'antecedent_false':7,'violation':2,'blocked':1}
assert Counter(x['status'] for x in b['checks'])=={'PASS':446,'FAIL':5,'INFO':1,'BLOCKED':1}
assert read('独立证书回放.json')['strict_infeasible_exact'] and read('A证书回放.json')['verified']
scripts=list(E.glob('*.py'))
for p in scripts:ast.parse(p.read_text(),filename=str(p))
review={'status':'passed','report_sha256':h(report),'reviewer':'本轮主会话；未声称第二位独立人工审稿',
 'reader_pass':{'self_contained':True,'current_state_separated_from_historical_snapshots':True,
 'header_matches_evidence':True,'no_instruction_echo':True,'numbers_and_units_consistent':True,
 'names_self_explanatory':True,'cross_references_exist':True},
 'checks':{'seven_fields_match_footer':True,'formal_rows':len(nums),'difference_rows':len(diff['formal_differences']),
 'local_links':len(links),'markdown_tables':len(groups),'syntax_parsed_scripts':len(scripts),'input_files_stable':len(manifest['files'])},
 'scope':'交付物自审；候选结论仍是pass=false，静态与LP失败；没有运行认证。'}
(E/'交付自审.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
files=[p for p in E.rglob('*') if p.is_file() and p.name!='证据哈希.json']+[report]
(E/'证据哈希.json').write_text(json.dumps({str(p.relative_to(B)):h(p) for p in sorted(files)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(review,ensure_ascii=False))
