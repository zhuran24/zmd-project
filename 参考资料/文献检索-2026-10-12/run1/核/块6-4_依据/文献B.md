# 块6-4：后三篇引文原文核查

核查日期：2026-10-12。核查范围为 `run1/块6/找空白.md` 的块6-4 所引 Iannopollo、Polgreen、Kaelbling 三篇。以下均依据全文；PDF 页码从文件第一张起算，不混用期刊排版页码。三篇标识均查到了对应论文；没有一篇在所核方法中给出假设文字的不可满足核提取或极小核删除算法。

## W2995734305：等价改名排除成立，转置推广仍需另证

- **题录与版本：** Antonio Iannopollo、Stavros Tripakis、Alberto Sangiovanni-Vincentelli，*Constrained synthesis from component libraries*，Science of Computer Programming 171，21–41，2019，DOI `10.1016/j.scico.2018.10.003`。OpenAlex 的 `W2995734305` 确实返回这个题名和 DOI，其年份字段为在线年2018；[作者所在大学题录](https://research.aalto.fi/en/publications/constrained-synthesis-from-component-libraries/)给出正式卷期日期2019-02-15。全文核查的是 Aalto 保存的36页作者稿，不是21页期刊排版。
- **取得过程：** `python3 lit.py full W2995734305` 已执行；解析 KEY 成功，但下载失败，原输出为「没有拿到开放获取的 PDF：https://doi.org/10.1016/j.scico.2018.10.003」。随后从[大学保存全文](https://aaltodoc.aalto.fi/server/api/core/bitstreams/111a5b0f-ce31-4ca4-ace6-59cd0a861485/content)取得 PDF，HTTP 200，1,939,189字节，SHA-256 为 `6234c84e8ec6f80e501f60d189e9d652e6332bcc0f361526f96e714f0d09a534`，与既有 `run1/块6/sol/fulltext/cscl.pdf` 完全相同。当前证据为 `iannopollo2019.pdf`、`iannopollo2019.txt`、`iannopollo2019_openalex.json`、`文献B_download.json`。
- **原文一句：** “The returned set R collects all the possible renaming functions that would yield a candidate equivalent to (H, ρ).”——§5.1 的 Table 2（RejectCandidate），PDF第18页，稿内页17；这是完整句子，不超过25词。
- **原文实际方法：** §5 起首定义等价组件集 E(G)，以同一重命名下双向 refinement 为条件（式21，PDF第16页）。§5.1 的 Table 1 在验证失败后调用 RejectCandidate，对返回的每个连接重命名加入不等约束（PDF第17页）；Table 2 生成与失败候选等价的连接重命名（第18页）。所以「把等价改名一起排除」有直接依据。
- **对块6-4的支撑边界：** 排除的是已建立组件／端口等价关系下的失败候选族，并非从该候选中取一个较小 UNSAT 核。组件规格等价也不自动包含格点几何、固定外部占用、取货口方向、供电覆盖的等价性；本文不能直接证明把本题区块核按 x↔y 推广是正确的。

## arXiv:2107.13477：神谕回答类型成立，不能据此声称能返回极小核

- **题录与版本：** Elizabeth Polgreen、Andrew Reynolds、Sanjit A. Seshia，*Satisfiability and Synthesis Modulo Oracles*。所给 KEY 是[2021-07-28的 arXiv v1](https://arxiv.org/abs/2107.13477)，12页；[共同作者的正式论文页](https://people.eecs.berkeley.edu/~sseshia/pubs/b2hd-polgreen-vmcai22.html)确认2022 VMCAI发表版本。这里章节和页码均按2021 arXiv v1，不能当作2022会议排版页码。
- **取得过程：** `python3 lit.py full arXiv:2107.13477` 成功，返回 `cache/full_f04da146ab81eaa7.txt`；对应源地址是[arXiv PDF](https://arxiv.org/pdf/2107.13477)。证据复制到 `polgreen_arxiv2107.13477v1.pdf` 和 `.txt`。
- **原文一句：** “We show the oracle interfaces for each of the classic query types in Table I.”——§V，PDF第7页；完整句子，不超过25词。
- **原文实际方法：** §II-B Definition II.1 定义 query domain、response co-domain、assumption generator 与 constraint generator（PDF第3页）。§V Table I 列出 membership、input-output、正／负见证、implication、counterexample、correctness 等查询／回答类型（第7页）；§IV 算法2将回答形成的约束送回综合阶段（第6页）。因此「神谕的回答类型」准确。
- **对块6-4的支撑边界：** 这支持显式定义反馈接口及其逻辑意义。它不规定布局区块神谕必须返回冲突决定集，也没有给出 CP-SAT 假设文字的核接口、逐条删核或核的转置推广。这里 oracle assumptions 是关于黑箱函数行为的公式；与块6-4中计划决定的 assumption literals 含义不同，不能因同用“assumption”就等同。

## 10.1109/ICRA.2011.5980391：串行化失败后联合解决成立，属于回退策略

- **题录与版本：** Leslie Pack Kaelbling、Tomás Lozano-Pérez，*Hierarchical Task and Motion Planning in the Now*，ICRA 2011，1470–1477。Crossref 精确 DOI 记录与作者提供的8页会议稿相符；证据 `kaelbling2011_crossref.json`。
- **取得过程：** `python3 lit.py full 10.1109/ICRA.2011.5980391` 失败，原输出为「没有拿到开放获取的 PDF：无链接」。随后从[MIT作者全文](https://people.csail.mit.edu/tlp/pdf/2011/hpnICRA11Final.pdf)取得 PDF，HTTP 200，412,369字节，与既有 `run1/块6/sol/kaelbling2011.pdf` 完全相同。当前证据为 `kaelbling2011.pdf`、`.txt` 和 `文献B_download.json`。
- **原文一句：** “The degree to which abstract operators can be serialized depends on how the domain is formalized.”——§IV 的 Hierarchy 段，PDF第6页；完整句子，不超过25词。
- **原文实际方法：** §I 说明首个抽象步骤的任意具体实现应允许后续步骤实现；串行化失败则为两个步骤的效果制定交错计划（PDF第1页）。§IV 的 Hierarchy 段末明确：抽象层串行化失败后，撤掉抽象重新解决规划问题，不再继续尝试串行化（第6–7页）。所以「串行化失败就把层次合起来解」作为通俗概括成立，更准确是“撤销失败处的抽象／分别求解，改为联合规划”。该段没有 C 小节编号。
- **对块6-4的支撑边界：** 这给的是扩大／联合重解的回退策略，并非取核、缩核或加计划层 no-good 的算法。§VI 的正确性论证要求最具体动作表示正确完备、起始状态静态连通，即动作最终可逆（PDF第7–8页）；同节又说明当前连续 suggester 只考虑少量实例，不能保证找到存在的解。这些假设不能直接搬到本题的高密度静态布局或长期运行上。

## 文献核查结论

这三条简短归纳各有原文依据，但提供的是三种不同东西：**已证等价关系下的失败族排除、带逻辑含义的反馈接口、分解失败后的联合规划回退**。它们能作块6-4的配套设计依据，不能被合并声称为已有“假设文字取 UNSAT 核→删到极小→转置推广”的完整文献算法。
