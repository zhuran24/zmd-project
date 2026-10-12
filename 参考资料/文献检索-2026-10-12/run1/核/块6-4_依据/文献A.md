# 块6-4 原文核查：文献 A

核查范围：`找空白.md` 的块6-4所引前三篇论文；这里只判论文是否有被归给它的方法或结论。页码一律为下面保存的全文 PDF 从 1 开始的页序，不是出版页码。

## 1. Dantam 等 2018：IDTMP

**题录核实：** Neil T. Dantam、Zachary K. Kingston、Swarat Chaudhuri、Lydia E. Kavraki，*An Incremental Constraint-Based Framework for Task and Motion Planning*，DOI `10.1177/0278364918761570`。作者全文首页印有该 DOI；Crossref精确 DOI 记录的题名一致。采用 Kavraki Lab 的20页作者稿，[原文 PDF](https://www.kavrakilab.org/publications/dantam2018incremental-tmp.pdf)，本地全文：[dantam2018.pdf](dantam2018.pdf)、[转写](dantam2018.txt)。

**完整原文句（§7.3，PDF p.13；12词）：**

> Using constraint (5), we generalize motion planning failures to all task steps.

**逐项核对：**

- 「§7.3–7.4 把失败推广到阻挡物」：**成立，但应细分。** §7.3式(5)在固定状态下排除同一失败动作的所有任务步；§7.4式(6)把固定整个状态替换为仅固定碰撞检测中涉及的物体位置，因此可排除多个状态。依据是PDF p.13；撤销这些约束的规则见p.14。
- 「§7 把超时和证出不可行分开」：**部分成立，原说法容易误导。** §2.3（PDF p.3）和§7.1、§7.3（pp.12–13）明确说明采样式运动规划一般不能证明运动不存在；有限时限内失败只是暂时避开，步数与采样时限增大后重试。§7.4（pp.13–14）同样撤销碰撞推广约束。论文没有低层求解器的 `UNKNOWN/INFEASIBLE` 二值证明接口，更没有从低层取假设文字不可满足核。作者所证明的是整个搜索的概率完备性。
- 「IDTMP 推广依赖后配置连通」：**成立。** §7.1定义8–10（PDF p.12）定义配置集、计划后配置、状态后配置；§7.3（p.13）明确要求状态后配置连通，才能将一个配置的失败推广；§7.4末尾（pp.13–14）沿用同一假设。不能据此把阻挡物集合称为已证明的最小不可满足核。

**剩下的依据：** 这篇支持“反馈粒度越小、能影响更多上层候选”的设计思路及“搜索失败不可永久排除”的边界；对块6-4的证明型不可满足核方法只属类比，未给出该方法本身。

**获取记录：** `python3 lit.py full 10.1177/0278364918761570` 能解析KEY，但返回“没有拿到开放获取的 PDF：无链接”；采用上述作者网站原文并复核已有全文。这不是KEY查不到。

## 2. Garrett 等 2021：Integrated Task and Motion Planning

**题录核实：** Caelan Reed Garrett、Rohan Chitnis、Rachel Holladay、Beomjoon Kim、Tom Silver、Leslie Pack Kaelbling、Tomás Lozano-Pérez，*Integrated Task and Motion Planning*，DOI `10.1146/annurev-control-091420-084139`。Crossref精确 DOI 记录与题名一致，正式刊于 *Annual Review of Control, Robotics, and Autonomous Systems* 4（2021），265–293。采用 [arXiv:2010.01083v1](https://arxiv.org/abs/2010.01083v1) 的30页作者稿，[PDF](https://arxiv.org/pdf/2010.01083v1)，本地：[garrett2021.pdf](garrett2021.pdf)、[转写](garrett2021.txt)。

**完整原文句（§3.4.2，PDF p.22；15词）：**

> The smaller a counterexample is, the more h-csps and thus plan skeletons it can prune.

**逐项核对：**

- 「§3.4.2 共享不可满足的子问题」：**成立。** p.21说明任一混合约束满足问题（h-CSP）只要包含不可满足子问题，整体也不可满足；因此可记录并复用失败子问题，剪掉尚未探索但包含同一失败结构的任务骨架。
- 「反例越小，排掉的越多」：**成立。** 上述完整原句直接支持该结论。p.22随后明确提到SAT不可满足核，且指出找小反例可能本身费时，需要将原h-CSP拆成较小h-CSP并分别测试不可满足性；该节参考文献80是最小不可满足子集算法论文。
- **边界：** p.21–22同时指出许多连续低层求解器仅能半判定：暂视为不可满足时，必须继续分配搜索线程，有解后撤回反例。本文是方法综述，不给出CP-SAT假设文字接口、转置推广、本题逐格精确模型或性能保证。

**剩下的依据：** 这是三篇里对“已证明不可满足子问题回传上层、缩小核提高剪枝覆盖”最直接的支持；其可迁移的前提是候选确实包含同一个完整子问题及依赖条件。

**获取记录：** `python3 lit.py full 10.1146/annurev-control-091420-084139` 能解析KEY，但未取得出版社PDF，返回链接 `https://www.annualreviews.org/doi/pdf/10.1146/annurev-control-091420-084139`；采用上述arXiv作者稿全文。不是仅凭摘要，也不是KEY查不到。

## 3. Patterson 等 2023：Factorio Blueprints

**题录核实：** Sean Patterson、Joan Espasa、Mun See Chang、Ruth Hoffmann，*Towards Automatic Design of Factorio Blueprints*，[arXiv:2310.01505v1](https://arxiv.org/abs/2310.01505v1)，2023-10-02提交。采用该版本的16页全文，[PDF](https://arxiv.org/pdf/2310.01505v1)，本地：[patterson2023.pdf](patterson2023.pdf)、[转写](patterson2023.txt)。

**完整原文句（§5，PDF p.12；23词）：**

> Beyond this size, runtimes increase rapidly and soon become intractable due to the number of failed attempts and subsequent retrying of each stage.

此句的“this size”承接前一句约100格、生成耗时数分钟的规模。

**逐项核对：**

- 「只禁整个解」：**不完全成立。** §4.3.1（PDF p.10）记的是机器配方及各机器搬运臂的总数，不记录每个搬运臂分配哪种物料，因后者改变不能修复装箱失败。§4.3.2（p.11、Listing 6）只记机器布局的0/1矩阵；后续阶段检查搬运臂的所有布置并重新分配机器身份。因此它排除的是阶段接口的聚合候选，不是整厂所有变量的一次完整赋值。这些排除仍然比结构化小核粗，但不能说它完全没有归并。
- 「回退次数爆炸」：**作为经验性规模瓶颈部分成立。** §4.3（p.8）描述下层不可满足就让上层换解；§5（p.12）把超出约100格后的不可处理归因于失败次数和逐阶段重试。没有证明回退次数呈指数增长，也没有实测对比“完整排除”与“最小核排除”，不能将该数据当作小核回传有效的因果证明。

**剩下的依据：** 论文给出一个工厂游戏中的多阶段反馈瓶颈，能作改进反馈粒度的动机；它没有实现不可满足核回传，也没有证明块6-4会更快。

**获取记录：** `python3 lit.py full arXiv:2310.01505` 成功返回 `cache/full_043b4cfab548e715.txt`；核查以该全文为依据。KEY与题名匹配。

## 证据文件与可复查性

三份全文从已有缓存复制到本目录，文件大小和SHA-256见[文献A_manifest.json](文献A_manifest.json)。Dantam与Garrett的题录另存[Crossref记录A](dantam2018_crossref.json)、[Crossref记录B](garrett2021_crossref.json)。引句每篇只取一句，其他核对均为释义；三篇都取得了全文。
