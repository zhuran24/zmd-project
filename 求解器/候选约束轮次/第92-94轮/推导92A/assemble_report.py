#!/usr/bin/env python3
"""Assemble the reviewable report and the response payload from this directory."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
REPORT = OUT.parent / '推导92A.md'
inventory = json.loads((OUT/'inventory.json').read_text())
root_notes = (OUT/'root_notes.md').read_text()

def paragraph(name):
    return re.search(r'^'+re.escape(name)+r'：(.+)$', root_notes, re.M).group(1)

root_candidates = []
def candidate(name, text, basis, derivation, relation=None):
    root_candidates.append(dict(name=name, kind='必要条件', text=text, basis=basis,
                                derivation=derivation, relation=relation or f'修订正式条目「{name}」'))

candidate('分叉分支',
          '规则「层数」中存在多个合资格下游元件时，按哪一个数层数随接通先后而定，规则未给出唯一选择办法；目标须对每种规则允许的选择及相应可到达循环态成立。成环数不出来时仍为未定，不得指定有利层数，也不得因此擅自排除该构型。',
          '规则第28—30行；任务第14行。', '阻尼分支改为数层数所选元件；未定处不得取有利值。')
candidate('传输相位', paragraph('传输相位'), '规则第20、21、25—27、37行；任务第12—14行。',
          '传输只在步内判定执行，持续运行时冷却40步；覆盖实际可到达余数。')
candidate('判定先后',
          '判定先后不再是独立任取的同刻排列。每步依次结束到时制造、逐个判定、开始能开始的制造；元件按层数从小到大排，元件之后才排非运输单位，同层元件之间及非运输单位之间按送货通道最早接通的先排，并执行非分流器元件上游一起判定及收货轮询；各自每步只判定一次。目标须对接通、层数选择及其他规则未定量产生的全部合法步序和可到达循环态成立。',
          '规则第25—33行；任务第14行。', '第27行给出排序，第31行给出一起判定，第26行禁止重复判定。')
candidate('传输按仓库余量判定', paragraph('传输按仓库余量判定'),
          '规则第37行；非成品零入库。', '每次实际传输前min(箱内量,仓库余量)=0；详见报告。')
candidate('满速箱头限存', paragraph('满速箱头限存'),
          '规则第23—27、32、65、73行；端口速率。', '满速迫使每口每8步取一次；箱头多于c_x件会堵住其余口至少8步。')
candidate('传输与送货先后', paragraph('传输与送货先后'),
          '规则第26、37行。', '第37行明确保留两种先后，结论须分别成立。',
          '补充不得依赖的量；与「传输相位」「判定先后」分别记录。')

all_candidates = root_candidates[:]
for name in ('order_candidates.json', 'clearing_candidates.json', 'polling_candidates.json'):
    all_candidates.extend(json.loads((OUT/name).read_text()))
formal_order = {x['name']: x['id'] for x in inventory['items']}
all_candidates.sort(key=lambda c: formal_order.get(c['name'], 'Z99'))
assert len({c['name'] for c in all_candidates}) == len(all_candidates)
required = {'name', 'kind', 'text', 'basis', 'derivation', 'relation'}
for c in all_candidates:
    assert required <= set(c)
    assert all(isinstance(c[k], str) and c[k] for k in required)
    assert c['kind'] == '必要条件'
    if c['name'] in formal_order:
        assert c['relation'] == f'修订正式条目「{c["name"]}」'

table = [
 ('N01', '不受影响', '任务第14行仍要求离线后覆盖接通重排。'),
 ('N02', '只改措辞', '阻尼分支改为第28行按哪一个下游元件数层数；保留未定性。'),
 ('N03', '只改措辞', '覆盖可到达的步相位；持续运行传输周期为40步。'),
 ('N04', '改结论', '删去独立任意判定序，改为第25—33行派生的合法步序。'),
 ('N05', '改结论', '按每个合法组合比较级最大层数与最早接通；严格层数差只作为充分办法。'),
 ('N06', '只改措辞', '保留分流比可能变化的结论，以合法同层先后给出双编码见证。'),
 ('N07', '改结论', '保留实际周期的必要收支，撤去仅凭限流上限保证全部吸收的用法。'),
 ('N20', '只改措辞', '阻断不收货替换断开重接，有限批扣除与台数界不变。'),
 ('N34', '只改措辞', '观察点是实际传输动作前，覆盖传输与送货两种先后。'),
 ('N41', '只改措辞', '异种清空截止落在完成当步开工前，通道数界不变。'),
 ('N43', '只改措辞', '观察点改为每步判定后；64与分种平均22、42不变。'),
 ('N48', '只改措辞', '明确持续全收前提；箱内18件保守上界不变。'),
 ('N49', '改结论', '非运输单位按起点成功历史形成的顺序循环；均分保留。'),
 ('N51', '只改措辞', '按实际成功循环顺序编号，最大公约数公式不变。'),
 ('N56', '只改措辞', '同义观察截面改为每步判定后，c_x界不变。'),
]
by_id = {x['id']: x for x in inventory['items']}
assert {x[0] for x in table} == set(inventory['review_ids'])
summary = 'N01不受影响；N02、N03、N06、N20、N34、N41、N43、N48、N51、N56只改措辞；N04、N05、N07、N49改结论；无整条否证。已给出「不得依赖的量」新版及传输与送货先后新项。'

intro = f'''# 第92轮A组：正式必要条件的步进时间模型重核

日期：2026-10-02。状态：重核完成，候选待审。结论：15条在范围内的正式条目中，1条不受影响、10条只改措辞、4条改结论；没有据此否证一张达标布局。另补记「传输与送货先后」这一未定量。

本报告区分三种用途：必要条件限制所有达标布局或其明确前提所指定的子类；简化必须证明不丢最优；充分条件必须证明所述前提足以产生所述效果。本轮提交的候选均登记为必要条件。正式必要条件文件中的「不得依赖的量」是目标的全称量词范围；「密集结点」是运行可能性的说明，不能单独当作排除该构型的必要条件；它的保留用途只是禁止仅凭一个有利接通安排认证固定分流比。本轮没有简化或充分条件候选。

## 1. 前提与范围

数学前提只取同目录 `前提快照/` 内四份正式文件。`不补的设定.txt` 只作背景，依赖清点和 sim2 只作线索或局部计算工具。没有用根目录同名文件替换前提，没有把旧候选、旧模拟或旧充分性证明直接当成新规则证明。

| 快照 | 行数 | SHA-256 |
|---|---:|---|
'''
for p in inventory['snapshots']:
    intro += f'| {p["name"]} | {p["lines"]} | `{p["sha256"]}` |\n'
intro += '''
### 检索闭合

检索命令为 `rg -n '阻尼|存货优先级|判定次序|判定先后|同一时刻' 前提快照/求解约束.txt`。快照实际命中19行、12个条目，包含正文与“据”；任务描述中的13行没有作为停止检索的数目。加上指定的开头整节及重核项，共14条；再补扫N56的同义观察截面“任一时刻全部判定结束后”，共15条。没有把无旧术语的其他必要条件或充分条件扩成复扫任务。

| 命中的条目 | 快照行号 |
|---|---|
'''
for entry_id in sorted({m['item'] for m in inventory['matches']}):
    nums = ', '.join(str(m['line']) for m in inventory['matches'] if m['item'] == entry_id)
    intro += f'| {entry_id} {by_id[entry_id]["name"]} | {nums} |\n'
intro += '\n全文与逐行检索记录见 [inventory.json](推导92A/inventory.json)，生成程序为 [audit_inventory.py](推导92A/audit_inventory.py)。\n\n## 2. 逐条结论表\n\n| 条目 | 类型 | 结论 | 理由或修订内容 |\n|---|---|---|---|\n'
for entry_id, verdict, reason in table:
    kind = '必要条件的量词范围' if entry_id in {'N01','N02','N03','N04'} else ('必要条件（附顺序敏感性说明）' if entry_id == 'N06' else '必要条件（按原前提）')
    intro += f'| {entry_id} {by_id[entry_id]["name"]} | {kind} | {verdict} | {reason} |\n'

def fragment(path, start, end=None):
    text = (OUT/path).read_text()
    if start:
        text = text[text.index(start):]
    if end and end in text:
        text = text[:text.index(end)]
    return text

# Subreports are embedded so this report contains the proofs, not merely pointers.
order_text = fragment('construction_order.md', '## N05', '## 交付核验')
polling_text = fragment('polling_audit.md', '## N49 的原结论')
polling_text = re.sub(r'## 待审候选条文\n.*?(?=## 程序、结果及证据边界)', '', polling_text, flags=re.S)
clearing_text = fragment('clearing_stock.md', '## 2. N20', '## 7. 待审候选全文')
def nested(text):
    text = re.sub(r'^(#{2,})\s+\d+(?:\.\d+)*\.?\s+', r'\1 ', text, flags=re.M)
    return re.sub(r'^(#{2,}) ', r'#\1 ', text, flags=re.M)
proofs = '\n## 3. 不得依赖的量及逐次传输、箱头库存\n\n' + nested(root_notes)
proofs += '\n## 4. 取货分级、密集结点与来源定序\n\n' + nested(order_text)
proofs += '\n## 5. 误料停机、混做清空与回路、箱体存量\n\n' + nested(clearing_text)
proofs += '\n## 6. 轮询均分与混料分料\n\nN49作为必要条件使用时，只限制满足前提的子构型的实际流量；不要求所有达标布局满足这些前提。其前提足以保证局部均分，但不是全厂达标的充分条件。N51进一步给出下游供给的必要上界。\n\n' + nested(polling_text)

bridge = '''
## 7. 两处桥接条文的两种读法

现行第28行允许在同轴相邻桥接器之间绕回而使层数无法确定；第31行按非分流器上游中最先判定的那个触发一起判定，不能擅自换成最先实际送货者。证明若碰到这两处，须保留未定性和可能提前耗掉判定机会的影响，不能把直线满速当作规则公理。

拟改读法为：数层数不绕回自己，只有所有走法都会绕回时才未定；一起判定由最先往该单位送货的上游触发。在该读法下，N02、N04中的允许选择与派生步序按拟改条文重新产生；N05仍逐个合法组合比较取货级别。N06的构型没有桥接器，N49的历史反例不含桥接器，故两者结论不变。N07、N20、N34、N41、N43、N48、N51、N56只依赖实际收支、最低滞留、制造前件、库存容量或已写出的成功循环前提，也不因改读法改变。本轮没有把拟改条文作为现行证明前提。

特别是N49的“每次收件后恰1 tick腾空”是前提，不能用来认证任意桥接直线。现行读法下某直线达不到该前提时不能套用；拟改读法也须先证明它实际满足前提。

## 8. 计算证据与未解决边界

所有程序、日志、JSON和分项推导均在 [推导92A](推导92A/) 内。未运行内核 cargo 测试，未更改正式文件、候选文件或其他求解器路径，未使用 Git 操作。计算最多三个分项各一个进程加主进程，共四核上限；长枚举采用串行。

关键数值采用独立编码交叉核对：root_checks.py的分数换算与逐步时钟、子集穷举与极值间隔；clearing_check_fraction.py与clearing_check_integer.py；order_reference.py与order_independent.py；polling_verify_a.py与polling_verify_b.py，以及polling_formula_verify.py的直接计数和整数同余两种算法。具体结果、校验摘要和程序文件哈希见 [validation.json](推导92A/validation.json) 与 [artifact_manifest.json](推导92A/artifact_manifest.json)。

局部模拟只核验明确构型或有限算术，不充当达标布局。N06的种子返库小构型违背达标全厂的矿口专用和非成品零入库要求，其用途仅是证明规则允许不同分流比，不能作为全厂必要条件的反例。N49的历史顺序反例针对一般轮询断言，所改的只是该断言过强的接通顺序子句；它也不声称一张完整达标布局。

本轮未给出新的空矩形上界、合格布局或最优性证明，也未把规则仍未说明的成环层数算法补成确定算法。含这种未定处、且必须依赖其具体判定顺序的全厂认证仍须补足。以上完成的是本轮指定条目的重核与待审修订。

## 9. 候选条目全文

以下条目均为待审必要条件候选；原正式文件与候选文件均未修改。详细证明在本报告前述分项中。
'''
appendix = ''
for c in all_candidates:
    appendix += f'\n### {c["name"]}\n\n类型：{c["kind"]}。relation：{c["relation"]}。\n\n{c["name"]}：{c["text"]}\n\n    据：{c["basis"]}\n    推导：{c["derivation"]}\n    状态：待审\n'

REPORT.write_text(intro+proofs+bridge+appendix)
payload = dict(report_path=str(REPORT), candidates=all_candidates, summary=summary, status='完成，候选待审')
(OUT/'root_candidates.json').write_text(json.dumps(root_candidates, ensure_ascii=False, indent=2)+'\n')
(OUT/'candidates.json').write_text(json.dumps(all_candidates, ensure_ascii=False, indent=2)+'\n')
(OUT/'final_payload.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'report_path': str(REPORT), 'candidates': len(all_candidates), 'reviewed': len(table)}, ensure_ascii=False))
