# 块6-3：两篇 VLSI 文献原文核查

核查日期：2026-10-12。范围为 `run1/块6/找空白.md` 的块6-3，重点对应第 169、172、174、180 行。下述页码为取得的 PDF 页码；两篇均核到全文，KEY 与 DOI、标题一致。

## W4385834439：ILPGRC

- **身份成立：** Tiago Augusto Fontana 等，*ILPGRC: ILP-Based Global Routing Optimization With Cell Movements*；DOI `10.1109/TCAD.2023.3305579`。OpenAlex 单篇解析结果保存在 [W4385834439-identity.json](W4385834439-identity.json)。
- **获取：** `python3 lit.py full W4385834439` 成功。全文来自 [IEEE PDF](https://ieeexplore.ieee.org/ielx7/43/6917053/10218743.pdf)，封面注明是 accepted author version，未完全编辑，14 页，682118 字节。保存在 [作者接受稿 PDF](W4385834439-author-version.pdf) 与 [全文文本](W4385834439-author-version.txt)。不能将其页码误当成最终期刊连续页码。
- **原文一句（12 个英文词）：** “The number of nets routed through a GCell cannot exceed its supply.”（§IV-C，PDF p.7，式(15)之前。）
- **实际内容：** §III（p.2）把电路划成 GCells，以各层 GCell 为 3D 图节点，capacity 是 routing tracks 数；式(11)（p.3–4）要求 demand 不超过 supply。§IV-C（p.5–7）生成 net routing 候选，以二元变量选择，并联合选择 cell 位置；式(14)选一个候选、式(15)限制容量。式(19)（p.7）将 pin blockage 与 cell 位置变量结合，约束为 `Σ r_ij + Σ b_i m_ij ≤ S(g_k)`。§IV-D（p.8）另做几何合法化。
- **核对：** 确实支持“粗空间图 + 容量约束 + 整数选择”的表示，也支持 placement/routing 的耦合。它接收已合法摆放、已有 global routing 的设计（§III，p.3），优化 VIA 与线长；不是逐格摆放前按物品组跑整数多商品流加机身/端点/供电面积账的算法。后者属于本题另外提出的改造。尤其不能从本论文得出“容量和摆放无关”：式(19)就是反例。

## W4200129711：Detailed Placement and Global Routing Co-Optimization

- **身份成立：** Zhipeng Huang 等，*Detailed Placement and Global Routing Co-Optimization with Complex Constraints*，*Electronics* 2022, 11(1), 51（2021-12-24 发布）；DOI `10.3390/electronics11010051`。解析结果见 [W4200129711-identity.json](W4200129711-identity.json)。
- **获取：** `python3 lit.py full W4200129711` 未能从 OpenAlex 给的 MDPI PDF URL 取得文件；之后取得 [MDPI 出版社完整 PDF](https://mdpi-res.com/d_attachment/electronics/electronics-11-00051/article_deploy/electronics-11-00051.pdf)，22 页，1452614 字节，见 [PDF](W4200129711.pdf) 与 [文本](W4200129711.txt)。[出版社文章页](https://www.mdpi.com/2079-9292/11/1/51)亦含全文。依据是全文，不是摘要。
- **原文一句（15 个英文词）：** “Congestion happens when the demand d(u) exceed the capacity c(u) assigned to the gGrid u.”（§2.1，PDF p.4。）
- **实际内容：** §2.1（p.4）用 3D gGrid 表示 global routing，capacity 为 tracks 数，demand 包括 net segments、cell blockage、同格 cell pair 与水平相邻格 cell pair 的额外需求；cell 移动会改变 blockage demand。§2.2（p.5）的方法是在已 placed/routed 的设计上做 R-tree 预处理、BFS 选移动位置、A*/maze 局部 reroute 和 refinement，降低线长。
- **核对：** 支持粗网格容量检查和摆放/布线联合考虑；没有把本文算法写成按物品组的整数多商品流，也没有本题的面积账。不能据此主张 placement 与容量无关：即使 nominal capacity `c(u)` 固定，有效余量 `c(u)-d(u)` 明确随 placement 改变。

## 对候选点四处措辞的结论

| 候选点位置 | 两篇原文核查结论 |
|---|---|
| 第169行：“出自”两篇文献 | 若指借用粗网格/容量/联合优化思路，成立；若指完整的“多商品流加面积账”闸门来自这两篇，未获支持。 |
| 第172行：“G-cell 就是区块”“边界容量就是空格数” | GCell 与区块可作粗空间抽象的类比。两篇实际约束的是多层 GCell/gGrid 的 routing tracks/supply/demand，不能直接等同本题公共边空格或一个物品格的存储上限。本题映射仍须独立从游戏规则证明。 |
| 第174行：“VLSI容量和摆放无关” | 不成立。ILPGRC 式(19)与 MDPI §2.1 明确计入 placement 造成的 blockage/额外需求；有效布线资源与摆放相关。 |
| 第180行：“全局布线的多商品流是VLSI标准步骤” | 这两篇支持粗网格容量布线是流程的一部分，不能据此把整数多商品流指定为所有全局布线的标准步骤。ILPGRC 采用候选路径二元 ILP，另一篇采用启发式局部重布线；这与本题按组汇总的整数流并非原文同一个方法。 |

上述对应结论为文献到本题的核查判断；不宣称粗容量闸门能保证逐格可实现，也不宣称它已经是本题的安全必要条件。若用来淘汰计划，容量必须覆盖真实可用资源的上界，路线需求与面积消耗必须是所有真实方案都满足的下界；这些方向仍须独立证明。

## 文件校验

- `W4385834439-author-version.pdf` SHA-256：`008d6927c7c132ebc1bd9e6d35f1a9addc3652905d7f14e5e3aff7f485ef525b`
- `W4200129711.pdf` SHA-256：`af8d3707ae58e965f7e3d8ab3bbb30537d241253b5400b916ddcc2f5cbe87399`
