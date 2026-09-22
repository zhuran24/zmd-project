from pathlib import Path
import json,hashlib,difflib,ast
R=Path('/home/zhuran24/zmd-research-fresh'); E=R/'求解器/会议成果/任务书7执行/证据/规格'; p=R/'求解器/数据/样例/check_examples.py'
old=p.read_text(); tree=ast.parse(old); assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCE_HASHES' for t in n.targets)); values=ast.literal_eval(assignment.value)
new=old
for name,sha in values.items():
 actual=hashlib.sha256((R/name).read_bytes()).hexdigest()
 assert old.count(sha)==1,(name,'unexpected additional registry')
 new=new.replace(sha,actual)
p.write_text(new)
(E/'secondary-registry.json').write_text(json.dumps({'path':str(p),'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'final_sha256':hashlib.sha256(new.encode()).hexdigest(),'reason':'SOURCE_HASHES是仍执行的正式源比对登记（原L58—62，读取在L720、L734—735）；按任务1同步全部现行登记，仅替换规则/任务两个哈希字面量，其余字节及算法保持。原样例、投影和历史结果不重生成。','diff':list(difflib.unified_diff(old.splitlines(),new.splitlines(),lineterm='',n=2))},ensure_ascii=False,indent=2)+'\n')
print('secondary live registry synchronized; two hash literals changed')
