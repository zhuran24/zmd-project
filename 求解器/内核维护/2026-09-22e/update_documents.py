#!/usr/bin/env python3
"""保持条款去向，重建现行覆盖的原文、行号、索引及来源指纹。"""
from pathlib import Path
import json, re, hashlib
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
cat=json.loads((R/'数据/正式静态目录.json').read_text())

def row_key(text):
    return text.split('：',1)[0]

def replace_rows(section, rows, pattern=r'^\| \d+ \|'):
    lines=section.splitlines(); indexes=[i for i,line in enumerate(lines) if re.match(pattern,line)]
    assert indexes
    return '\n'.join(lines[:indexes[0]]+rows+lines[indexes[-1]+1:])+'\n'

for path, kind in [(R/'规格/规则覆盖表.md','spec'),(R/'数据/规则覆盖表.md','data')]:
    sections=path.read_text().split('## ')
    for index,source in enumerate(cat['sources'][:2],1):
        old=[line.split('|')[1:-1] for line in sections[index].splitlines() if re.match(r'^\| \d+ \|',line)]
        by_key={row_key(row[1].strip()):[cell.strip() for cell in row[2:]] for row in old}
        rows=[]
        for n,line in enumerate(source['lines'],1):
            text=line.strip() or '（空行）'
            if kind=='spec':
                rest=by_key.get(row_key(text), ['§5；T12','成品拿取的批量与不干预其他单位条件；据：拿取成品'])
            else:
                rest=[f'`sources[{index-1}].lines[{n-1}]` 完整转录；'+('规则字段与运行义务见规格；完整转录不代表运行认证' if index==1 else 'task.conditions；本条运行或布局义务由规格承接，尚无执行证书')]
            rows.append('| '+' | '.join([str(n),text,*rest])+' |')
        sections[index]=replace_rows(sections[index],rows)
    if kind=='spec':
        old=[line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|',line)]
        dest={row[2].strip().removeprefix('约束·'):row[3].strip() for row in old}
        rows=[f"| {n} | {rule['source_line']} | 约束·{rule['name']} | {dest.get(rule['name'],'§6：达标必要条件，保持原文前件；未作运行认证')} |" for n,rule in enumerate(cat['constraints'],1)]
        sections[3]=replace_rows(sections[3],rows)
        sections[0]=re.sub(r'日期：[^\n]+', '日期：2026-09-22。状态：现行规则 114 行、任务 16 行逐行映射，登记正式约束全部 72 条；C 线内核输入接口索引见第5节。行号对应运行语义 §1 的 SHA-256 快照。',sections[0])
    else:
        rows=[f"| {rule['name']} | {rule['section']}；{rule['obligation'] or '按条文前件'} | `constraints[{n}]`；报告“正式条目/{rule['name']}”；据行 {rule['basis_line']} 完整转录 |" for n,rule in enumerate(cat['constraints'])]
        sections[3]=replace_rows(sections[3],rows,r'^\| .*`constraints\[')
        sections[0]=re.sub(r'日期：[^\n]+', '日期：2026-09-22。状态：现行规则 114 行、任务 16 行与 72 条正式约束逐行/逐项登记；完整转录不等于运行语义已实现。', sections[0])
    path.write_text('## '.join(sections))
p=R/'规格/运行语义.md';s=p.read_text()
s=s.replace('日期：2026-09-21。状态：','日期：2026-09-22。状态：现行三份正式源与 72 条约束覆盖已同步；')
s=re.sub(r'本次现行依据为规则`[^`]+`、任务`[^`]+`、约束`[^`]+`', '本次现行依据为'+ '、'.join(label+'`'+source['sha256'][:12]+'`' for label,source in zip(['规则','任务','约束'],cat['sources'])),s)
s=s.replace('旧逐行入口为史料[规则覆盖表](规则覆盖表.md)，当前行号以本节正式源和任务7回填为准','现行逐行入口为[规则覆盖表](规则覆盖表.md)，当前行号与本节正式源一致')
for source in cat['sources']:
    s=re.sub(r'^\| `'+re.escape(source['path'])+r'` \|.*$',f"| `{source['path']}` | {len(source['lines'])} | `{source['sha256']}` |",s,flags=re.M)
s=s.replace('；种植机恰 32 台时植物入库为零，荞花采种/种植率为 5.5/11、砂叶为 10.5/21。（据：约束·回路守恒；条文直引）','；植物零入库由约束·非成品零入库对任意台数给出。种植机恰 32 台时，荞花采种/种植率为 5.5/11、砂叶为 10.5/21。（据：约束·非成品零入库、约束·回路守恒；条文直引）')
anchor='| 取货口配置、入库途径 |'
a=s.index(anchor)
s=s[:a]+'''| 矿系不入库、非成品零入库 | 达标循环中十种含矿非成品零入库；全部非成品零入库包括任意种植机台数下的植物。核心正入库计划只允许两成品，据为约束·非成品零入库、入库途径、协议核心；静态计划不认证实际循环与全参数。 |
| 传输按仓库余量判定 | 实际传输判定前，非成品箱内总件数 n 与仓库真实可接受余量 f 须满足 n=0 或 f=0，计入同刻此前判定；不禁止冷却期间的物理过箱。普通有限运行仍按真实余量接收非成品并记账，必要条件不作为转移守卫。据：约束·传输按仓库余量判定、传输 |
'''+s[a:]
p.write_text(s)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=R/'规格/修订记录.md'
with p.open('a') as f:
    f.write('\n## 2026-09-22 r23：72 条正式约束与核心入库检查同步\n\n')
    f.write('本轮登记：目录 version 为 `'+cat['version']+'`，SHA-256 为 `'+sha(R/'数据/正式静态目录.json')+'`。正式源如下：\n\n| 文件 | SHA-256 |\n|---|---|\n')
    for source in cat['sources']: f.write(f"| {source['path']} | `{source['sha256']}` |\n")
    f.write('\n新增「1113 位置」；「矿系不入库」只保留十种含矿非成品零入库；同步「非成品零入库」「回路守恒」「回路存量」「植株半分」原文及据。删除 `plant_trigger` 提取与目录常量，不设置替代默认值。`矿系不入库/计划` 名称保留兼容，核心计划只接受两种成品，依据迁移至「非成品零入库、入库途径、协议核心」，不依赖种植机台数。矿系、非成品、传输判前条件的正式覆盖各保留 Unknown，普通运行转移与生产抽象支持域未改。\n\n重建两张现行覆盖表（114 行规则、16 行任务、72 条约束）并更新运行语义来源；修订自查使用本轮只读指纹。样例、fixture、SOURCE_HASHES 和候选 B 来源按实际变化重锁。脚本、验证命令/日志与历史证据还原清单见[本轮执行记录](../内核维护/2026-09-22e/记录.md)。旧记录和旧证据保留。\n')
print('updated coverage tables, semantics source snapshot and revision registration')
