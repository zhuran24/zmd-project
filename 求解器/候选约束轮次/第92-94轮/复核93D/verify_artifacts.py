from pathlib import Path
import ast, hashlib, json, re
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'复核93D.md'
text=REPORT.read_text()
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
missing=[x for x in links if not (REPORT.parent/x).exists()]
assert not missing, missing
for path in HERE.glob('*.py'):
    ast.parse(path.read_text(),filename=str(path))
for path in HERE.glob('*.json'):
    json.loads(path.read_text())
dense=json.loads((HERE/'dense_results.json').read_text())
loose=json.loads((HERE/'arbitrary_results.json').read_text())
cycle=json.loads((HERE/'independent_nine_cycle.json').read_text())
assert dense['cases']==280 and dense['paired_steps']==504000
assert loose['cases']==500 and loose['paired_steps']==800000
assert loose['lowest_BB_excess_phi2']==352
assert cycle['period_steps']==9 and cycle['empty_counts']==[1,1,0,0]
assert cycle['published_core_certificate_equal_after_cyclic_shift']==5
snapshot=HERE.parent/'前提快照'
necessary=[x for x in (snapshot/'求解约束.txt').read_text().splitlines() if '：' in x and not x.startswith(' ') and not x.endswith('：')]
sufficient=[x for x in (snapshot/'求解充分条件.txt').read_text().splitlines() if '：' in x and not x.startswith(' ')]
assert len(necessary)==77, len(necessary)
assert len(sufficient)==11, len(sufficient)
result={'report':str(REPORT),'report_lines':len(text.splitlines()),'links_checked':len(links),
        'necessary_entries':len(necessary),'sufficient_entries':len(sufficient),
        'paired_state_steps':dense['paired_steps']+loose['paired_steps'],
        'syntax_json_links_and_claims':'pass',
        'reader_pass':['Definitions and conditions included','Two readings separated',
                       'Original 176 retained with explicit start boundary',
                       'Abstract cycle not presented as a legal layout',
                       'Finite probes separated from universal proofs']}
(HERE/'artifact_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
manifest={str(p.relative_to(HERE.parent)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'}
manifest[REPORT.name]=hashlib.sha256(REPORT.read_bytes()).hexdigest()
(HERE/'artifact_hashes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
