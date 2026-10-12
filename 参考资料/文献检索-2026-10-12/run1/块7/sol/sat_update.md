# 分流网络与约束综合引用链补查

核查日期：2026-10-12。追加 OpenAlex 检索使用 2 次；只列本次新增候选，不重复阅读已查 Splitter Networks。

## 补查小结

追加 2 次 OpenAlex search 未找到新的 Factorio SAT 或 shapez 专门论文；等流量网络种子的引用链新进 24 条，形成 4 条有主源依据的新增证据：全局 flow 约束（仅摘要）、增益加等流量网络单纯形（全文）、多场景一致流（全文）、拉格朗日松弛与可行流恢复（作者上传稿相关节）。这些主要用于 L 的物流骨架、窗口修复和场景筛选；没有一条能直接认证本题 U 或全部循环态吞吐。

最可操作的两个点是：将接口均分与带容量物流分开，在普通最小费用流上反复修复；将单输入倍率配方表示为增益弧，再把联合配方与时序保留在外部模型。两者均须由终末地规则逐步内核验证。稳健网络的自由弧可随场景调整，不能误当作固定布局的全运行保证。

pool 共26条，全部完成题名/摘要筛选：4条较详证据、16条摘要层证据、2条仅书目保留、3条无关筛除、1条已有阅读。摘要层及书目保留不表示已核全文或已经可迁移。Splitter 原始工具补跑 chain 仍新进 0，正式参考书目的手工方向继续是有效链证据。

## 调用日志

- 原始路径 `python3 lit.py search "Factorio SAT belt balancer synthesis" --pool run1/块7/sol/sat_pool_update.jsonl --n 30`：返回 0、新进 0。
- 原始路径 `python3 lit.py search "shapez factory planning" --pool run1/块7/sol/sat_pool_update.jsonl --n 30`：返回 2、新进 2；都是明显无关生物系统/牡蛎病毒材料，详见筛选表。
- 原始路径 `python3 lit.py chain 10.4230/LIPIcs.FUN.2024.9 --pool run1/块7/sol/sat_pool_update.jsonl --top 20`：新进 0。新工具运行后仍缺 OpenAlex 引用索引；实际参考方向以已有正式出版商参考书目为证。
- 原始路径 `python3 lit.py chain 10.1016/j.orl.2009.03.006 --pool run1/块7/sol/sat_pool_update.jsonl --top 25`：新进 24；新进条目的筛选与阅读见下文。

## 新增证据

- [W1550646467；DOI:10.1007/3-540-45578-7_14] Alexander Bockmayr、Nicolai Pisaruk、Abderrahmane Aggoun 2001，Network Flow Problems in Constraint Programming（CP 2001，LNCS 2239，196–210）。
  解的问题：在约束规划中直接表示和求解网络流问题。
  方法：提出 flow 全局约束，定义其声明与操作语义，并展示应用；传播规则细节尚未取得全文核查。
  规模：仅核摘要，实例规模未核。
  对应本题：规则“通道：物品在两个物品格之间移动的路径”可在抽象层对应有向弧；机器配方与仓库供给对应结点收支，带段对应容量弧。
  不对应的：静态 flow 约束没有逐格停满 1 tick、轮询、机器成批消耗，也不自动处理同一格自产自销与不想要的端口自动连接。
  对本题有什么用：L 小窗口或模块综合的表示备选：将抽象流可行性封成全局约束，和布局变量连接；在读到操作语义后再评估能否替换逐格多商品子模型中的部分流传播。不能以摘要声称已获得更快求解或严格产量证明。
  依据：仅[Springer 主源摘要](https://link.springer.com/chapter/10.1007/3-540-45578-7_14)；作者[出版物目录](https://page.mi.fu-berlin.de/bockmayr/publications.html)确认题名/出处。全文未取得。
  引用方向：Meyers/Schulz 2009 作者公开稿参考文献 [3] → 本文；chain 新进 W1550646467 后复核真实方向。作者稿中同一条目 pp.196–210，非题名相近推断。

- [W2043901793；DOI:10.1287/ijoc.1110.0485] David R. Morrison、Jason J. Sauppe、Sheldon H. Jacobson 2011 online / 2013 卷期，A Network Simplex Algorithm for the Equal Flow Problem on a Generalized Network（INFORMS Journal on Computing 25(1)，2–12）。
  解的问题：有乘法增益/损失弧、并要求若干弧集等流量的最小费用流。
  方法：基于网络结构的 simplex，不直接维护一般 LP tableau；减少每次 pivot 的结构运算。
  规模：作者稿 §8 pp.14–15：1200 结点，35,970–647,460 弧，10 或 50 组等流量集；最大的 50 组实例平均约 81 秒。实际 CPU 比 CPLEX primal simplex 约慢 4–8 倍，尽管 pivot 更少；不把理论单次迭代改进写成实测更快。
  对应本题：配方“1 荞花 → 2 荞花种子”这样的单输入倍率可对应增益弧；已证均分的物流模块可对应等流量弧集。
  不对应的：多输入配方“10 钢制零件 ＋ 15 致密源石粉末 → 1 高容谷地电池”不能由单条增益弧表达同步联合耗料；连续流没有格子几何、缓存/滞留和周期状态。
  对本题有什么用：L 的物流骨架表示：对可建模子模块同时保留变换倍率与均分关系，再生成并修复空间布局；提供大型静态放宽可计算的规模数据，但没有替代游戏运行内核或现有 LP 后端的实测依据。U 的任何使用仍需证明这是正确放宽。
  依据：作者公开全文 §1–2 pp.1–3、§8 pp.14–15；[作者研究主页](https://evokewonder.com/research/)确认归属，[作者全文](https://evokewonder.com/research/docs/geneqflow-ijoc-final.pdf)，[出版商 DOI](https://pubsonline.informs.org/doi/10.1287/ijoc.1110.0485)。本次 PDF 只在内存提取，未另写下载文件。
  引用方向：本文作者稿 §1 p.2 和参考文献 p.25 → Meyers/Schulz 2009；属于 chain 的施引结果。

- [W3047602970；DOI:10.1007/s10479-021-04426-0；arXiv:2008.02035] Christina Büsing、Arie M. C. A. Koster、Sabrina Schmitz 2021 online / 2022 卷期，Robust minimum cost flow problem under consistent flow constraints（Annals of Operations Research 312，691–722）。
  解的问题：多个供需场景共享一个网络，指定弧在所有场景上必须使用同一个流量，其他弧可以调整；最小化最坏场景费用。
  方法：§3.1 定义一致流约束；§5 对固定场景数的串并联图给动态规划，并给同一单源单汇特例的多项式算法。
  规模：理论结果，未核本题规模的运行实验；DAG 上甚至两个场景和单位容量也可 NP-hard。
  对应本题：布局不能随未知连接/重建先后调整，需求、可用量或固定模块接口在多种工况下须兼容，可借“共享固定决定、逐场景检查”的表示。
  不对应的：论文允许 free arcs 各场景另选流；本题这些流由唯一物流规则运行产生，没有场景知道后的调流控制。任意运行周期的不确定性也不能未经证明压成有限供需场景。
  对本题有什么用：L 的稳健模块筛选与反例测试架构；只有在场景可完备覆盖、且自由流适应被精确状态约束替代后，才可能用于全循环态认证。目前不直接用于 U 或严格 L。
  依据：[Springer 全文 §2、§3.1 Definition 1、§5](https://link.springer.com/article/10.1007/s10479-021-04426-0)，[arXiv 主源](https://arxiv.org/abs/2008.02035)；RWTH 元数据确认在线2021/卷期2022。未保存新的 PDF。
  引用方向：该文 §2 与参考文献 → Meyers/Schulz 2009；同处还实际引用 Morrison 2013 和 Srinathan 2002。chain 的施引关系已在正文复核。

- [W1971980172；DOI:10.1080/02331939808844399] Torbjörn Larsson、Zhuangwei Liu 1998，An efficient Lagrangean relaxation scheme for linear and integer equal flow problems（Optimization 44(1)，49–67）。
  解的问题：有成对等流量侧约束的线性或整数最小费用流，既找费用下界又恢复可行流。
  方法：把等流量约束拉格朗日对偶化，次梯度优化乘子；连续问题通过子问题解的平均值在极限恢复等流变量，有限轮固定近似流值后再解普通最小费用流以得到可行解。整数部分是启发式，不保证找到可行解或最优解。
  规模：此次已读作者上传稿 §1–2 的方法，未核实验表规模，因此不填写“高效”的定量结论。
  对应本题：某些接口必须按配方比例或已证均分输出，能作为耦合的流变量；将复杂分配与普通容量物流分开有利于修复候选拓扑。
  不对应的：把流变量平均或固定不等于物品能按八步时序实现；没有轮询指针、格子占用、批量制造、反压或最大空矩形目标。等流量约束是否成立仍须规则证明。
  对本题有什么用：L 的网络修复备选：在可正确抽象的子模块中先用便宜流子问题找近似接口流，再固定这些流重解拓扑并提交规则内核。对偶费用界仅属于抽象物流问题，不能直接充当本题面积 U。
  依据：作者 Torbjörn Larsson 上传的[论文原文 §1–2](https://www.researchgate.net/publication/290588052_An_efficient_Lagrangean_relaxation_scheme_for_linear_and_integer_equal_flow_problems)，[出版商卷期目录](https://www.tandfonline.com/toc/gopt20/44/1)确认题名、卷期页码，DOI 已由 pool 核。出版商正文接口未打开；本次只读取原论文公开文本，未注册账号。
  引用方向：Meyers/Schulz 作者稿参考文献 [11] 同题 → 本文；作者稿混写另一篇1997论文的卷期，此处出版元数据按本篇 DOI 和作者上传稿1998纠正，未将误写卷期作为本篇证据。

## 其余网页检索日志

以下都是网页搜索，不计入追加 OpenAlex search 数：

- `"Network Flow Problems in Constraint Programming" 2001` → Springer DOI 摘要、作者出版目录。
- `"A network-flow-based optimal sample preparation algorithm for digital microfluidic biochips"` → 书目信息与聚合摘要；主源全文未核。
- `"Robust minimum cost flow problem under consistent flow constraints"` → Springer 全文、arXiv、RWTH 元数据。
- `"A Network Simplex Algorithm for the Equal Flow Problem on a Generalized Network"` → INFORMS 摘要、作者全文。
- `"6742894" pdf Dinh` → 主要是无关编号命中，未带来原论文。
- `"Bockmayr" "Pisaruk" "Aggoun" "Network Flow Problems" pdf` → 作者出版目录，未取到全文。
- `"A network-flow-based optimal sample preparation" pdf Yamashita` → 书目/作者索引，未取到全文。
- `"An efficient lagrangean relaxation scheme" Larsson Liu pdf` → 作者上传论文正文与出版商卷期目录。
- `"A network-flow-based optimal" "pdf" "Dinh"` → 后来论文的参考文献与二手摘要，未据此声称已读原文。

主源访问：IEEE 6742894 只返回 JavaScript 人机核验页；ACM DOI 页打开失败，没有注册、填写或绕过验证。Morrison PDF（401,973 字节）在内存经 `pdftotext` 提取并读相关节，没有另写文件；RWTH PDF URL 返回 HTML，改读 Springer 正文。CP 2001 只有摘要，Larsson 1998 的证据来源是作者上传的原论文正文而非聚合页面解释。

## 新进候选的摘要层证据

以下证据来自摘要或明确列出的引言，均不代表精读全文；对应与用途是尚未实施的迁移判断。

- [W2114616381；DOI:10.1287/moor.8.4.538] Integer Programming with a Fixed Number of Variables（1983）。
  解的问题：固定变量数整数线性规划的可解性。
  方法：几何数论方法；变量维数固定时输入位长多项式可解。
  规模：理论结果；本题运行规模未核。
  对应本题：规则“基地：所有单位都建在基地内，70×70 格”对应有限整数坐标区域。
  不对应的：70×70逐格模型有大量整数变量，不能称为固定维；也未含游戏动态。
  对本题有什么用：L/U模型设计：尝试将一个固定接口模块的整数决定压成少数计数，其余用连续流；只有确实固定维才适用，不是现有模型加速保证。
  依据：[INFORMS摘要](https://pubsonline.informs.org/doi/abs/10.1287/moor.8.4.538?journalCode=moor)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2003160050；DOI:10.1137/0205048] On the Complexity of Timetable and Multicommodity Flow Problems（1976）。
  解的问题：整数多商品流及排课问题的复杂性。
  方法：归约证明：有向/无向整数多商品流即使仅两商品仍NP-complete；受限排课有多项式情形。
  规模：理论结果；归约细节和实验未核。
  对应本题：规则“运输单位：除桥接器外只有一个物品格，每个物品格上限 1”对应局部容量。
  不对应的：本题物流是固定确定性规则产生的周期率，不是可自由选择的静态整数流；不能由此推出本题NP-hard或面积界。
  对本题有什么用：L表示的复杂性边界：若把两个物品的路径一次交给整数流模型，不能直接沿用普通单商品流的整性/多项式保证；本次不替换任何求解步，保留为模型审查依据。
  依据：[SIAM摘要](https://epubs.siam.org/doi/10.1137/0205048)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W1995246641；DOI:10.1137/0203021] Computationally Related Problems（1974）。
  解的问题：网络流等多个组合问题之间的多项式归约关系。
  方法：复杂性归约；本次摘要不列每个具体网络变体，Meyers已读正文明确以此为整数等流量困难性来源。
  规模：理论结果；具体构造未核。
  对应本题：规则“元件轮询：按接通先后循环，从上次成功的下一条开始”可形成需另证的分配关系。
  不对应的：一般困难性不是给定70×70实例不可行，也没有轮询动态或矩形空地约束。
  对本题有什么用：U证明背景候选：只在要审查某个等流量子模型的复杂性时追到精确归约；目前没有面积上界或可替换步骤，保留而不计直接算法贡献。
  依据：[SIAM摘要](https://epubs.siam.org/doi/10.1137/0203021)；Meyers作者稿§1/[15]核引用，未读本文归约。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2000200530；DOI:10.1016/0377-2217(84)90068-7] Network models for vehicle and crew scheduling（1984）。
  解的问题：公交车辆与人员排班网络模型的统一综述。
  方法：统一组织已有车辆调度、人员调度网络模型；摘要不列单个算法细节。
  规模：综述；具体实例规模未核。
  对应本题：规则“配方时长过后结束”要求运输与制造的时间语义相容。
  不对应的：车辆/人员是可安排的执行者；本题机器不能被人为调整每一步执行顺序，公交日程不等于任意可达周期。
  对本题有什么用：L的时间展开表示线索：若需为小模块显式给出一周期操作与资源连接，可查看网络调度建模；先核全文对应模型，当前不宣称能构造合格布局。
  依据：[Elsevier摘要](https://www.sciencedirect.com/science/article/pii/0377221784900687)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2142343014；DOI:10.1287/opre.48.2.233.12384] A Dynamic Network Flow Problem with Uncertain arc Capacities: Formulation and Problem Structure（2000）。
  解的问题：弧容量随机的动态网络流。
  方法：多阶段随机LP、多场景表示和compath分解；最廉价compath子问题多项式算法，扩展多商品。
  规模：摘要未给结点/场景/时间层规模。
  对应本题：规则“运输单位：除桥接器外只有一个物品格，每个物品格上限 1”对应局部容量。 规则“配方时长过后结束”要求运输与制造的时间语义相容。
  不对应的：本题未知的是连接先后、轮询初态和运行交错，不是有已知概率的外生容量；随机期望不满足所有周期达标。
  对本题有什么用：L模块反例筛选：以时间层+场景结构组织堵塞工况；可试分解表示，但须改成对全部工况验证，且不能直接使用概率目标认证L/U。
  依据：[INFORMS摘要](https://pubsonline.informs.org/doi/10.1287/opre.48.2.233.12384)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2159446692；DOI:10.1287/mnsc.26.3.274] A Lagrangean Relaxation Algorithm for the Two Duty Period Scheduling Problem（1980）。
  解的问题：两值勤时段排班的0-1规划。
  方法：转成单值勤时段网络流加侧约束；对偶化侧约束，次梯度求界。
  规模：摘要只说若干大实例，具体数未核。
  对应本题：规则“通道：物品在两个物品格之间移动的路径”可抽象成图弧。
  不对应的：排班侧约束不是配方同步或轮询；费用下界不是最大空矩形上界。
  对本题有什么用：L修复结构候选：把已可转普通流的物流部分留子问题，把接口耦合留侧约束；只借拆分套路，不搬运排班约束，U须另证放宽。
  依据：[INFORMS摘要](https://pubsonline.informs.org/doi/10.1287/mnsc.26.3.274)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2052580805；DOI:10.1109/aspdac.2014.6742894] A network-flow-based optimal sample preparation algorithm for digital microfluidic biochips（2014）。
  解的问题：多目标浓度样本制备并节省试剂、缓冲剂和废液。
  方法：最小费用最大流模型生成最优制备方案；精确模型假设未核。
  规模：摘要没有实例规模或耗时，未核。
  对应本题：规则“通道：物品在两个物品格之间移动的路径”可抽象成图弧。 配方产物可作为目标需求结点。
  不对应的：液滴混合改变浓度，物品身份和三路轮询不同；没有格子容量、反压或全周期证明，摘要中的“optimal”不适用于本题。
  对本题有什么用：L物流骨架候选：先满足多个目标配比并共享上游制造，再嵌入布局；必须读原模型才能确定可否替代拓扑分配步骤，当前仅摘要级保留。
  依据：[OpenAlex摘要与ID](https://openalex.org/W2052580805)，DOI:10.1109/ASPDAC.2014.6742894；IEEE/ACM主源访问失败，主源全文及引用方向未核。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2114364830；DOI:10.1016/j.jcss.2003.11.005] Decoding turbo-like codes via linear programming（2004）。
  解的问题：turbo-like纠错码的LP译码。
  方法：把合法码字表示为图中路径，LP结构近似最小费用流，证明特定噪声条件下错误率界。
  规模：摘要给按码长的理论错误界；数值规模未核。
  对应本题：规则“通道：物品在两个物品格之间移动的路径”可抽象成图弧。
  不对应的：码字路径不是输送带流量；随机噪声错误界无关所有循环态吞吐，也未编码空间共享。
  对本题有什么用：L表示候选：将合法子模块选择表示为图路径，再对路径一致变量做LP；只有找到模块→路径的精确映射才可操作，现阶段不替换内核或作为U。
  依据：[作者机构摘要](https://research.google/pubs/decoding-turbo-like-codes-via-linear-programming/)，未读2004期刊全文；MIT链接是先前会议稿。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2149301478；DOI:10.1287/mnsc.45.10.1440] Algorithms for the Simple Equal Flow Problem（1999）。
  解的问题：只有一个等流量弧集的最小费用流。
  方法：network/parametric simplex、二分、容量缩放；二分需O(log(nB))次普通min-cost-flow（B为数据最大值，避免与本题U混淆）。
  规模：理论复杂度已核摘要；实验结点数未核。
  对应本题：规则“元件轮询：按接通先后循环，从上次成功的下一条开始”可形成需另证的分配关系。
  不对应的：只支持一组等流量关系；本题很多轮询结点，且堵塞后未必均分。
  对本题有什么用：L小模块求解：若仅一个已证耦合的均流接口，可用普通流+二分替代通用整数求解；先证明均流必要性并核整性转换，不能直接作为产量证明。
  依据：[INFORMS摘要](https://pubsonline.informs.org/doi/10.1287/mnsc.45.10.1440)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2046222814；DOI:10.1016/0377-2217(88)90012-4] The equal flow problem（1988）。
  解的问题：带等流量侧约束的网络问题。
  方法：拉格朗日松弛给下界，右端分配分解给费用上界；对偶同时给初始等流量分配。
  规模：摘要：最多1500结点、6000弧；解距费用最优1%内。摘要还称整数候选“99.99% feasible”，不当严格可行证据。
  对应本题：规则“元件轮询：按接通先后循环，从上次成功的下一条开始”可形成需另证的分配关系。
  不对应的：近似约束满足不能满足本题严格周期阈值；MPSX相对时间是旧软件比较，不能预测当前性能。
  对本题有什么用：L候选修复：先以对偶给接口流初值，再解分配网络；把近似解交严格内核修复。费用界不能直接转本题面积U。
  依据：[Elsevier摘要](https://www.sciencedirect.com/science/article/pii/0377221788900124)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W1986624101；DOI:10.1080/02331939708844312] A Lagrangean Relaxation Scheme for Structured Linear Programs With Application To Multicommodity Network Flows（1997）。
  解的问题：结构化LP拉格朗日分解后的原问题解恢复，应用于多商品流。
  方法：修改调和步长；平均对偶子问题解可在极限趋向原LP最优解，形成近似多商品流算法。
  规模：摘要称运输实例实验，具体规模未核。
  对应本题：规则“运输单位：除桥接器外只有一个物品格，每个物品格上限 1”对应局部容量。 不同物品对应商品。
  不对应的：平均分数流可能不可嵌入固定带子；极限收敛不是有限轮证明，整数布局/轮询动态均未涵盖。
  对本题有什么用：L骨架初值：对几十种物料分解容量耦合，平均得连续流初解，后续选路径、布置并验证；U只有有效对偶界且模型确为放宽才可用。
  依据：[作者上传原论文摘要](https://www.researchgate.net/publication/233295539_A_Lagrangean_Relaxation_Scheme_for_Structured_Linear_Programs_With_Application_To_Multicommodity_Network_Flows)，未读算法全文；出版社DOI:10.1080/02331939708844312。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W1966139704；DOI:10.1002/(sici)1097-0037(199901)33:1<1::aid-net1>3.0.co;2-m] Balanced network flows. I. A unifying framework for design and analysis of matching algorithms（1999）。
  解的问题：多类匹配问题的统一平衡网络流表示。
  方法：增广算法分析、非cut/barrier最优性判据；导出类似Dinic的c-capacitated b-matching。
  规模：理论框架；实验规模未核。
  对应本题：规则“通道：物品在两个物品格之间移动的路径”可抽象成图弧。 端口的有限连接数可成为匹配容量。
  不对应的：balanced是偏对称/匹配网络概念，不是轮询流量均衡；它只解匹配，不保证多商品路径或周期吞吐。
  对本题有什么用：L模块拼接候选：先在兼容输出/输入端口间做容量匹配，再布线；需按物料、空间可达性过滤边，不能以匹配可行认证整厂。
  依据：[原论文摘要](https://web.eecs.umich.edu/~pettie/matching/Fremuth-Paeger-Jungnickel-balanced-network-flow-I-unified-framework-for-matching-algs.pdf)，未读主体。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W1968248813；DOI:10.1016/s0377-2217(02)00505-2] Network simplex algorithm for the general equal flow problem（2003）。
  解的问题：任意多个等流量弧集的连续最小费用流。
  方法：把基刻画成可分解子图并给graphical/network simplex，利用网络结构。
  规模：摘要未给实验规模/耗时。
  对应本题：规则“元件轮询：按接通先后循环，从上次成功的下一条开始”可形成需另证的分配关系。
  不对应的：连续同组均流不包含轮询、物品年龄或空间资源；均流关系不能凭愿望附加。
  对本题有什么用：L抽象网络后端：相比单组算法，可容纳多个已证分配接口；可替通用LP的表示/专用后端候选，但须先核数值性能，无严格运行保证。
  依据：[Elsevier摘要](https://www.sciencedirect.com/science/article/abs/pii/S0377221702005052)，未读全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W4385282889；DOI:10.1145/3592437] Min-Deviation-Flow in Bi-directed Graphs for T-Mesh Quantization（2023）。
  解的问题：T-mesh边整数长度赋值/四边形网格量化。
  方法：双向网络最小偏差流；近似求解和基于图匹配的迭代精化得到精确解。
  规模：作者摘要：300数据集约301实例，精确算法合计17.06s，对比QuadWild3491s、能量低11%；仅网格量化数据。
  对应本题：规则“基地：所有单位都建在基地内，70×70 格”对应有限整数坐标区域。
  不对应的：边长度约束不是有障碍的多商品带子；需固定网格拓扑，无矩形机器端口、反压或配方。
  对本题有什么用：L/U静态几何子模型候选：固定拓扑后若通道长度/区域边长守恒可化成Bi-MDF，借专用整数流求解代替该小块通用branch-and-cut；未证明本题可化归，不能搬性能。
  依据：[作者项目摘要](https://www.algohex.eu/publications/bimdf-quantization/)，未读论文主体。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2964977947；DOI:10.1007/978-3-030-35802-0_42] Level-Planar Drawings with Few Slopes（2019）。
  解的问题：固定层与边斜率集合的平面图绘制，含部分图固定后的扩展。
  方法：整数环流表示及原图流/对偶距离表示；proper分层图存在性O(n log²n/loglogn)，部分图扩展有多项式算法。
  规模：理论时间界；本题规模实验未核。
  对应本题：规则“基地：所有单位都建在基地内，70×70 格”对应有限整数坐标区域。 固定窗口外布局可类比不可改部分图。
  不对应的：直线分层边不等于直角逐格传送带；无桥接器、物品、多层同格穿过和机器矩形障碍，general非proper问题可难。
  对本题有什么用：L窗口修复表示外延：固定外部端口/线，再求内部拓扑的绘制扩展；只对可转proper分层平面图子模块可试，不能据其不可绘制排除允许桥接的本题布局。
  依据：[作者arXiv摘要](https://arxiv.org/abs/1907.13558)；[扩展期刊引言](https://link.springer.com/article/10.1007/s00453-021-00884-x)核流/距离表示，未读2019全文。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

- [W2105826541] On an Integer Multicommodity Flow Problem from the Airplane Industry（1997）。
  解的问题：飞机零件与专用拖车耦合的整数多商品运输及空拖车回收。
  方法：优化与近似算法；飞机仅允许指定货物/拖车组合，细节未核。
  规模：仓库索引摘要无实例规模/算法界，未核。
  对应本题：规则“运输单位：除桥接器外只有一个物品格，每个物品格上限 1”对应局部容量。 规则“通道：物品在两个物品格之间移动的路径”可抽象成图弧。
  不对应的：车辆稳定性组合约束、拖车回收不是本题轮询；物流路径可调与已建自动运行不同。
  对本题有什么用：L多物料耦合建模线索：若一组机器接口/通道必须联合配给，可考察组合容量而非各商品独立分配；目前只保留表示候选，未核算法是否能替布线。
  依据：[OpenAlex索引摘要](https://openalex.org/W2105826541)，报告ID可核；TU/e主源URL本次打开失败，原文未核。
  引用方向：OpenAlex chain连接到Meyers/Schulz2009；未逐篇核原文参考文献时不认定具体是参考还是施引。

## 仅书目保留与筛除

- [W2011039300] Garey、Johnson 1979，Computers and Intractability: A Guide to the Theory of NP-Completeness。仅书目保留：问题为NP-completeness背景教材（据题名），方法/规模均未核；与规则“基地：所有单位都建在基地内，70×70 格”的整数布局仅一般关联，未核到可替换的L构造或U界；不能把通用困难性当本题不可行证明。依据：[OpenAlex元数据](https://openalex.org/W2011039300)，无摘要；本次未编造具体章节贡献。
- [W1977545325；DOI:10.2307/2583863] Network Flows: Theory, Algorithms, and Applications.（1994）。仅书目保留并标元数据疑点：Crossref将其记为David K.Smith等的JORS期刊条目；Meyers引用的是Ahuja等1993专著。本ID与所引专著不是已确认同一文献；索引摘要介绍最短路/最大流/最小费用流，但未核此条目原文。与规则“通道：物品在两个物品格之间移动的路径”可作一般物流图算法背景；方法、规模、本题可替换L/U步骤未核，不能以该ID声称读了原书。依据：[Crossref登记](https://api.crossref.org/works/10.2307/2583863)、[OpenAlex摘要](https://openalex.org/W1977545325)。
- [W2039371991；DOI:10.1145/180139.181063] On the limits of proper learnability of subclasses of DNF formulas（1994）：筛除。已读摘要只研究DNF概念类在exact/PAC学习模型的可学习性上下界，没有物料网络、容量、几何布置或构造接口；本题没有学习未知DNF的需求。[索引摘要](https://openalex.org/W2039371991)。
- [W7209977076] Biosystems Engineering Research Review 19：筛除，生物系统年报，没有本题工厂游戏或网络综合接口。
- [W2603312558] An assessment of RT-qPCR accuracy in monitoring infectious norovirus in oyster farms：筛除，牡蛎病毒监测，与本题物流/空间构造无对应。
- [W1851375266] Theory of Equal-Flows in Networks：已在sat_lineage.md读过；保留已有证据，不重读。

## 追加候选闭合日志

没有新增OpenAlex search或引用链扩展。直接读取sat_pool_update.jsonl的19个候选题名/摘要；对4个缺摘要或身份需核条目，读取Crossref DOI单篇登记（10.2307/2583863、10.1016/0377-2217(84)90068-7、10.1016/0377-2217(88)90012-4、10.1016/j.jcss.2003.11.005），登记均无摘要；再以网页查主源摘要。

本阶段网页查询（来源均网页搜索，结果依据各证据行主源链接）：

- `"Algorithms for the Simple Equal Flow Problem" abstract`
- `"Network models for vehicle and crew scheduling" abstract Carraresi Gallo`
- `"The equal flow problem" Ali Kennington Shetty 1988 abstract`
- `"Network simplex algorithm for the general equal flow problem" Calvete abstract`
- `"Min-Deviation-Flow in Bi-directed Graphs for T-Mesh Quantization" authors`
- `"On an Integer Multicommodity Flow Problem from the Airplane Industry" TU Eindhoven`
- `"Level-Planar Drawings with Few Slopes" arxiv`
- `"Balanced network flows" "unifying framework" abstract`
- `"Network models for vehicle and crew scheduling" site:sciencedirect.com/science/article`
- `"The equal flow problem" "1988" "Abstract"`
- `"Decoding turbo-like codes via linear programming" abstract MIT`
- `"Integer Programming with a Fixed Number of Variables" Lenstra abstract`
- `"A Lagrangean Relaxation Scheme for Structured Linear Programs" Liu Larsson`
- `"On an integer multicommodity flow problem from the airplane industry" Verweij Aardal Kant abstract`

旧4条较详证据未重读。Dinh和飞机工业报告只有OpenAlex索引摘要，明确保留摘要证据、主源全文未核；未把来源访问失败推成文献不存在或模型不可用。Garey教材与1994网络流期刊条目仅保留书目，不虚构方法或规模。
