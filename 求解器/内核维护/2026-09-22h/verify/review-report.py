import hashlib,json,re,subprocess
from pathlib import Path
v=Path(__file__).resolve().parent;r=v.parents[3]
p=v/'核验报告.md';text=p.read_text();summary=json.loads((v/'summary.json').read_text())
links=re.findall(r'\]\(([^)]+)\)',text)
missing=[name for name in links if name!='report-review.json' and not (v/name).exists()]
assert not missing,missing
assert all(str(summary['counts'][field]) in text for field in ['rust_tests','python_tests','independent_layouts','independent_ticks','historical_files','old_sha_text_lines','old_sha_text_files'])
assert summary['final_head'] in text and summary['before_head'] in text
current_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip()
assert current_head==summary['final_head']
status=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=r).decode().split('\0')
after=json.loads((v/'after.json').read_text())
before_other={x for x in after['status'] if not x[3:].startswith('求解器/内核维护/2026-09-22h/verify/')}
now_other={x for x in status if x and not x[3:].startswith('求解器/内核维护/2026-09-22h/verify/')}
assert before_other==now_other,(before_other^now_other)
review={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'links_checked':len(links),'missing_links':missing,'numeric_summary_matches':True,'head_matches_report':True,'status_outside_verify_matches_snapshot':True,
    'reader_review':{'self_contained_verdict':True,'historical_and_current_rules_distinguished':True,'scope_failures_not_attributed_to_runtime':True,'counts_do_not_double_count_reruns':True,'own_temporary_write_deviation_disclosed':True,'protected_history_evidence_linked':True}}
(v/'report-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(review,ensure_ascii=False,indent=2))
