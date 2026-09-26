"""Build the self-contained report from reviewed conclusions and proof text."""
from pathlib import Path
import json,hashlib,re
OUT=Path(__file__).resolve().parent
target=OUT.parent/'推导81C.md'
conclusions=json.loads((OUT/'conclusions.json').read_text())
inputs=json.loads((OUT/'inputs.json').read_text())
numbers=json.loads((OUT/'final_numbers.json').read_text())
formal=[s for s in inputs['sources'] if s['role']=='formal premise']
header='''# 第81轮C组推导：换到1110后的在产、运输、供电和增配预算

日期：2026-09-26。状态：推导与独立复算完成，八条必要条件待审。

**本轮证明：任意面积的十桩布局都没有占边桩；A≥1110时九机型仍恰为下限、仍没有协议储存箱。桩数只能推出P≤13，十三桩尚未排除。** 新的增机增箱排除使用方向面积成本及边界端点，未借用第63—80轮对1113所有位置的排除。正式总上界仍按快照为1113，本轮未给出达标布局。

前提仅为本轮指定的三份快照；候选和讨论只作材料。inputs.json冻结其内容与本次读到的候选文本。报告不把根目录同名文件当作当前前提。

| 正式快照 | SHA-256 |
|---|---|
'''
for s in formal:
    name=Path(s['path']).name
    header+=f'| [ {name} ](前提快照/{name}) | `{s["sha256"]}` |\n'
header+='''
统一记号：坐标左下角为(0,0)；A为最大空矩形面积，P为供电桩数；占格含第1列、第69列、第1行或第69行的供电桩计入J。n为物理台数，「在产」只指所考察循环态中有正制造批数。所有空矩形短边至少6格。下文的必要条件对每个可到达的达标循环态分别成立。

## 一、候选条目

'''
parts=[header]
for i,c in enumerate(conclusions,1):
    parts.append(f'### {i}. {c["name"]}\n\n{c["name"]}：{c["text"]}\n\n')
    for label,key in [('种类','kind'),('据','basis'),('推导','derivation'),('关系','relation'),('状态','status')]:
        parts.append(f'{label}：{c[key]}\n\n')
proof=(OUT/'proofs.md').read_text()
cost='| 增加一件 | 实际占地增加 | 如在产的供电加权费用 | 4E+Ω净增至少 | 运输单位仍至少 | A≥1110结果 |\n|---|---:|---:|---:|---:|---|\n'
for r in numbers['costs']:
    charge=str(r['extra_active_weight']) if r['extra_active_weight'] is not None else '不按制造单位收费'
    cost+=f'| {r["name"]} | {r["extra_area"]}格 | {charge} | {r["net_direction_area_cost"]} | {r["T_lower_after_one"]} | 排除 |\n'
branches='| 桩数P | 尚未被这些条件排除的J | X+Y上限 | 说明 |\n|---:|---|---|---|\n'
for p in (10,11,12,13):
    rows=[r for r in numbers['remaining_1110_scalar_branches'] if r['P']==p]
    branches+=f'| {p} | '+ '、'.join(str(r['J']) for r in rows)+' | '+ '、'.join(str(r['XY_upper']) for r in rows)+' | 按J次序对应；未证布局存在 |\n'
proof=proof.replace('{{COST_TABLE}}',cost).replace('{{BRANCH_TABLE}}',branches)
parts.append(proof)
target.write_text(''.join(parts))
text=next(s['text'] for s in formal if Path(s['path']).name=='求解约束.txt')
entries=[]
for line_no,line in enumerate(text.splitlines(),1):
    if not line or line[0].isspace() or '：' not in line:continue
    name,body=line.split('：',1)
    if not body:continue
    entries.append(dict(name=name,line=line_no,text=body))
assert len(entries)==72,(len(entries),[x['name'] for x in entries])
(OUT/'formal_index.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report_path':str(target),'conclusions':len(conclusions),'formal_entries':len(entries),
    'report_sha256':hashlib.sha256(target.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
