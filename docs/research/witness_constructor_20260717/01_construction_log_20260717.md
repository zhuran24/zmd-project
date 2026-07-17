# witness 构造战役日志（2026-07-17 凌晨离线时段）

> 决策包（`rab_sep_promotion_20260716/07_owner_decision_package_20260717.md`）
> 牌 A 的执行记录。目标：构造放下全部 266 mandatory + 留 6×7 空矩形、
> front-clear 审计零违规的布局（witness placement），随后真 binding 复核。
> 全部 research-grade、zero-sealed；产物在 `.artifacts/witness_20260717/`。

## §1 几何事实（本批实测建立，此前无文书记载）

1. **口格悬空**：制造件端口格不在 body 内——body 外 1 行（口行），front
   再外 1 行。TB 形态实测（5×5）：body y∈[2,6]，in 口 y=7（dir N），out 口
   y=1（dir S）；front = 口 + `_DIR_DELTA[dir]`（再外一格）。
2. **口向只有四种对侧形态**：TB/BT/RL/LR（in 全一侧、out 全对侧），每模板
   四分。无单侧/L 型口——任何件都必然向两个对侧各伸须。
3. **须 = 口格(1) + front 格(1) 的 2 格纵深**。demand（SSOT:
   `routing_visible_port_demands`）极小：5×5 = (1,1)/(1,2)，3×3 =
   (1,1)/(2,1)，6×4 同量级。
4. **足迹算术**（决定一切的三本账）：
   - 整行留空带式布局：每件足迹 = body + 2×宽侧 → 总需 ~5,400 格 >
     4,900 —— **规则带式被算术判死**，与实现无关；
   - 点状保留（口+front 各 demand 个）：~4,750 / 4,900（余 3%）；
   - **只保 front 格**（binding/审计口径；口格语义属 routing）：~4,100 /
     4,900 —— 此口径下须点甚至可以不共享。
   ⇒ witness 布局必然是不规则密铺；这也部分解释 lift 后 master 的搜索
   硬度（可行解在 3% 余量的密铺空间里极稀）。

## §2 构造器战绩表（placed / 266，front-clear 审计全部 0 违规）

| 版本 | 策略 | placed | 备注 |
|---|---|---|---|
| greedy v0 | 散点贪心 + 全 front 保留 | 204 | |
| greedy v1 | demand 计数保留 + 共享优先 | 217 | 排序/ghost 位不敏感（217/217/216） |
| comb v1/v2 | 梳状带（带 pass 因几何认知错全废）+ 散点兜底 | **241** | 贪心系冠军；兜底=小件先 |
| skyline | 单调 skyline + 点状须 | 193 | 单调性锁死孔隙回收 |
| BL v2-v4 | 精确 bottom-left 全朝向 ± 共享 front ± best-fit | 222-226 | best-fit 反而 -4 |
| BL v5 + 重启矩阵 | 小件先 + ghost/种子扫描 | 226-229 | 贪心天花板 ~230-240 确认 |
| cpsat v1/v2/v3 | CP-SAT 装箱可行性（NoOverlap2D ~760 矩形，front-only 须点，ghost 位置自由变量；v2 +同 op 字典序对称破除；v3 +四朝向+241 件 warm hint） | — | 120s/300s/600s **三连 UNKNOWN** |
| cpsat v4 | 四朝向 + maximize + 变尺寸 optional interval | — | ortools 9.15 原生 SIGSEGV（core dump 08:40，非 OOM） |
| **cpsat v5** | TB-only + maximize + hint | **232** | 480s FEASIBLE；审计 0 违规、ghost 复核干净——maximize 全链打通 |
| cpsat v6 | 四朝向 maximize（per-mode fixed-size interval 绕 segv）+ hint | 229 | 600s；自由度更大反而更低=LNS 没爬完更大空间，非可行域问题 |
| cpsat v7 | v6 配方 + v5 解接力 + 1800s（setsid 独立进程） | 231 | FEASIBLE 1802.6s；30 分钟 LNS 仍爬不过贪心 241——CP-SAT LNS 在此问题上弱于结构化贪心，收官铁证 |

反直觉实测两则：①小件先 > 大件先（3×3 先自组织共享 front 走廊网，
大件后进整块区）；②best-fit 贴墙评分输给首可行 BL（局部焊死制造新碎片）。

## §2b 收官判读（07-17 晨）

全工具谱（散点/梳状/skyline/精确 BL×4 变体/重启矩阵/CP-SAT 可行性×3/
maximize×3 含 30 分钟接力）一致卡在 **229-241 / 266**，缺口 ~25 件。
front-clear 审计全程 0 违规（12 发构造无一错），ghost 复核干净——
**构造机械是对的，装不满是问题本身硬**。这与 §1 的 3% 密铺余量账自洽：
witness placement 本质是接近完美的拼图，贪心和十分钟级 CP-SAT 都不够。
装箱侧的"难"反向抬升了负锚点侧（过夜跑 INFEASIBLE 证书）的相对价值——
详见决策包 doc 07 §6 的三点判读。

## §3 审计与诚实边界

- 每发构造后跑**真机械审计**（`port_front_status` × demand SSOT），全部
  版本 0 违规——构造器的 front 语义与 binding 机械已证一致。
- **口格可压性未查证**：本批审计口径只保 front 格（与 binding/审计机械
  一致）；若 routing 要求口格也空，点状预算回到 ~4,750，且 CP-SAT 模型
  须点要扩成 1×2。构造成功后进 routing 版本前必须先查这条语义。
- boundary 边缘容量 138/140（46 件 × 3 格 vs 两边 140 格）——几乎满，
  边缘件的放置几乎无自由度。
- 五月蓝图 hint（`data/hints/blueprint_2026_05_13_master_hint.json`，225
  件）**不可直接用**：pose_idx 是旧池（53,594,995 字节版）索引，对当前
  拐角修复后的池已错位（6 个越界+满图重叠实测）；源 IP v2 蓝图 JSON 不在
  仓库。跨版本重映射需 (anchor, orientation, port_mode) 链路 + 旧池文件。

## §4 下一步（按当前状态分支）

- cpsat v2 FEASIBLE → 反查 pose → 审计 → binding 空域复核 → 266 witness
  placement 达成，doc 07 牌 A 升级为「placement 完成，待 routing/power」。
- cpsat v2 仍 UNKNOWN → 待试杠杆：贪心解作 warm hint；放开 BT 口向；
  LNS（冻结贪心 227 件只解残余）；ghost 固定位枚举。
- **不做**：第二个 prod-scale solve（fc-lift-overnight 在跑）；触碰 sealed
  文件；把本构造器的任何产物当证明材料（witness 的可行性证明由多项式
  验证器终审，构造器只负责「找到」）。
