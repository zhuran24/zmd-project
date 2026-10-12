## 本块小结

**一句话：** 本题的带子层在 VLSI 里有现成的名字，叫「Manhattan 型开关盒布线（Steiner 树打包）」：两条线共用一格时只能各自直穿，这正是桥接器。「中间物品自产自销」是逐格模型里一个有名的漏洞（无源环），文献里有三种补法：割不等式、整数势（递增标号）、方向受限。能扩到 70×70 级的做法都不用「每格×每条线」的变量，而是路径列、拓扑先行或构造加压缩。

**查了哪些领域（9 个）：** VLSI/PCB 布线；纳米电路（QCA/FCN）物理设计；流式微流控芯片；运筹学的设施布局 + 物流通道 / AGV 流路；化工厂布局 + 管道；FPGA/CGRA 映射；图绘制（正交画法、端口约束、拓扑-形状-尺寸）；多智能体路径规划；谜题（Numberlink/Flow Free）。另有工厂游戏（Factorio）。

**查询词和来源：**
- OpenAlex 检索（1 次，之后共享额度降到 0.0028，第 2 次自动改成 arXiv）：「integrated facility layout and flow path design」。
- OpenAlex 引用链（chain，1 次，6 个种子，见下）。
- arXiv：「field-coupled nanocomputing placement routing」（先 429，重试得 1 篇）、「nanocomputing placement routing」、「CGRA mapping routing」、「global routing integer programming column generation」（OpenAlex 额度不足自动转来）。arXiv 接口一直限流，后面不再用。
- Crossref（主题检索）：「Packing Steiner trees cutting plane switchbox routing」「single layer routing jumpers」「Flow path design for automated guided vehicle systems」「process plant layout pipe routing mixed integer」「rubber-band routing topological routing planar」「single-layer routing with crossovers jumpers minimization」「conveyor network layout design optimization integer programming」；另有十几次按标题查 DOI（Close-to-optimal…biochips、GRIP、PathFinder、Columba、Port constraints…data flow diagrams、A* is Born、Graph-Oriented Layout Design、Non-crossing MAPF、Yu–LaValle、On embedding a graph in the grid…、Numberlink NP-completeness、Solving Numberlink by SAT）。
- 网页搜索（WebSearch）：FCN 精确放置布线 SMT 与交叉块、时钟方案；PCB 单层布线加跳线；Columba 的 MILP 与流道交叉；Numberlink 的 SAT 编码与防环；CGRA 映射 ILP 与 MRRG；数据流图正交排版的端口约束；Factorio 带子布线与 SAT；格点手术（lattice surgery）的不相交路径编译；Walter 2018 精确 QCA；Klausnitzer–Lasch 2019；流式微流控布线、交叉开关、ILP；GRIP；FCN 的 OGD 可扩展法；Grimmer 2017；柔性跨布局 MIP；Grötschel 等的 knock-knee/Manhattan 模型；knock-knee 与不相交路径；FCN 布局后优化；Nadel 的带约束布线；开关盒分支定价；拓扑-形状-尺寸与压缩；Numberlink 的 SAT 与复杂度。
- Semantic Scholar API（OpenAlex 额度用完后的替代）：补摘要，并做了 2 轮引用链（取参考文献和施引文献各前 100 条）。

**引用链的种子：**
- OpenAlex chain：Klausnitzer–Lasch 2019（W2900723210）、Walter 等 2018（W2798373485）、Grötschel–Martin–Weismantel 1996（W2082591111）、Walker–Anderson 2019（W2913300152）、Guirardello–Swaney 2005（W1986460167）、Patterson 等 2023 Factorio（W4387355460）。
- Semantic Scholar 第 1 轮：Walter 2018、Grimmer 2017、Factorio 2023、GMW 1997、Klausnitzer–Lasch 2019、Walter 2019。
- 第 2 轮（去掉 FCN 种子，免得结果全是 FCN）：GMW 1997、Klausnitzer–Lasch 2019、Grimmer 2017、Walker–Anderson 2019、Factorio 2023、Gaskins–Tanchoco 1987。
- 引用链带进来的有用论文：FCN 布局后优化（门搬家 + 删整行导线）、开关盒分支定价（Jørgensen–Meyling）、Nadel 的 DRouter、Burstein 的分层布线、BonnCell、AGV 格子导引路径、Montreuil 1991、2DDWave 时钟方案。

**留下多少：** pool 共 271 条，大部分是 OpenAlex 引用链带进来的泛泛之作（化工手册、TSP、CGRA 架构等），看标题筛掉。留下 49 篇：36 篇写了证据行（28 行，有几行合写了会议版和期刊版这类同组论文），另 13 篇在第十节各写一句。

**最可能有用的 5 篇：**
1. Grötschel、Martin、Weismantel 1997，Steiner 树打包（10.1007/BF02614374）：本题带子层和 Manhattan 开关盒布线一一对应，桥接器就是「直穿交叉点」。用 Steiner 割不等式表示连通性，就不会有无源环，LP 也比流模型紧。knock-knee 是更宽的放松，在它下面证出不可行，本题也不可行，可以拿来压 U。
2. Patterson 等 2023，Factorio 蓝图（arXiv:2310.01505）：给每个带子格一个整数势 ≤ w+h，沿带子严格递增，环就排除了。这是补「自产自销」漏洞最便宜的办法，能直接写进 CP-SAT。他们的三段分解（台数→装箱→布线）也和我们的放松模型同构。
3. Hofmann、Walter、Wille 2025，FCN 布局后优化（10.1109/tcad.2025.3549354），加上 2024 年的 A* is Born：先用 A* 按拓扑序构造，再「门搬家」（就是只含一台机器的小窗口工具），再删掉只穿过导线的整行或整列并合拢（压缩），把空面挤出来。实测能到千万瓦片，可以直接照着搭抬 L 的流程。
4. Wu、Davoodi、Linderoth 2011 GRIP（10.1109/tcad.2010.2066030），加上 Jørgensen–Meyling 2002 分支定价（10.1002/net.10029）：每条线一列，定价是带对偶价的最短路或 Steiner 树；按区域分解，长线用浮动端子过界，开关盒尺度能解到最优。如果改用路径变量，这两篇就是现成的做法；定价时要多带一个「进入方向」状态，才能表示「只许直穿、共格付一个桥」。
5. Walker、Anderson 2019，按连通性的 CGRA ILP（10.1109/fccm.2019.00019）：摆放模型里不放逐格带子，只放「上下游端口距离 ≤ k」和区域拥塞约束，冲突的地方再加细节。这给「先粗后细、按需加约束」的表示提供了实测。

**这块里真没找到东西的方面：**
- 单层布线加跳线（单面 PCB 自动插跳线）的学术算法：搜了「single-layer routing with jumpers」（网页、Crossref）和「single-layer routing with crossovers jumpers minimization」（Crossref），只找到工具文档（tscircuit、Altium、Specctra 论坛）和 80 年代的单层布线理论，没有能引的算法论文。所以最近的学术对应是 Manhattan 模型和 FCN 的交叉块。
- 「端口挨上就自动接通，要禁掉不想要的相邻」作为建模约束：专门的论文没找到。最近的有三处：设计规则约束（Nadel 2016）、QCA 导线最小间距（Walter 2018 提到，没展开），以及 A* FCN 反过来把自动接通当成特性用。
- 汇流的有向布线，也就是多源到一汇的有向 Steiner 树，在格子上做打包：GMW 的施引文献里有有向 Steiner 树打包、有向路径打包的纯理论，没找到用在格子布线上的算法。
- 一条带同时走几种物料，并且按流量拆线（一条满载 1 件/tick）：搜 Factorio 和 GRIP 时都看了，Factorio 那篇明确简化成「每格一种物品」，GRIP 只有边容量，没有汇流的轮询，所以没找到。
- 一格里四个方向各一条通道、同一轴上两个反方向都能过（本题桥接器的四个物品格）：哪个领域都没对应，Manhattan 模型的一个交叉点只容两条线。
- 格点手术（lattice surgery）的不相交路径编译：搜过（EDPC 和后续），它解决的是「每个时间步一批不相交路径」，和静态占格不同，判为关系小，没有写进证据行。
- 网页检索没找到 Klausnitzer–Lasch 2019、Columba、Guirardello–Swaney 的开放全文，这几条的依据只有摘要。
