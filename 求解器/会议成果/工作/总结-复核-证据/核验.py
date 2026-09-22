from pathlib import Path
import json, re, hashlib
from collections import Counter

root=Path(__file__).resolve().parent
out=root.parent
evidence=json.loads((root/'输入与结果.json').read_text())
reply=json.loads((root/'回复.json').read_text())
entries=evidence['entries']
assert set(reply)=={'file','final_file','verdicts','counts'}
assert set(v['id'] for v in reply['verdicts'])=={f'M-{n}' for n in range(1,68)}|{'F-68','F-69'}
assert len(reply['verdicts'])==69
for v in reply['verdicts']:
    assert set(v)=={'id','verdict','reason'}
    assert v['verdict'] in {'维持','改状态','删除','改写'}
    assert all(isinstance(v[k],str) and v[k] for k in v)
for source in evidence['inputs']:
    assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()==source['sha256'],source['path']
final=(out/'总结-终稿.md').read_text()
audit=(out/'总结-否证.md').read_text()
ids=re.findall(r'^### (F-\d+)\s',final,re.M)
assert len(ids)==69 and set(ids)=={f'F-{n}' for n in range(1,70)}
assert len(re.findall(r'^## ',final,re.M))==4
for x in entries:
    block=re.search(rf"^### {x['id']}\s.*?(?=^### |^## |\Z)",final,re.M|re.S).group()
    for field in ['结论','依据','对话时刻','取代v45何处']:
        assert f'**{field}：**' in block,(x['id'],field)
    if x['status']=='未定':
        assert '**缺什么：**' in block,x['id']
    assert x['reason'] in audit,x['id']
assert len(evidence['owner_coverage'])==24
dialogue=Path(evidence['inputs'][5]['path']).read_text()
actual=[dialogue[:m.start()].count('\n')+1 for m in re.finditer(r'^\*\*👤 OWNER\*\*',dialogue,re.M)]
assert actual==[x['line'] for x in evidence['owner_coverage']]
assert len(evidence['disputes'])==16
assert {x['id'] for x in evidence['disputes']}=={f'D-{n}' for n in range(1,17)}
reader_ids=[r for x in entries for r in x['reader_ids']]
assert len(reader_ids)==len(set(reader_ids))==164
for p in [out/'总结-终稿.md',out/'总结-否证.md']:
    for raw in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if raw.startswith(('http:','https:','#')): continue
        target=Path(raw)
        if not target.is_absolute(): target=p.parent/target
        assert target.exists(),str(target)
result={
 'schema':'pass',
 'original_entries':67,
 'added_entries':2,
 'reader_entries_covered':164,
 'owner_utterances_covered':24,
 'disputes_adjudicated':16,
 'counts':dict(Counter(x['status'] for x in entries)),
 'verdict_counts':dict(Counter(x['verdict'] for x in entries)),
 'all_input_hashes_unchanged':True,
 'links_exist':True,
 'outputs':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in [out/'总结-否证.md',out/'总结-终稿.md',root/'回复.json']],
 'limits':'结构、覆盖、引用文件存在性与字节未变的核验；数学判定由逐条人工复核承担，不是整厂运行认证。'
}
(root/'核验结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(root/'核验.log').write_text(json.dumps(result,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
