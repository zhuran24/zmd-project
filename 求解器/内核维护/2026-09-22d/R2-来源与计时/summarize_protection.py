from probe_common import *
a=json.loads((OUT/'protected-before.json').read_text());b=json.loads((OUT/'protected-after.json').read_text())
changed=[k for k in a.keys()&b.keys() if a[k]!=b[k]];added=sorted(b.keys()-a.keys());removed=sorted(a.keys()-b.keys())
def protected(k):
 return k.startswith(('求解器/crates/','求解器/数据/','求解器/规格/','求解器/内核维护/2026-09-22/','求解器/内核维护/2026-09-22b/','求解器/内核维护/2026-09-22c/')) or k in ['求解器/Cargo.toml','求解器/Cargo.lock','求解器/内核维护/代码体检方案.md','求解器/内核维护/2026-09-22d/GPT-Pro-意见.md'] or '/' not in k
critical={k:v for k,v in a.items() if protected(k)}
summary={'before_files':len(a),'after_files':len(b),'existing_changed':sorted(changed),'removed':removed,'added_count':len(added),'protected_existing_files':len(critical),'protected_changed':[k for k in changed if protected(k)],'protected_removed':[k for k in removed if protected(k)],'protected_added':[k for k in added if protected(k)],'note':'Broad inventory includes concurrent sibling task outputs; this task only writes its designated output directory/report, /tmp sources, shared target artifacts.'}
dump(OUT/'protection-summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
