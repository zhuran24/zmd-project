# 块7-1：Refraction、Yu–LaValle、Leung 引文核对

核对日期：2026-10-12。范围为 `run1/块7/找空白.md` 的块7-1，并核同文对这三篇的关联转述。三项指定 KEY 都精确解析成功；没有 KEY 404。三个 `lit.py full KEY` 均报「没有拿到开放获取的 PDF：无链接」；网页补得两篇作者全文，Leung 仅依据出版社摘要。详见 [取文记录](three_source_full_attempts.txt) 与各 `*_download.json`。

## 1. W2117006321：Smith 等，Refraction（2012）

**精确身份：** OpenAlex 返回 *A case study of expressively constrainable level design automation tools for a puzzle game*，DOI `10.1145/2282338.2282370`，与所引论文匹配。元数据见 [source_W2117006321.json](source_W2117006321.json)。

**依据：全文。** [作者所在华盛顿大学 PDF](https://grail.cs.washington.edu/wp-content/uploads/2015/08/smith2012acs.pdf)，本地 [refraction.pdf](refraction.pdf)、[refraction.txt](refraction.txt)。正式页码 156–163；所引 §6.4、§6.5 均在 p.161（PDF 第6页）。

**英文原文节录（同一句有省略）：**

> “The final ASP-based mission generator … can be combined with the ASP-based grid embedder … to form a monolithic puzzle generator.”

**逐条结论：**

- 「先生成任务图再嵌入，有的任务图嵌不进去」：**成立**。§6.5 p.161 第2段明确举含无向三角环的任务 DAG 为不可嵌入例子。
- 「把任务生成和格子嵌入两段 ASP 拼成一个程序」：**成立**。§6.5 p.161 最后一段明确以拼接两个程序的源代码形成单体生成器；§6.4 同页同时枚举位置与端口配置、要求全部任务边实现且器件不重叠。
- 「Refraction 的任务图里没有速率」：**若“速率”指逐 tick 生产吞吐，成立**。§4 p.158、§5.1 p.159 和 §6.5 p.161 建模的是带分数功率的激光，任务图具有数量属性，不能扩写成“没有量”。论文没有本题的缓存、反压、批量生产或所有循环态保证。联合选图与空间的设计原则成立；并未直接给一格直连工厂模型或本题规模保证。

## 2. 10.1007/978-3-642-36279-8_10：Yu、LaValle（2013）

**精确身份：** OpenAlex 返回 *Multi-agent Path Planning and Network Flow*；[Springer 指定 DOI 页面](https://link.springer.com/chapter/10.1007/978-3-642-36279-8_10) 标明作者、2013 年、pp.157–173。元数据见 [source_10.1007_978-3-642-36279-8_10.json](source_10.1007_978-3-642-36279-8_10.json)。

**依据：全文。** [作者发布的正式章节 PDF](https://people.csail.mit.edu/jingjin/files/YuLav13STAR.pdf)，首页直接印有所核 DOI；本地 [yu_lavalle.pdf](yu_lavalle.pdf)、[yu_lavalle.txt](yu_lavalle.txt)。这不是用相似标题替换指定 KEY。

**英文原文节录：**

> “allowing an arbitrary permutation σ to act on xG means that we may treat all agents as a single type of commodity.”

位置：§3.2 p.166（PDF 第10页），Theorem 3 之后的段落。

**逐条结论：**

- 「目标可互换时，多机器人路径化成网络流」：**成立**。§2 p.161 的 Problem 2 允许固定但任意的目标排列；§3.2 pp.165–166 将路径对应到时间展开图，匿名时所有机器人是一个商品。摘要 p.157 也给出该方向及算法界。
- 作为「每个目的地要有流、不指定由谁供」的支持：**概念类比成立，直接适用只部分成立**。论文原始底图是连通、无向、单位距离、碰撞自由的 CUG（§2 p.160）；解是有限时间的机器人轨迹，允许等待与不同时刻经过同一位置。它不证明固定有向传送带的空间独占、不改线持续满载或所有循环态吞吐。
- 「单物料单独是最大流」：§3.1 pp.162–163 确介绍带供需量的转运可用最大流求解；应用到本题仍需明确固定合法资源图、逐目的端口需求及容量。本篇不能证明 19 种物料各自有流便能同时共享同一张空间布局。

## 3. 10.1287/mnsc.38.4.594：Leung（1992）

**精确身份：** OpenAlex 与 [INFORMS 出版社页面](https://pubsonline.informs.org/doi/10.1287/mnsc.38.4.594) 均返回 Janny Leung，*A New Graph-Theoretic Heuristic for Facility Layout*，*Management Science* 38(4):594–605。元数据见 [source_10.1287_mnsc.38.4.594.json](source_10.1287_mnsc.38.4.594.json)。

**依据：摘要，未取得全文。** 出版社 [PDF 链接](https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.38.4.594) 的实际请求为 HTTP 403，返回 HTML，记录见 [leung_attempt_download.json](leung_attempt_download.json)。以下不冒称全文页节；原句位置为出版社页面 **Abstract**，文章始页 p.594。

**英文原文一句：**

> “An important first step in facility layout is the determination of which machines should be adjacent.”

**逐条结论：**

- 「选最大权平面邻接子图」：**成立，摘要依据**。摘要下一句把邻接选择建模为最大权平面子图，邻接权重来自预期流量与技术约束；摘要随后说明给出的是一种启发式及初步计算结果，不能说成已算出全局最优。
- 「设施布局中先选邻接图、再出布局是老路子」：**部分成立**。摘要明确支持邻接选择是布局的第一步；没有据此核实本文实际第二阶段如何生成几何布局、是否联合优化位置，也不支持本题端口隔一格、双轴桥、自动接通与不重叠建模。
- 「该篇不带端口和输送」：**全文未能核实**。摘要没有这些机制，只能说摘要未提供端口/输送机制，不能把全文的缺席当作已核事实。

## 可保留的引文支持

Refraction 保留“任务边与空间一同选”的直接方法依据；Yu–LaValle 保留“可互换目的地使同类对象免去预指定配对”的网络流依据，但不能直接认证静态工厂；Leung 保留邻接子图作为布局建模中间层的摘要依据。三篇均不能单独证明块7-1 的一格直连受限类足以达成本题产量。
