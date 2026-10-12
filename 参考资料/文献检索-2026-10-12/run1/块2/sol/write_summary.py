#!/usr/bin/env python3
"""Prepend the requested stand-alone block summary and complete query ledger."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / '证据.md'
body = path.read_text()
if '## 本块小结' in body:
    headline = body.split('\n', 1)[0]
    body = headline + '\n\n用途：' + body.split('\n用途：', 1)[1]
queries = [json.loads(x) for x in (ROOT / 'queries.jsonl').read_text().splitlines() if x.strip()]
count = sum(x.startswith('- [') for x in body.split('## 文献证据', 1)[1].splitlines())
summary = f'''## 本块小结

找到了用于本块的状态表示、全周期产率证书、启动/返回定理和瞬态界。最直接的路线是：**完整运行状态图上的两个负环检查 + 允许粗粒度操作的全初态启动验证**。堵满起法与blocking marking关系紧密，但其适用条件、自动收敛和多个末级同时关闭仍需本题证明；本轮没有找到可不经建模核对就保证整个游戏布局达标的定理。

**领域与数量。** 实际覆盖七类领域：形式化/定量验证与游戏；制造系统/Petri网/监督控制；离散事件/max-plus与min-max；分布式自稳定/同步；组合动力学/rotor-router/交换网络；非竞争化学反应网络；交通流/排除过程/元胞自动机。留下 **{count} 项文献**；书与其home-markings章节合并计一项，同一rotor-router预印本/会议版只计一项。明显不适合的同词异义、空间回返、随机期望、递归栈及通用背景候选保留筛选记录；对拿不准而可能提供本块方法的文献仍写证据，并标明待核。候选元数据在 `pool.jsonl`，`screening=retained` 的记录指向本文件证据编号；去重前原始数据在 `pool.raw.jsonl`。

**最可能有用的五项。**

- [Karp 1978](https://doi.org/10.1016/0012-365X(78)90011-0)：把“每个可达循环都达标”变成两次最小均值/负环检查，直接服务候选L的证书器。
- [Gaujal–Haar–Mairesse 2003](https://arxiv.org/abs/0707.4372)：给“关服务、积料到唯一堵塞标识”精确定理入口，最贴近堵满起法，但需核对自由选择与单变迁条件。
- [Pocci等 2013](https://arxiv.org/abs/1307.2427)：同一同步输入序列把全部未知初态送到目标，是开关调试方案的直接形式化工具。
- [Bouillard–Gaujal–Mairesse 2006](https://doi.org/10.1007/s10626-006-9326-y)：定时路由网状态必须含物料、时间、游标，且最坏吞吐可由非0–1的周期策略实现，防止只查简单调度。
- [Gaubert–Gunawardena 1998](https://doi.org/10.1016/S0764-4442(97)82710-3)：若模块准确落入min-max递推，可证明不同初相位具有同一长期斜率，比要求唯一库存周期更弱也更有希望。

补查还得到两个直接研究循环生产启动/切换的来源（Korbaa等1999、Bourdeaud'huy等2011）、以初始WIP决定满负荷生产的Hillion–Proth1989、以及带权双模拟和交通堵塞几何表示；它们的控制/更新语义差异见各条。

**自动引用链种子与补做情况。** 初轮已完成，不是手工替代；额度更新后使用新版 `lit.py` 自动带key，重新扩展新领域种子。引用链取所有参考文献和前100篇施引，按工具规则选择候选；新增数为各轮写入pool时的数，之后又统一去重筛选。

| 轮次 | 种子（标识与简称） | 新写入候选 | 记录 |
|---|---|---:|---|
| 初轮，8种子 | Karp `10.1016/0012-365X(78)90011-0`；Blocking `arXiv:0707.4372`；同步PN `arXiv:1307.2427`；并行rotor `arXiv:1407.3200`；Abelian I `arXiv:1309.3445`；MPL瞬态 `arXiv:1111.4600`；Dijkstra `10.1145/361179.361202`；Generalized MP `10.4230/LIPIcs.FSTTCS.2010.505` | 50 | `chain.log` |
| 聚焦轮，5种子 | Blocking、同步PN、并行rotor、Abelian I、MPL瞬态（上述相同标识） | 33 | `chain_focus.log` |
| 额度更新后补做，8种子 | 启动调度 `W1480872605`；周期切换 `W2130730283`；交通初态几何 `arXiv:2602.08991`；带权双模拟 `W1959886368`；晶圆启动 `W2884307365`；Extremal throughput `10.1007/s10626-006-9326-y`；min-max duality `10.1016/S0764-4442(97)82710-3`；MPL形式验证 `arXiv:2308.10587` | 34 | `chain_after_key.log` |

补做链的新候选逐篇筛选后，正文另外留下了job-shop初始WIP、lot switching、非扩张/单调映射、彩色资源PN死锁和deadlock/starvation/blocking等来源。新增OpenAlex检索用了12次（获准新增最多15次）；最初使用4次。补查开始时本席隔离缓存仍记旧额度，四个查询先自动回退arXiv；刷新本席旧预算缓存后这四个词也已在OpenAlex补查，来源分别记在下表。

**未找到满足本题口径的方面。**

- 对“容量1、成功才转指针、跳过无可移动输入、配方批加工、固定隐藏级别”同时成立的转子/交换网全周期同速定理，未找到；检索包括 `finite capacity rotor router blocking`、`rotor-router backpressure finite capacity`、`bounded rotor-router capacity`。现有rotor结果主要无容量/无背压，交换网须先检验局部公理。
- 对整个堵满方案、多个末级同时关闭、任意足够长等待、再一次全部打开的全初态保证，未找到可直接应用的结果；查了blocking/home cluster、同步PN、cyclic-production transient、晶圆start-up。结果多证明“存在可选择序列”，或要求精确控制，未解决R2/R4的自动运行量词。
- 对合并/删除内部步后仍保两个交付数与时间分母的现成mean-payoff偏序约简，未核实；查了 `mean-payoff partial order reduction`、`partial order reduction quantitative mean payoff`、`weighted transition systems partial order reduction`。找到带权双模拟候选及定性POR论文，但没有核实其直接保本题产率的条件。
- 对有限缓存生产线的“所有确定性周期”统一启动/吞吐界，新增查询主要返回Markov故障、溢出时间分布或期望性能；这类量词不足以支持R6。交通元胞自动机给初态几何和消退表示，但并行更新、闭路和守恒条件不同。

**全部实际查询及来源。** 下表逐条记录实际调用；“web”为网页搜索，论文事实最终采用原论文/作者稿/出版社或OpenAlex摘要。开放全文用供给的 `full` 获取，失败后尝试作者/机构PDF，不注册、不付费；下载器上限99 MB。脚本、缓存与文档均在本席输出目录；研究仓库只读。

| # | 来源 | 查询词（原样） | 阶段 |
|---:|---|---|---|
'''
source_names = {'web': '网页搜索', 'openalex': 'OpenAlex / lit.py', 'arxiv': 'arXiv / lit.py', 'crossref': 'Crossref / lit.py'}
for i, query in enumerate(queries, 1):
    text = query['query'].replace('|', '\\|')
    summary += f"| {i} | {source_names[query['source']]} | `{text}` | {query.get('phase', '首轮')} |\n"
summary += '\n'
headline, remaining = body.split('\n', 1)
path.write_text(headline + '\n\n' + summary + remaining.lstrip('\n'))
