#!/usr/bin/env python3
"""Evaluate ONLY literal path declarations from six CLI scripts; no imports/main/tests."""
import ast,json,os
from pathlib import Path
OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[2]
rows=[]
for name,variable in [('revision_cli.py','EVIDENCE'),('revision_r2_cli.py','EVIDENCE'),('revision_r3_cli.py','OUT'),('revision_r4_cli.py','OUT'),('revision_r5_cli.py','E'),('round6_cli.py','E')]:
    p=ROOT/'crates/kernel/tests'/name
    tree=ast.parse(p.read_text())
    selected=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('ROOT',variable)]
    assert len(selected)==2
    # No arbitrary expressions: these assignments must contain only Path(__file__).resolve(), parent selection and '/'.
    assert not any(isinstance(n,ast.Call) and ast.unparse(n.func) not in ('Path','Path(__file__).resolve') for node in selected for n in ast.walk(node))
    values=[]
    for supplied in (None,str(OUT/'requested-redirect')):
        old=os.environ.get('KERNEL_TEST_EVIDENCE_DIR')
        try:
            if supplied is None:os.environ.pop('KERNEL_TEST_EVIDENCE_DIR',None)
            else:os.environ['KERNEL_TEST_EVIDENCE_DIR']=supplied
            ns={'Path':Path,'__file__':str(p)}
            exec(compile(ast.Module(body=selected,type_ignores=[]),str(p),'exec'),ns)
            values.append(str(ns[variable]))
        finally:
            if old is None:os.environ.pop('KERNEL_TEST_EVIDENCE_DIR',None)
            else:os.environ['KERNEL_TEST_EVIDENCE_DIR']=old
    rows.append(dict(file=str(p.relative_to(ROOT)),line=selected[-1].lineno,variable=variable,without_env=values[0],with_env=values[1],env_ignored=values[0]==values[1]))
(OUT/'default_path_probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'scripts':len(rows),'same_repository_target_with_or_without_env':sum(r['env_ignored'] for r in rows),'tests_executed':0,'audited_scripts_imported':0,'default_target_writes':0},ensure_ascii=False))
for r in rows: print(r['file']+':'+str(r['line']),r['without_env'])
