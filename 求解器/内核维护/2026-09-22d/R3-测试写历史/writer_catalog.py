#!/usr/bin/env python3
"""Resolve closed path declarations statically, without importing audited modules."""
import ast,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
inventory=json.loads((OUT/'static_inventory.json').read_text())
def val(n,env):
    if isinstance(n,ast.Constant):return n.value
    if isinstance(n,ast.Name):return env[n.id]
    if isinstance(n,ast.BinOp):
        a,b=val(n.left,env),val(n.right,env)
        if isinstance(n.op,ast.Div):return Path(a)/b
        if isinstance(n.op,ast.Add):return a+b
    if isinstance(n,ast.Subscript):return val(n.value,env)[val(n.slice,env)]
    if isinstance(n,ast.Attribute) and n.attr in ('parent','parents','name','stem'):return getattr(val(n.value,env),n.attr)
    if isinstance(n,ast.Call):
        name=ast.unparse(n.func)
        if name in ('Path','pathlib.Path'):return Path(val(n.args[0],env))
        if name in ('Path.cwd','pathlib.Path.cwd'):return ROOT
        if isinstance(n.func,ast.Attribute) and n.func.attr in ('resolve','absolute'):
            return Path(val(n.func.value,env)).absolute()
    raise ValueError()
rows=[]
for r in inventory:
    if not r['file'].endswith('.py') and not r['file'].endswith('/bin/python'):continue
    if not r['sinks'] and not r['calls']:continue
    p=ROOT/r['file'];tree=ast.parse(p.read_text());env={'__file__':str(p)};paths=[]
    # All assignments are only evaluated if they are closed, side-effect-free path expressions.
    for n in sorted(ast.walk(tree),key=lambda n:getattr(n,'lineno',0)):
        if not isinstance(n,ast.Assign):continue
        try:v=val(n.value,env)
        except (ValueError,KeyError,TypeError,IndexError,AttributeError,ZeroDivisionError):continue
        for t in n.targets:
            if isinstance(t,ast.Name):
                env[t.id]=v
                if isinstance(v,Path):paths.append(dict(line=n.lineno,variable=t.id,path=str(v)))
    rows.append(dict(file=r['file'],closed_paths=paths,sinks=r['sinks'],calls=r['calls']))
(OUT/'resolved_writer_catalog.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
text=['# 全树脚本写点目录\n\n日期：2026-09-22。性质：静态源码台账。范围：Git 跟踪的 Python 脚本（含历史快照）及维护包装器；Rust 活动测试见主报告。没有执行被查程序。\n\n每个条目给出实际文件、行号、可静态求值的目录和写点。`ROOT/BASE` 可兼作输入根，并不表示该目录整体被覆盖；具体写向以写点及调用参数为准。未能静态求值的函数参数保留原表达式，不假装成已运行路径。文档生成器和历史复核脚本也列入，以免将它们当只读入口。\n']
for r in rows:
    if not r['sinks'] and not any('--out' in x['source'] or x['source'].startswith(('save(','write(','s.finish(','b.generate(')) for x in r['calls']):continue
    text+=['\n## `'+r['file']+'`\n\n']
    for v in r['closed_paths']:
        try:path=str(Path(v['path']).relative_to(ROOT)) or '.'
        except ValueError:path=v['path']
        text+=['- 路径 `'+str(v['line'])+'`: `'+v['variable']+' = '+path+'`\n']
    text+=['\n```text\n']
    for x in r['sinks']+r['calls']:
        if x in r['calls'] and not any(k in x['source'] for k in ('save(', 'write(', 'dump(', '--out', 'finish(', 'generate(')):continue
        text+=[str(x['line'])+': '+x['source']+'\n']
    text+=['```\n']
(OUT/'全树脚本写点目录.md').write_text(''.join(text))
print('Statically resolved script catalog:',len(rows),'scripts; source is not executed.')
