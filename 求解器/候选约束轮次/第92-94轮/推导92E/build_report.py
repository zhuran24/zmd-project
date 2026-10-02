#!/usr/bin/env python3
"""Assemble the self-contained report and its structured handoff."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT.parent / '推导92E.md'

def read(name):
    return (ROOT / name).read_text()

def drop_title(text):
    body = text.split('\n', 1)[1].lstrip()
    return '\n'.join('#' + line if line.startswith('#') else line for line in body.split('\n'))

header = '''# 第92轮 E组推导：步进判定带来的必要条件

日期：2026-10-02。状态：完成推导，七条新增必要条件均待审；没有新增简化或充分条件。

步进规则不仅改变启动相位，还对循环态施加容量损失、同单位出货错相和换料间隔限制。本报告提交以下七条；均无面积前提，表中的机型台数和局部结构是各条自己的适用条件。

| 名字 | 主要结论 | 适用条件 |
|---|---|---|
| 分流先判的首段带容量 | q≤8n/(8n+1)；分流器满速时其他支合计≥1/(8n+1) | 分流器实际先于其直连的n格连续传送带判定 |
| 满速分流的断头支层数限制 | 禁止断头支让满速分流器早于唯一活支首段带判定 | 纯运输断头支、唯一正流支；同层情形保留允许组合条件 |
| 满速取货的逐步相位 | 同单位满速取货通道的模8步余数互异 | 平均每tick一件的外部通道；协议核心六路必须错开 |
| 制造取货连续同种段步数界 | 同种段最短步数；按种子各至多一路的采种机≤8/9批/tick | 全部采种机均受该限制时至少18台；非无条件18台 |
| 满载采种双路逐种均分 | 每种种子分别在两路均分 | 全厂恰16台采种，所考察采种机恰两条有通过量取货通道 |
| 研磨单路换主料步数余量 | 8B+W≤NK；32台时所计换料≤4次/tick | 新主料在循环态只经该机一条实际存货通道进入 |
| 接箱末格失败判定收费 | 8N+H≤P；满速循环的成熟拒收次数为零 | 接箱末运输格中的所计物品没有其他去向 |

七条均是新增必要条件，不是对旧正式条目的重核或改写。它们约束每种允许接通先后下的每个可到达循环态；不把有限启动或停收恢复期间的一次延迟判成永久不达标。面积为1110时，若使用快照「面积预算」给出的恰16台采种、32台研磨，则相应的台数特例直接适用；本报告未证明面积1110不存在，也未给出合格布局。

## 前提、记账与证据口径

数学前提只取本轮 `前提快照/` 中的游戏规则、求解任务、求解约束和求解充分条件。没有调用旧充分条件的同时反复判定性质。《不补的设定.txt》只用于识别背景与规则的边界。五份文件的完整SHA-256、行数留在 [快照指纹及满速复核](推导92E/full_rate_checks.json)；游戏规则为115行，游戏规则SHA-256为 `c8d3a17b8830baba18aea36c4c66f02f8873895188f8821176cc218aa6135f93`。

下文一步为1/8 tick，周期均以整数步计。各节的P、K是该节循环周期步数，Q、N、B等件数或批数均在该周期内计；换成每tick速率时乘8再除周期步数。物品在运输格的驻留按每步全部移动结束后的占格状态计，进入步到离开步之间至少有八个这样的状态。桥接器两轴分别计格。

所有程序均为本输出目录中的独立标准库脚本，未导入或修改sim2，也不依赖其已知两处实现问题。局部枚举只复核证明的记账和数值；局部可行时序、边界持续供货和放宽状态图都不是70×70布局证书。

## 一、分流器、首段传送带与断头支

'''

splitter = drop_title(read('splitter/推导.md'))
splitter = splitter.replace('`../../前提快照/`', '`前提快照/`').replace('本报告', '本节')
splitter = splitter.replace('脚本 `check_capacity.py`', '脚本 `推导92E/splitter/check_capacity.py`')
splitter = splitter.replace('在 `capacity_checks.json`', '在 `推导92E/splitter/capacity_checks.json`')
phase = drop_title(read('满速相位.md'))
phase = phase.replace('`check_full_rate.py`', '`推导92E/check_full_rate.py`')
phase = phase.replace('`full_rate_checks.json`', '`推导92E/full_rate_checks.json`')
phase = phase.replace('日期：2026-10-02。状态：推导完成，待审。无面积前提。',
                      '种类：必要条件。面积前提：无。relation：新条目。')
throughput = drop_title(read('throughput/report.md')).replace('三条候选均待审', '本节三条候选均待审').replace('本报告', '本节')
for name in ['check.py', 'check.json', 'check.log']:
    throughput = throughput.replace(f'`{name}`', f'`推导92E/throughput/{name}`')
box = drop_title(read('box/findings.md'))
box = '\n'.join(line for line in box.split('\n') if not line.startswith('- 读者自审已执行：'))
box = box.replace('`../../前提快照/`', '`前提快照/`')
for name in ['check_local.py', 'local_results.json']:
    box = box.replace(f'`{name}`', f'`推导92E/box/{name}`')
box = box.replace('### 可直接提交的必要条件', '### 第七条必要条件（无面积前提，relation：新条目）')
box = box.replace('### 需要明确「一起判定」操作含义后才可提交的桥接器条文',
                  '### 桥接器两种读法：尚未提交为候选的局部推导')
# The bridge calculation is deliberately outside the seven submitted candidates.
bridge_pos = box.find('### 桥接器两种读法：')
if bridge_pos >= 0:
    box = box[:bridge_pos] + box[bridge_pos:].replace('状态：待审。', '状态：语义前提待明确，未提交为候选。')

footer = '''
## 五、证据索引与交付判定

| 文件 | 内容与复核范围 |
|---|---|
| [满速状态图和时间戳复核](推导92E/check_full_rate.py) / [结果](推导92E/full_rate_checks.json) | 单运输格放宽状态图、独立时间戳枚举、满速取货余数的两种计数 |
| [分流器容量复核](推导92E/splitter/check_capacity.py) / [结果](推导92E/splitter/capacity_checks.json) | 两套独立局部编码，128例逐状态、周期和格步计数一致 |
| [取货与换料复核](推导92E/throughput/check.py) / [结果](推导92E/throughput/check.json) | 240对最短段公式与动态规划；4092个种子序列；台数和换料余量双编码 |
| [箱与桥局部复核](推导92E/box/check_local.py) / [结果](推导92E/box/local_results.json) | 时间戳与倒计时两编码；箱相移及桥接器不同判定读法 |
| [箱席交叉审阅](推导92E/box/审阅.md) | 满速相位与分流容量的证明边界 |
| [取货席交叉审阅](推导92E/throughput/independent_review.md) | 接箱失败收费的零流量边界、满速相位及采种均分 |
| [分流席交叉审阅](推导92E/splitter/交叉审阅.md) | 连续同种段、采种均分和研磨换主料 |
| [结构化候选](推导92E/result.json) | 与本报告七条候选对应的短字段交接 |

交付判定：七条全称证明所需的结构、通道、机型台数和实际判定次序前提均已写进条文。相邻桥接器的九步论证因重叠收货组语义尚未明确，未混入这七条。直连汇流器只捡元件阶段留下的空位，可作为逐步检查条件，但尚未由此得到新的无条件机型台数界。

没有证明可以无损删除断头支、移除协议储存箱或把混做改成专机；这些修改可能改变层数、轮询、取货优先级、占地及可到达状态，所以没有提交简化。没有把8/9采种上界推广到每种种子有多条实际出口的机器，也没有把满箱的一步暂态延迟推广成稳态降速。

文件检查通过：七条名称均未与已有条目重名，JSON字段、报告引用和快照指纹一致，详见 [交付检查](推导92E/delivery_checks.json)。所有局部数值复核通过，两两交叉审阅未发现尚未处理的证明缺口。未用局部时序替代全厂布局证书。
'''

REPORT.write_text(header + splitter + '\n## 二、同一非运输单位的满速取货相位\n\n'
                  + phase + '\n## 三、制造取货、采种均分与研磨换主料\n\n'
                  + throughput + '\n## 四、接箱失败、直连汇流器和桥接器边界\n\n'
                  + box + footer)

candidates = [
    dict(name='分流先判的首段带容量', kind='必要条件',
         text='分流器每步实际先于其直连n格连续传送带判定时，该支q≤8n/(8n+1)；分流器满速时其他支合计≥1/(8n+1)。带子仅首格从该分流器收货、末格外送。',
         basis='滞留、步、判定、收货、周期收支。',
         derivation='格步占用同时≥8nQ、≤nP−Q。', relation='新条目；无面积前提。'),
    dict(name='满速分流的断头支层数限制', kind='必要条件',
         text='满速分流器仅一支有正循环流量，活支为m个单向元件、首段是带；断头支k≥2个同类元件。按断支数层时禁k<m；k=m且允许分流器先判也禁。两支均无其他进出口，仅含传送带和未阻断物品准入口。',
         basis='层数、收货、离线、首段带容量。',
         derivation='分流器层k、活支首带层m；先判迫使唯一活支流量小于1。', relation='新条目；无面积前提。'),
    dict(name='满速取货的逐步相位', kind='必要条件',
         text='循环中至少一端接运输单位、平均每tick一件的外部通道有固定模8步余数；同一非运输单位的满速取货通道余数互异，协议核心六路占六个不同余数。',
         basis='通道、滞留、步、判定、取货口配置。',
         derivation='周期满速迫使相邻送货恰隔8步；同单位每步至多送一件。', relation='新条目；无面积前提。'),
]
candidates += json.loads(read('throughput/candidates.json'))
candidates += [dict(name='接箱末格失败判定收费', kind='必要条件',
                    text='周期P步，接箱末运输格出N件；物品无其他去向，成熟后因箱拒收而耗掉唯一判定的次数H满足8N+H≤P。满速循环H=0。',
                    basis='滞留、步、判定、先后、协议储存箱。',
                    derivation='每件占格至少8步，每次成熟拒收另占至少一步；周期容量至多P。',
                    relation='新条目；无面积前提；不排除暂态满箱。')]
result = dict(report_path=str(REPORT), candidates=candidates,
              summary='推出7条新增必要条件，均待审；未提高无条件机型下限或空矩形上界，桥接器歧义另列。',
              status='完成推导，待审', error='')
(ROOT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report_path': str(REPORT), 'candidates': len(candidates)}, ensure_ascii=False))
