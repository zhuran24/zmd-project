# M5 归因线：C1 6×6 内存撞帽的成因调查（2026-07-10 开）

> 入口事实（1F B 段 smoke 五连，`07_batch1f_evidence.md`）：产品 C1 在 6×6 直建裸
> solve >42G OOM 未出解；b0_4r 原型（07-09）同机同题 OPTIMAL@541s「<20G 温和」。
> 初始假设=批 1 产品化引入回归。本文档记录归因实验链与结论演化。

## 第一刀：batch0 HEAD 复刻 b0_4r（88f65a5 worktree + 原型 patch）—— 撞帽

- 形态：worktree @88f65a5（runner 路径 sed 到 worktree），主仓 venv（ortools 9.15.6755
  无漂移，工件 hash 88f65a5 时代 checker 验证通过），w6 free 6×6，42G 硬帽+taskset 4,5。
- 结果：**exit 137，OOM @~8min**。build 段与 b0_4r 逐项一致（prototype 标记、
  cover_lits=4900、core 10.2s/master 15.4s）；solve 段 RSS 曲线 2.5min@13.8G →
  5.5min@15.4G(HWM 18.6) → 7.6min@27.3G → 撞帽。
- **推论：「批 1 产品化引入回归」假设大幅弱化**——原型代码自己都复现不了 b0_4r。
  同代码+同工件+同 ortools+同机器，隔天结果天壤之别。

## 执行形态考古：b0_4r 原跑与复刻的差异（`~/m5_runs/b0_c1_retry_w6.sh`）

| 维度 | b0_4r 原跑（07-09） | 第一刀复刻（07-10） |
|---|---|---|
| `EXACT_SUBPROBLEM_MAX_MEMORY_MB` | **=34000 已 export**（脚本 :6） | 未设 |
| taskset | 无（全 24 核可用） | `-c 4,5`（2 P-core） |
| cgroup 帽 | 无 | 42G |
| `__pycache__` 清理 | 有（:10） | 第一刀无 |

**头号新嫌疑：env 软 cap 丢失**。`EXACT_SUBPROBLEM_MAX_MEMORY_MB` 经
`apply_subproblem_memory_cap`（`cp_sat_worker_config.py:140-149`）落到 CP-SAT
`max_memory_in_mb=34000`；master 的 `solve()` 也走这条（`master_model.py` solve 段）。
docstring 自认「不限 OS RSS」，但它改变 solver 内存行为（clause cleanup/内部预算）。
1F 全部 smoke 与第一刀复刻都没设它。次嫌疑：taskset 2 核挤 6 worker 改变搜索时序轨迹。

## 侦察线（并行）：原型 vs 产品结构差异（代码层）

sonnet 侦察定稿（codex 同题在跑）：两版**唯一实质结构差异**=容量族有效不等式——
原型 `power_pole_family_count_vars={}` 恒空、`_add_global_valid_inequalities` 整段
跳过（patch 文档自认「跳过=更弱但 sound」）；产品每 family 建 IntVar+`count==sum`
链接+每受电模板需求不等式（`exact_coordinate_master.py:3307-3387,6939-7018`）。
已排除为非差异：决策策略（两侧都不引导杆 bool，residual pop 掉 power_pole）、
solve() 参数逐字节同、cov 通道/witness/dominance 形状同、目标无杆项、对称破缺两侧均无。
——若第二刀复现成功，此差异降级为次要优化候选；若非确定性假设上位，它仍是
「产品分布可能更差」的候选因子。

## 统一尖峰理论（第一刀曲线触发，待第二/三刀检验）

第一刀曲线形态：稳态 11-15.7G 走 7min → **45s 内 15.4G→38G 断崖** → 撞帽。与全部
已知死亡事件同形态同时刻：

| 跑 | 稳态 | 尖峰 | 死亡/出解时刻 |
|---|---|---|---|
| b0_6（w24 原型） | 11-16.6G | 3s +26G | 9min03s 死 |
| smoke#1（w6 产品 70×19） | 12-17G | 40s +24G | 9min47s 死 |
| 第一刀（w6 原型 6×6） | 11-15.7G | 45s +23G | ~8min 死 |
| smoke#2/#3/#4 | —（无曲线，journal 42G peak） | — | 9-10min 死 |
| **b0_4r（w6 原型 6×6，无帽）** | 「温和」 | **未被观测**（30s 采样全空） | **541s=9min 出解** |

**理论**：C1 solve 在 ~8-10min 有固定的阶段切换大分配事件（尖峰需求 ~44G，内核
anon-rss 证据 43.9G×3）；b0_4r 不是没有尖峰，而是**无 cgroup 帽 + 物理 47.7G +
zram swap 46G 兜底把尖峰挤过去了，且尖峰成功=出解，出解=进程结束释放**。「w6 温和
<20G」是 30s 间隔采样只看到稳态的观察假象（b0_4r rss.log 实为全空，观察级说法）。
产品 vs 原型、w6 vs w24、6×6 vs 70×19 都不改变尖峰量级——**1F 的 42G 帽+
MemorySwapMax=0 恰好低于该尖峰的真实需求，把 b0_4r 时代靠余量挤过去的路堵死了**。

若理论成立：①无代码回归（产品=原型同分布）②1F 内存条款需修订（帽值 42G 不可行，
或允许有限 swap）③M5 真正议题=把尖峰本身降下来（阶段切换大分配的机理定位）。

## 第二刀：完整复刻 b0_4r 执行形态（进行中）

- 变更：+`EXACT_SUBPROBLEM_MAX_MEMORY_MB=34000`、去 taskset、+`__pycache__` 清理；
  保留 42G 硬帽（保护系统，若真 <20G 则不干扰）。
- 结果：**exit 137，OOM @~7min（solve 段），HWM 41.95G**——理论预测命中。全核让稳态
  更快到达尖峰事件（7min vs 第一刀 8min），支持「事件由搜索进度触发而非墙钟」。

## codex 侦察定稿（关键事实纠正 + 结构差异终表）

1. **纠正**：b0_4r runner free 模式自设 `EXACT_MASTER_SEARCH_BRANCHING=automatic +
   PROBING_LEVEL=1 + SYMMETRY_LEVEL=1 + EXACT_SUBPROBLEM_MAX_MEMORY_MB=28000`
   （`batch0_prod_runner.py:30-35`，os.environ 赋值会覆盖外部 export）——因此第一/二刀
   复刻（同 runner）**已自动携带全套 env**，第二刀实为「除 cgroup 帽外的完整 b0_4r
   形态」，仍撞帽。**执行形态差异收敛到唯一变量：42G 帽+MemorySwapMax=0 vs 无帽+zram**。
2. 产品 vs 原型结构差异终表（针对 smoke#4，与撞帽根因解耦但影响 solve 分布）：
   - HIGH：solve 参数——产品默认 `FIXED_SEARCH+probing3+symmetry3` vs 原型 runner
     显式 `automatic+probing1+symmetry1`（`master_model.py:11550`）。
   - HIGH：产品独有 family-count×ghost-anchor big-M 条件上界网络——
     `count_f == Σp_k`（`exact_coordinate_master.py:3358,3379`）+ 每 ghost anchor
     每受削 family 一条 `count_f <= ub + M(1-ghost_u)`（`:4445,4465`，规模上界
     4225×F）；原型 family dict 恒空全段 no-op。共享 hub 连接 4761 pole bool +
     F family IntVar + 4225 ghost bool，最符合「build 正常、solve RSS 爆」的放大器。
   - MED-HIGH：聚合 power-capacity 下界（`:6941,6976`），原型 guard 直接返回。
   - 已排除：cov/witness/dominance 同构、interval 对（9522）同、NoOverlap2D 同、
     两版均无目标函数（b0_4r 的 OPTIMAL=satisfaction 可行即收）、决策策略结构同
     （杆 bool 两版都不进显式策略）、search profile 两版同为 v4。

## 第三刀：无帽裸跑复刻（理论最后一环）

- 形态：runner 原样（env 三件套+软 cap 自带）+ 无 taskset + **无 cgroup 帽**，
  纯靠物理 47.7G+zram 46G（=b0_4r 原始条件；主机空闲 41G，风险可控，系统 OOM killer 兜底）。
- 预测：~9min 尖峰事件靠 zram 挤过 → 出解 OPTIMAL（wall 可能因 swap 略长于 541s）。
- 结果：**OPTIMAL@525.4s，branches 4,982,981，conflicts 1077——b0_4r（541.3s/
  4,953,549/1077）完美复现**。资源证据：HWM 41.58G + **VmSwap 峰值 18.57G**（尖峰
  事件真实需求 ~60G 级，zram 兜住溢出），出解后 RSS 回落 16-17G。wall 反而更快
  （swap 对短暂尖峰的性能损失可忽略）。

## 终判（2026-07-10 晚）

1. **无代码回归**：原型同参数同轨迹完美复现（conflicts 逐位相同=solve 确定性），
   「产品化 C1 内存+求解双回归」（1F B 段初判）**被推翻**。
2. **「b0_4r 单样本幸运/非确定性」假设排除**：搜索轨迹确定性复现。
3. **根因=资源条款低于固有尖峰**：C1 6×6 solve 在出解时刻（~8.5-9min）有一个固有的
   大分配尖峰事件（RSS 需求 >42G、总需求含 swap 溢出 ~60G 级）；b0_4r 与第三刀靠
   「无帽+物理 47.7G+zram 46G」挤过尖峰并出解；1F 的 42G 帽+MemorySwapMax=0 恰好
   斩断了这条生路——smoke#1-4 与第一/二刀六连灭全部死于同一个尖峰事件。
4. **「w6 温和 <20G」考古定性**：观察假象——b0_4r 的 rss.log 30s 采样且全空，
   稳态 11-17G 被当成了全程；尖峰+swap 溢出从未被观测到。
5. 产品 vs 原型结构差异（fixed/probing3/symmetry3 vs automatic/probing1/symmetry1、
   family×ghost big-M 网络）与撞帽根因解耦，但仍是产品 solve 分布的未验证变量
   ——第四刀（产品+原型参数+无帽）是 M5 A/B 的入场券。

## 第四刀：产品 C1 + 原型参数 + 无帽 —— 产品完美出解（M5 A/B 解锁）

- 形态：主仓 HEAD 产品 C1 直建 + env 对齐原型（automatic/probing1/symmetry1/软cap
  28000）+ 无帽 + 无 taskset。
- 结果：**OPTIMAL@506.5s，branches 4,995,955，conflicts 1076，HWM 41.76G，
  swap 峰值 18.09G**——与第三刀原型（525.4s/4,982,981/1077/41.58G/18.57G）几乎逐位。
- **终判补全**：产品 C1 与原型同分布（产品甚至略快）；codex 侦察的两个 HIGH 结构差异
  （family×ghost big-M 网络、聚合容量下界）对 solve 行为无实质影响（branches/conflicts
  几乎相同）；参数默认值差异（fixed/probing3/symmetry3）未单测但已非阻塞项——
  A/B 实验设计自选参数即可。**M5 A/B 战场正式解锁**。

## 第五刀：修订条款验证（42G 帽 + MemorySwapMax=20G）—— 绿，条款定稿

- 结果：**OPTIMAL@512.9s，branches 4,898,023，conflicts 1076，HWM 41.93G（帽内），
  swap 峰值 18.08G（zram 吸收）**——wall 无损失。修订条款实测可行。
- 已落地（同日）：wrapper `MemorySwapMax` 0→可配 `CAMPAIGN_SWAP_MAX`（默认 20G，
  同款白名单校验 fail-closed，0 仍合法=显式禁 swap）；gate w6 档语义重写
  44→20（=稳态 17G+余量；**尖峰生存责任转移给 cgroup 条款**，gate 只守
  「稳态×parallel+host 不挤爆物理」）；dry-run 三形态验证过（新属性上链/
  infinity exit4/0 合法）。大 anchor（70×19+）在新条款下仍不可行（尖峰需求更高），
  本机 campaign 需限 anchor 或等 M5 降尖峰。

## 派生行动（全部落地，2026-07-10 晚）

- ✅ 1F 条款修订：wrapper `MemorySwapMax=20G` 默认（可配 `CAMPAIGN_SWAP_MAX`，
  第五刀实测背书）。
- ✅ gate w6 档语义重写 44→20（稳态模型，尖峰责任归 cgroup 条款），27 测绿。
- ✅ `07_batch1f_evidence.md` 归因后记；roadmap 撤「双回归」。
- ✅ memory 卡 `c1-solve-peak-memory-truth`（尖峰真相+采样纪律）。
- → M5 A/B 解锁；「C1 family 引导接入」等性能实验按 A/B 框架推进；
  大 anchor 尖峰治理（降尖峰机理定位）列 M5 议题。
