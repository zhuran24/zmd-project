#!/usr/bin/env python3
"""Assemble the reviewed report and validate the requested candidate schema."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
SNAP = ROUND / '前提快照'
REPORT = ROUND / '推导92C.md'

source = (SNAP/'求解充分条件.txt').read_text().splitlines()
original = []
for i, line in enumerate(source):
    if line and not line.startswith(' ') and '：' in line:
        name, txt = line.split('：', 1)
        original.append((name, txt, source[i+1].strip(), i+1))
assert len(original) == 11

root = (HERE/'s01_s05.md').read_text()
name02 = original[1][0]
text02 = re.search(r'^'+re.escape(name02)+r'：(.*)$',root,re.M).group(1)
candidates = [dict(name=name02,kind='充分条件',text=text02,
    basis='快照规则13、17—18、23—33、36及配方。',
    derivation='补来料只含A、B；前缀归纳排除永久互等，详见报告S02。',
    relation=f'修订正式条目「{name02}」')]
candidates += json.loads((HERE/'s06_s07_candidates.json').read_text())
candidates += json.loads((HERE/'s08_s09_candidates.json').read_text())
candidates += [json.loads((HERE/'s10_candidate.json').read_text())]
required = {'name','kind','text','basis','derivation','relation'}
assert len(candidates) == 6
assert len({c['name'] for c in candidates}) == 6
for c in candidates:
    assert set(c) == required and c['kind'] == '充分条件'
    assert c['name'] in [x[0] for x in original[:10]]
    assert c['relation'] == f'修订正式条目「{c["name"]}」'
    assert all(isinstance(v,str) and v for v in c.values())

reasons = {
    1:'计数器与真实箱逐动作耦合；恢复传输后容量余量足够。',
    3:'配方开批保持加权库存差，比例段把它限制在危险区间之外。',
    4:'周期逐边相加，节点势的边界项消去。',
    5:'两种首件均收不下只能是两格各满50，已经够一批。',
}
for number in [1,3,4,5]:
    name, txt, basis, _ = original[number-1]
    marker = re.search(r'^## S'+str(number).zfill(2)+r' .*?\n\n判定：.*?\n',root,re.M)
    assert marker
    pos = marker.end()
    block = (f'\n条目（原文保留）：\n\n{name}：{txt}\n'
             f'    {basis}\n    推导：{reasons[number]}完整核对见本节。\n    状态：待审。\n')
    root = root[:pos]+block+root[pos:]

def local_links(text):
    return re.sub(r'\]\((s[^()/]+\.(?:py|json|md|log))\)',r'](推导92C/\1)',text)

parts = [root]
for filename, first in [('s06_s07.md','## S06—S07 多取货通道复核'),
                        ('s08_s09.md','## S08—S09 采种单元复核'),
                        ('s10.md','## S10 专用进路下缓存格不空的传递')]:
    text = (HERE/filename).read_text()
    lines = text.splitlines()
    lines[0] = first
    for j in range(1,len(lines)):
        if lines[j].startswith('##'):
            lines[j] = '#'+lines[j]
    parts.append('\n'.join(lines))

head = '''# 第 92 轮 C 组：10 条充分条件的步进复核

日期：2026-10-02。状态：复核完成，6 份修订候选待审。4 条确认保留，6 条改写；S08 的原有一般拓扑、S09 的原有生产性强结论仍未解决。没有认证一张达标全厂布局。

## 结论表

所有条目的类型均为**充分条件**：满足所列前件才保证对应效果。本报告没有新增必要条件，也没有提出不丢最优的简化。“全厂专用进路接法达标”不在本轮范围内。

| 编号 | 正式名字 | 判定 | 本轮可用结论与边界 |
|---|---|---|---|
| S01 | 协议储存箱单种非成品保格 | 确认成立 | 逐动作计数器耦合有效；恢复后每40步最多新收15件成品。 |
| S02 | 单条混料进路逐件判据 | 改写 | 明确全部来料只含两种配方原料；前缀归纳保证逐件有限时间收下。 |
| S03 | 多条混料进路按配方比例分段 | 确认成立 | 加权库存差的不变量不依赖同刻重试。 |
| S04 | 调试期后状态图交付核验 | 确认成立 | 势函数证明保留；旧状态图须重新证明覆盖新步进。 |
| S05 | 双料机器各原料专用进路 | 确认成立 | 两种首件均拒收迫使两格满；排除所述库存死锁。 |
| S06 | 整批k件配k条取货通道的均分 | 改写 | 旧逐刻全取结论有反例；新增同级与恰8步清首格前提后，成功序轮转、流量均分。 |
| S07 | 植物专机一一配对满库存不断料 | 改写 | 同步补回被否；保留第0—399步的缓存、库存和有限回填保障，无限期未证。 |
| S08 | 采种单元的回路存量下界 | 改写 | 限纯传送带、合法完整步末，重证 Φ≥min(Φ(s)−1/2,L1+L2+176)；原一般拓扑未决。 |
| S09 | 采种单元不断料 | 改写 | 限纯带并要求K粉末逐件有限清出，保证无限开批与循环共同正批率；原满速等强结论未证。 |
| S10 | 专用进路下缓存格不空的传递 | 改写 | 原主结论有静止循环反例；补格内物品限制、单出路来源、无桥进路后证明步末缓存不空。 |

“改写”不等同于每个旧子结论均已否证：S02、S06、S07、S10 给出规则内反例击穿原条文；S08、S09 则提交已完成证明的收窄版本，原范围明确保留未决。S07 的400步是库存保底期限，并非断言闭环在第400步一定耗尽。

## 前提、观察时点与程序口径

前提只取本轮[游戏规则快照](前提快照/《明日方舟：终末地》游戏规则.txt)、[求解任务快照](前提快照/求解任务.txt)、[必要条件快照](前提快照/求解约束.txt)和[充分条件快照](前提快照/求解充分条件.txt)。根目录同名文件不作为依据；“不补的设定”未作为证明前提。旧清点和旧推导只帮助定位问题，用到的论证均在正文重证。

每步依次结束到时制造、完成各次判定、开始能开始的制造。正文新候选的“步末”均指三个阶段全部完成；制造中的原料也在缓存内，不能把模拟器 `running` 与 `cache=[]` 误读为游戏缓存空。每次非运输单位判定至多向外送一件，整批缓存入取货格仍按批量检查空间；二者不是同一件事。

所有结论都按其前件覆盖离线可能改变的接通先后。没有把有利的同层顺序、轮询起点或分流选支固定下来充当普遍证明。S08/S09 的修正版排除桥接器，S10 排除桥接器但保留不限额准入口；现行与拟改桥接器条文对这些版本结论相同。S07 的有限库存保证不依赖沿路满速，其首格保证另有独占和可接收前件；S06 的新增服务前件须分别核实。原先允许的桥接器一般范围没有被这几份证明认证，拟改读法也不能自动补齐证明。

程序及逐步证据均在[推导92C目录](推导92C/)。sim2 只读使用，原模块另存为[sim2_reference.py](推导92C/sim2_reference.py)，哈希见[实现记录](推导92C/sim2_reference.json)。S10 反例在自己的脚本内补 `Machine.flush` 的同种唯一检查；没有修改原模拟器。其余正式证据选用不触及该错误及“按元件而非单位检查刚离开者”错误的构型。有限枚举、局部边界模型与真正规则内反例在各节分别标明。

## 快照校验

'''
hashes = json.loads((HERE/'s01_s05_results.json').read_text())['snapshot_hashes']
for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','求解充分条件.txt']:
    assert hashlib.sha256((SNAP/name).read_bytes()).hexdigest() == hashes[name]
    head += f'- `{name}`：`{hashes[name]}`\n'

tail = '''

## 复现、交付与审查记录

候选机器可读版本见 [candidates.json](推导92C/candidates.json)，转发层结构化结果见 [reply.json](推导92C/reply.json)。文件校验见 [validation.json](推导92C/validation.json)，产物哈希见 [artifact_manifest.json](推导92C/artifact_manifest.json)。原条目和候选文件均未改写。上述反例用于复核局部充分条件，不冒充同时满足全部77条必要条件的达标全厂见证；误料反例与可用台数约束的关系已在 S02、S10 明示。

主要程序从项目目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python -B 求解器/候选约束轮次/第92-94轮/推导92C/s01_s05_checks.py
PYTHONDONTWRITEBYTECODE=1 python -B 求解器/候选约束轮次/第92-94轮/推导92C/s06_s07_verify.py
PYTHONDONTWRITEBYTECODE=1 python -B 求解器/候选约束轮次/第92-94轮/推导92C/s08_s09_independent.py
PYTHONDONTWRITEBYTECODE=1 python -B 求解器/候选约束轮次/第92-94轮/推导92C/s10_check.py
```

S08 的独立核验脚本将结果打印到标准输出，对应存档为 `s08_s09_independent.json`。其他三个主核验脚本在自己的目录写结果。各项关键数字由两套编码或独立状态表核对；枚举只检查实现和小构型，全部布局的结论依赖正文的证明。

交付前审查已经核对：10 条覆盖且没有纳入 S11；4 条保留、6 条修订与结构化结果一致；候选名字沿用正式名字、类型全部为充分条件；400步边界、Φ的176常数及1/2余量、步末观察截面一致；来源不明的4/6/5线索及虚拟接收边界均未充当布局反例；相对文件链接有效。S01—S05 与 S08 的承重论证另经独立席位审读，S07 库存下界已补成显式计数不等式。

未完成的部分是证明边界，不是计算超时：S07无限期库存保底、S08允许桥接器和准入口的一般原范围、S09原有的缓存连续非空/逐刻出口/满速断言、S10多出路及桥接器的原一般范围。这里的修订不能作为这些旧强结论的替代引用。没有运行内核 cargo 测试，没有操作 git；写入限于本报告与同名证据目录。
'''
report = head+'\n\n'+'\n\n'.join(local_links(x) for x in parts)+tail
REPORT.write_text(report)
(HERE/'candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2)+'\n')
reply = dict(report_path=str(REPORT),candidates=candidates,
    summary='S01、S03、S04、S05确认成立；S02、S06、S07、S08、S09、S10改写。S07仅保前50tick，S08保纯带强界，S09降为无限开批；原强结论未决处见报告。',
    status='完成，候选待审')
(HERE/'reply.json').write_text(json.dumps(reply,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report_path':str(REPORT),'report_bytes':REPORT.stat().st_size,
                  'candidate_count':len(candidates),'confirmed_count':4},ensure_ascii=False))

# The temporary-rule supplement is authoritative once created. Keep the first
# snapshot delivery archived, and do not accidentally publish its candidates.
if (HERE/'apply_temporary_rules.py').exists():
    import runpy
    runpy.run_path(str(HERE/'apply_temporary_rules.py'),run_name='__main__')
