# 分流网络、约束综合与验证的引用链核查

核查日期：2026-10-12。范围：分流网络、约束综合与验证的引用外延。L 指经规则逐步内核验证的合格布局；U 指目标最大空矩形面积的已证上界。下面的迁移建议尚未实施或获得本题运行证明。

## 本链小结

留下 6 条已阅读文献证据，另有 1 条既有 Splitter Networks 桥接记录；pool 共 8 条，额外 1 条基础设施图论论文仅作待筛候选，不计入已阅读文献。链条跨游戏自动化、形式化验证、运筹学等流量网络、微流控混合图和电话交换互连网络。全部真实执行的查询词和来源见末尾查询表；预备检索词不计作已执行查询。

引用链种子是 Splitter Networks（DOI:10.4230/LIPIcs.FUN.2024.9）和 Leue 2021（DOI:10.26083/tuprints-00017621）。Blueprints（arXiv:2310.01505）仅核其 §1/[9] 指向 Leue。对 Splitter 单独跑 `chain --top 25` 新进 0 篇；OpenAlex 对该正式版记录的参考文献和施引计数均为 0，所以直接核正式出版商列出的参考书目扩展，不能把 API 的空记录解释为没有引用。

最值得试的四条是：Leue 的模块接口与显式轮转状态可帮助小窗口的全状态验证，但需重写终末地转移语义；Chandler/Davidrajuh 的容量加轮询仿真可做 L 的管线瓶颈初筛，但其模型明确近似且未验证；Meyers/Schulz 的等流量弧集 LP/IP 是抽象拓扑的候选表示，适用前须证明哪些出口真的均分；Coviello Gonzalez/Chrobak 的混合图构造给出先造线性分配网络再嵌入格子的外延，三路轮询与反压的迁移尚未成立。Beneš 的可重排互连只提供拓扑模板，本题固定配置不享有其动态重排保证。

未找到带 DOI/arXiv 的专门 Factorio-SAT 布局论文：查询 `Factorio conveyor belt balancer SAT paper splitter networks`、`"Factorio" "SAT" paper balancer synthesis` 主要落到 R-O-C-K-E-T 的实现和社区说明。找到了主源实现，但不把它伪装成学术论文。Knuth–Yao 方向已由 Splitter 参考书目 [13] 确认，其原书章未在本次短链内取得可用 DOI/arXiv/OpenAlex 标识，未形成证据行。Parmar 学位论文只命中二手聚合和 CiteSeer 副本，未核到学校主源及所需标识，仍作为后续可查线索。

## 研究问题与预备检索词

1. 游戏中的分流网络能否从抽象拓扑综合为紧凑格子布局？游戏自动化：Factorio SAT belt balancer、conveyor splitter synthesis、blueprint constraint programming。
2. 满容量时的公平流分配可借用哪些网络优化定理？网络优化：equal-flow networks、maximum flow with side constraints、balanced flow、fair flow。
3. 保证所有运行都均衡的验证方法是什么？形式化验证：Petri net belt balancer、linear temporal logic throughput、model checking conveyor networks。
4. 指定比例的分流网络有哪些复杂度或构造界？随机计算与开关网络：Knuth Yao discrete distribution、rational stochastic flow network、probabilistic switching circuit。

## 查询与引用链日志

- 网页搜索：`Factorio conveyor belt balancer SAT paper splitter networks`、`"Splitter Networks" references`。命中 arXiv:2404.05472、Factorio-SAT 主源实现、arXiv:2310.01505；未把 Reddit 等二手讨论当论文证据。
- 主源页面：arXiv:2310.01505 全文 HTML 的 §1 明确引用 Leue 的 Petri-net/LTL belt-balancer 验证工作；§2 给出布局/布线外延。Splitter 主结果不重读，只核参考文献。

## 文献证据

- [DOI:10.26083/tuprints-00017621] Andre Leue 2021，Verification of Factorio Belt Balancers using Petri Nets（TU Darmstadt 本科学位论文；以学校元数据为准，另两篇的参考文献误写为硕士/博士）。
  解的问题：把一张既有 belt balancer 分解成 Petri-net 模块，定义均衡、吞吐不受限及 universal 等性质，并尝试自动验证。
  方法：生成、传输、分流、消费模块；用显式 token 保存分流优先/交替状态；性质写为 LTL，转换为 PROMELA。
  规模：§7 的 4→4 示例为 296 个 places、271 个 transitions，超过该翻译当时 SPIN 的 256 个 process/channel 编号上限；论文明确未完成合理规模实例自动验证。
  对应本题：规则原句“元件轮询：按接通先后循环，从上次成功的下一条开始”可对应模块内轮转状态；全运行性质可沿模块化状态表示来写。
  不对应的：本文 Factorio 的 2入2出 splitter 和抽象传输模块不保留本题 1入3出、3入1出、逐格滞留与八步判定时序；LTL 均衡也不是本题带阈值的长期平均收益。
  对本题有什么用：L 的验证表示备选：在小窗口把每格占用、物品年龄、轮询指针、连接次序和机器缓存建成状态机，再检查循环产出；只借模块接口，不能把此论文的验证结论视为布局达标。
  依据：全文 §1 p.4、§5.4 pp.35–36、§6 pp.39–45、§7.4 p.49；[学校 DOI 页面](https://tuprints.ulb.tu-darmstadt.de/entities/publication/8881c046-1cf2-40c7-a528-04c6069739ce)，[开放全文](https://d-nb.info/123465766X/34)；本地 leue2021.pdf / leue2021.txt。
  引用方向：Splitter Networks 正式版参考文献 [15] → Leue；Blueprints arXiv:2310.01505 §1/[9] → Leue；lit.py chain 返回 Chandler/Davidrajuh 2024 施引，且后者全文 §1.2/[5] 复核。

- [DOI:10.3390/electronics13071377；W4393994034] Benjamin Alexander Chandler、Reggie Davidrajuh 2024，Modeling and Analyzing the Strategy Game “Factorio” Using Modular Petri Nets and the General-Purpose Petri Net Simulator（Electronics 13(7),1377）。
  解的问题：以模块化 Petri nets 模拟 Factorio 生产管线，并比较产量、能耗、污染评分。
  方法：四个生产模块与模块间连接器；GPenSIM 的 COMMON_PRE 检查 belt token 容量，COMMON_PRE/POST 执行 splitter 轮转；仿真比较配置。
  规模：四个生产模块；论文不提供模型全部 places/transitions 数，不声称验证全状态空间。
  对应本题：规则原句“运输单位：除桥接器外只有一个物品格，每个物品格上限 1”可映为容量 place；“配方时长过后结束”可映为定时 transition；轮询状态可由前后处理器记录。
  不对应的：§6.1 明确 belt 吞吐仅为近似、同一模块的机器集体受 firing 条件限制；本题机器逐台按配方开工。§6.2 明确未验证模型；故模拟分数不能满足每个可达循环态要求。
  对本题有什么用：L 候选管线的低成本分模块筛选和瓶颈定位；可替换“凭静态配方数猜瓶颈”的初筛，不能替换严格逐步内核，也不能用于 U 不可行性证据。
  依据：全文 §3.3 p.7、§4.2 pp.8–9、§6.1–6.2 p.17；[出版商页面](https://www.mdpi.com/2079-9292/13/7/1377)，[出版商 PDF](https://mdpi-res.com/d_attachment/electronics/electronics-13-01377/article_deploy/electronics-13-01377.pdf?version=1712308624)；本地 factorio_pet2024.pdf / factorio_pet2024.txt。
  引用方向：该文 §1.2 与参考文献 [5] → Leue 2021；既有游戏验证向模块化离散事件模拟扩展。

- [DOI:10.1016/j.orl.2009.03.006] Carol A. Meyers、Andreas S. Schulz 2009，Integer equal flows（Operations Research Letters 37(4),245–249）。
  解的问题：最大流中指定若干互不相交的弧集合，每集合的弧流量相等且为整数；研究可近似性和特殊情形。
  方法：§2 给出守恒、容量、同组等流量约束的 LP/IP；给出 LP 有正流但 IP 仅零流的反例；固定等流量组数时为多项式可解。
  规模：理论复杂性论文，未给本题规模的求解实验。
  对应本题：可把有严格均分保证的物流子模块的出口组成等流量弧集；一个确定周期内的通过件数是整数。固定期长下可与机器配方的整数批量约束连接。
  不对应的：本题长期率是有理数，期长未知；输出堵塞时轮询流量未必相等。等流量不包含空间占用、滞留、批量时序，整数困难性不等于本题困难性。
  对本题有什么用：L 的抽象物流网络综合表示：先用连续守恒/容量和已证明的分配比例找拓扑，再落地验证。U 只能用确已证明对全部目标布局成立的等流量约束；禁止把“想均分”当必要条件。LP 可行不作为可运行布局证明。
  依据：作者公开全文 §1–2 pp.1–3、末节特殊情形；[作者 MIT 全文](https://web.mit.edu/schulz/www/epapers/meyers-schulz-august-2008.pdf)，[机构元数据及 DOI](https://portal.fis.tum.de/en/publications/integer-equal-flows)；本地 meyers_schulz2009.pdf / .txt，开放稿 2008、正式出版 2009。
  引用方向：Splitter Networks 正式版参考文献 [17] → Meyers/Schulz；其 §1/[17] → Srinathan 2002（本文已从参考书目确认）。

- [DOI:10.1007/3-540-45655-4_55] K. Srinathan 等 2002，Theory of Equal-Flows in Networks（COCOON 2002，LNCS 2387,514–524）。
  解的问题：除源点外，每个点出弧的流量必须相等且为整数的最大流变体。
  方法：证明 NP-hard，给近似算法并讨论传统流理论的等流量对应物。
  规模：仅核出版商摘要；没有核到实验规模或近似比，故不填。
  对应本题：未阻塞时轮转分配的流量约束、供应链 Bill-of-Demand 式固定比例与配方资源展开相关。
  不对应的：本题“分流器：大小1x1，任意一条边为存货端口、其余三条边为取货端口”是按成功移动的轮询；这不推出每个出口任意运行均等。整数静态流也没有每格容量及时序。
  对本题有什么用：L 的均分子网络约束术语与复杂性边界；先给某类已证明无阻塞、固定周期模块建立流模型。暂不作为 U 上界或具体求解器的建议。
  依据：仅[出版商摘要及 DOI](https://link.springer.com/chapter/10.1007/3-540-45655-4_55)；主源全文为订阅内容，未注册或付费。
  引用方向：Splitter Networks 参考文献 [23] → 本文；Meyers/Schulz 2009 §1/[17] → 本文。

- [DOI:10.1016/j.tcs.2020.09.007；arXiv:1806.08875] Miguel Coviello Gonzalez、Marek Chrobak 2020，Towards a theory of mixing graphs: A characterization of perfect mixability（Theoretical Computer Science 845,98–121；arXiv v4,2019）。
  解的问题：给一组二进有理浓度的液滴，判断能否仅用每次二入二出取均值的混合器，令所有输出浓度都等于输入均值。
  方法：完美可混合性的必要充分刻画；可在多项式时间判断并构造多项式大小 DAG。一般指定目标 mix-reachability 复杂度仍未解决。
  规模：输入位长的理论多项式界；未报告 70×70 或真实布局规模。
  对应本题：可作为“抽象分流网络先构造，再嵌入格子”的组合构造外延；平衡来自局部平均/线性变换，而不是逐格搜索。
  不对应的：混合器改变物理浓度并同步产生两滴，不是单件物品保留身份的三路轮询；无容量反压，也无二维长度/桥接代价。其二进浓度障碍不能直接套到本题可有循环的三分流网络。
  对本题有什么用：L 的模块库生成思路：在另行证明本题某子模块实现相同线性变换后，借 DAG 构造生成配比分配拓扑；当前仅候选构造外延。不能拿可混合性定理直接抬 U 或认证产量。
  依据：作者稿全文 §1–2 pp.1–5、§6–7 多项式构造；[出版商正文](https://www.sciencedirect.com/science/article/pii/S0304397520305065)，[arXiv](https://arxiv.org/abs/1806.08875)；本地 mixinggraphs.pdf / .txt。
  引用方向：Splitter Networks 正式版参考文献 [7] → 本文；核的是实际参考书目，非名称相似推断。

- [DOI:10.1002/j.1538-7305.1964.tb04102.x] V. E. Beneš 1964，Permutation Groups, Complexes, and Rearrangeable Connecting Networks（Bell System Technical Journal 43(4),1619–1640）。
  解的问题：多级方形交叉开关网络何时可以通过重新选路实现任意输入—输出置换。
  方法：置换群与组合表示，提出和示范可重排网络的充分条件。
  规模：本次只核出版商摘要，未核元件数定理或空间实现规模。
  对应本题：物流端口之间的可连接拓扑可与多级互连网络比较；可用模块化网络替代整张格图一次综合。
  不对应的：可重排允许运行时重新选择路由；本题“建好、调试完以后就不再动”的固定布局里没有可控交叉开关。置换互联不等于固定轮询均衡或所有周期吞吐保证。
  对本题有什么用：L 的拓扑模板来源与分级端口组织的参考；必须提前冻结所有开关/路由并经本题内核验证。不能凭“rearrangeable”声称是本题 universal balancer。
  依据：仅[出版商摘要与参考文献](https://onlinelibrary.wiley.com/doi/abs/10.1002/j.1538-7305.1964.tb04102.x)；全文未取到。
  引用方向：Splitter Networks 正式版参考文献 [2] → Beneš 1964；Beneš 1964 参考文献 [1] → Beneš 1962 On rearrangeable three-stage connecting networks（DOI:10.1002/j.1538-7305.1962.tb03990.x；仅桥接，未再精读）。

## 既有工作与非学术桥接

- [DOI:10.4230/LIPIcs.FUN.2024.9；arXiv:2404.05472；W4394673243] Couëtoux、Gastaldi、Naves 2024，The Steady-States of Splitter Networks。既有工作，不重读稳态定理；本次仅核[正式出版商参考书目](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.FUN.2024.9)的 [2] Beneš、[7] mixing graphs、[15] Leue、[17] Meyers/Schulz、[23] Srinathan、[21] Factorio-SAT，作为真正引用方向的证据。出处中的学位类型错误由学校主源校正。
- [Factorio-SAT 主源实现](https://github.com/R-O-C-K-E-T/Factorio-SAT)：README 的 How it works 说明每格编码方向、地下状态、splitter 侧/ID、颜色；固定抽象 splitter network 的端口颜色后，由 SAT 排布实现。Caveats 明确无编码符合 Factorio 规则的证明，并假设外部输入/输出由 splitters 覆盖。它可以给 L 的“抽象拓扑→窗口 SAT 布置”工程原型，但要替换为本题 1×1 三路分流/汇流与桥接器编码，再由规则内核验证；不能凭该编码 UNSAT 认证本题 U。不计学术文献数或 pool 论文记录。

## 全部已执行查询及来源

以下 12 个检索查询均使用网页搜索；命中论文后只使用出版商、学校仓库或作者/arXiv 全文作结果证据。未执行 OpenAlex search。

| 查询词 | 来源 | 直接目的或结果 |
|---|---|---|
| `Factorio conveyor belt balancer SAT paper splitter networks` | 网页搜索 | 找到 Splitter、Factorio-SAT、Blueprints 等入口 |
| `"Splitter Networks" references` | 网页搜索 | 定位正式论文与参考文献方向 |
| `"Verification of Factorio Belt Balancers using Petri Nets" Leue` | 网页搜索 | 学校论文 DOI、开放全文；命中 Chandler 施引 |
| `"Factorio" "SAT" paper balancer synthesis` | 网页搜索 | 实现与社区资料；未找到专门 SAT 学术论文 |
| `"The steady-states of splitter networks" "References" Knuth Yao` | 网页搜索 | 定位正式出版商参考书目 |
| `"Integer equal flows" Meyers Schulz doi` | 网页搜索 | MIT 作者全文与机构 DOI 元数据 |
| `"Theory of equal-flows in networks" DOI` | 网页搜索 | 题名与 DOI 线索，随后核 Springer 主源 |
| `"Towards a theory of mixing graphs" perfect mixability` | 网页搜索 | 出版商正文及 arXiv:1806.08875 |
| `"On rearrangeable three-stage connecting networks" DOI` | 网页搜索 | Beneš 1962 DOI，仅桥接 |
| `"Theory of Equal-Flows in Networks" Srinathan Goundan Kumar Springer` | 网页搜索 | Springer 主源摘要 |
| `"Integer programming approaches for equal-split network flow problems" Parmar` | 网页搜索 | 缺学校主源及论文标识，未作证据行 |
| `"Permutation groups, complexes, and rearrangeable connecting networks" DOI` | 网页搜索 | Beneš 1964 出版商摘要与引用 1962 的方向 |

引用链调用记录：

1. `lit.py refs arXiv:2404.05472 --pool sat_pool.jsonl`：新进 0 篇。
2. `lit.py chain 10.4230/LIPIcs.FUN.2024.9 10.26083/tuprints-00017621 --pool sat_pool.jsonl --top 20`：新进 W4393169405（Using Graph Theory to Investigate the Role of Expertise on Infrastructure Evolution: A Case Study Examining the Game Factorio）和 W4393994034（Chandler/Davidrajuh 2024）。W4393169405 为待筛候选，未以题名推断其有无实际方法贡献；W4393994034 已用全文 §1.2/[5] 复核施引 Leue。
3. `lit.py chain 10.4230/LIPIcs.FUN.2024.9 --pool sat_pool.jsonl --top 25`：新进 0 篇；对应 OpenAlex W4394673243 的 `referenced_works` 长度 0、`cited_by_count` 为 0。由正式出版商参考书目手工扩展；不是重复阅读已查工作，也不据空列表筛掉可能的外延。
4. 六个 DOI 单篇解析到 OpenAlex 标识以补 pool 元数据；不消耗检索次数。lit.py 在内存执行，`__file__` 指向输出目录，使缓存落到本目录 cache，没有修改原工具或仓库。

## 本地全文

- Leue：`leue2021.pdf` / `leue2021.txt`（6.68 MB PDF，来源德国国家图书馆公开存档）。
- Chandler/Davidrajuh：`factorio_pet2024.pdf` / `factorio_pet2024.txt`（9.79 MB PDF，出版商）。
- Meyers/Schulz：`meyers_schulz2009.pdf` / `meyers_schulz2009.txt`（0.15 MB PDF，MIT 作者页面，2008 开放稿）。
- Coviello Gonzalez/Chrobak：`mixinggraphs.pdf` / `mixinggraphs.txt`（0.91 MB PDF，arXiv v4,2019；正式出版 2020）。
- Srinathan 与 Beneš 1964：未取得全文，证据明确仅基于出版商摘要。
