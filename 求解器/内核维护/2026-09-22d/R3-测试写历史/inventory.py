#!/usr/bin/env python3
"""Static source inventory only: never import or execute audited scripts."""
import ast, hashlib, json, re, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
paths=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0')
rows=[]
for name in paths:
    p=ROOT/name
    if p.suffix not in ('.py','.sh','.rs') and name!='内核维护/2026-09-22/bin/python': continue
    s=p.read_text(); lines=s.splitlines()
    assignments=[]; calls=[]; sinks=[]
    if p.suffix=='.py' or name.endswith('/bin/python'):
        try: tree=ast.parse(s)
        except SyntaxError: tree=None
        if tree:
            for n in ast.walk(tree):
                if isinstance(n,(ast.Assign,ast.AnnAssign)):
                    val=n.value
                    targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                    if val is not None and any(isinstance(t,ast.Name) and (t.id.isupper() or t.id in ('out','output','output_dir','target','path','here','root','base','dest','source','record','report_path','evidence')) for t in targets):
                        expr=ast.unparse(n)
                        if len(expr)<700 and ('/' in expr or 'Path' in expr or '.parent' in expr or 'args.' in expr or 'OUT' in expr or 'EVIDENCE' in expr):
                            assignments.append({'line':n.lineno,'source':expr})
                if not isinstance(n,ast.Call): continue
                f=ast.unparse(n.func); expr=ast.unparse(n)
                is_sink=f.endswith(('.write_text','.write_bytes','.mkdir','.unlink','.rename','.replace')) or f in ('shutil.copyfile','shutil.copytree','shutil.rmtree','shutil.move')
                if f.endswith('.open') or f=='open':
                    is_sink=any(isinstance(a,ast.Constant) and isinstance(a.value,str) and re.match('^[wax][bt+]*$',a.value) for a in n.args[1:]) or any(k.arg=='mode' and isinstance(k.value,ast.Constant) and str(k.value.value).startswith(('w','a','x')) for k in n.keywords)
                if is_sink: sinks.append({'line':n.lineno,'source':expr[:900]})
                elif f.split('.')[-1] in ('save','write','dump','write_json','save_json','call','invoke','run','run_script','generate','main') or '--out' in expr or '--output' in expr:
                    if len(expr)<1100: calls.append({'line':n.lineno,'source':expr[:900]})
    else:
        for i,line in enumerate(lines,1):
            if re.search(r'fs::(?:write|create_dir)|File::create|Command::new|--out|\b(?:tee|cp|mv|mkdir)\b|>>?',line):
                if p.suffix=='.rs' and not re.search(r'fs::(?:write|create_dir)|File::create|Command::new|--out',line): continue
                sinks.append({'line':i,'source':line})
    rows.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'assignments':sorted(assignments,key=lambda x:x['line']),'sinks':sorted(sinks,key=lambda x:x['line']),'calls':sorted(calls,key=lambda x:x['line'])})
(OUT/'static_inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
active=[r for r in rows if r['file'].startswith(('crates/kernel/tests/','数据/样例/','数据/工具/')) and '/legacy_probes/' not in r['file']]
for key,data in [('active-source-writers.md',active),('all-source-writers.md',rows)]:
    chunks=['# 静态写点与路径表达式台账\n\n源码只读扫描；未执行列出的程序。`sinks` 包括创建目录、覆盖、删除和移动；`calls` 为间接写出链定位，不能仅凭命名认定实际写入。历史快照不是当前测试入口。\n']
    for r in data:
        if not r['sinks'] and not r['calls']:continue
        chunks += ['\n## '+r['file']+'\n','\n```text\n']
        for category in ('assignments','sinks','calls'):
            chunks += [category+'\n']+[str(x['line'])+': '+x['source']+'\n' for x in r[category]]
        chunks+=['```\n']
    (OUT/key).write_text(''.join(chunks))
print(json.dumps({'source_files':len(rows),'files_with_direct_mutation_or_command':sum(bool(r['sinks']) for r in rows),'active_files':len(active),'active_with_direct_mutation_or_command':sum(bool(r['sinks']) for r in active)},ensure_ascii=False))
