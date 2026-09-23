from helpers import *
from guard import digest, guard
guard('preflight-before')
edit('数据/样例/check_examples.py', [('只接一轴的桥保留另一轴 pending 并通过结构检查','只接一轴的桥另一轴仍固定双向，未接边不形成通道')])
edit('数据/候选B/验证记录.md', [('2026-09-22g 记录](../../内核维护/2026-09-22g/记录.md)','2026-09-22h 记录](../../内核维护/2026-09-22h/记录.md)')])
# Header notes name the current bridge semantics without changing unrelated support text.
for name in ['运行语义.md','选择点清单.md','选择点参数轴.md','内核输入.md','受限转移定义.md']:
    p=ROOT/'规格'/name;t=p.read_text()
    lines=t.splitlines()
    lines.insert(2,'现行桥接器依据：2026-09-22，正式规则 `743f18b`；四边固定双向、每对边上限1且独立调度，物品不移回刚离开的单位。')
    write(p,'\n'.join(lines)+'\n')
# The axis table is a hashed source: refresh only its exact reference bytes after the header change.
summary=json.loads((OUT/'sync-summary.json').read_text())
axis=ROOT/'规格/选择点参数轴.md'
for rel in summary['inputs']:
    p=ROOT/rel;d=json.loads(p.read_text());old=d['parameters']['axis_registry']['sha256']
    assert old in p.read_text()
    write(p,p.read_text().replace(old,digest(axis)))
import sys
sys.path.insert(0,str(ROOT/'数据/样例'))
from runtime_example import profile_projection
for name,source in [('kernel_profile_v1参数赋值.json','混做粉碎机两下游.json'),('分流器三路轮询-参数赋值.json','分流器三路轮询.json')]:
    write(ROOT/'数据/样例'/name,dump(profile_projection(json.loads((ROOT/'数据/样例'/source).read_text()))))
guard('preflight-after')
