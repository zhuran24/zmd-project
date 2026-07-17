# 批 3+5 合并换钉执行方案（点火前置文档，2026-07-18）

> **定位**：front 错位事故批 3（候选域补齐）与规则校对批 5（语义批）的合并
> 执行方案。两批**必须同批原子落地**：生成器语义改动与 45MB 池重生成互为
> 死锁（改生成器不换池 → rederivation 假红；换池不改生成器 → 生成不出来），
> canonical/preprocess_plan 语义改动又决定池的口形态——拆开做每一半都过不了门。
> **点火条件：owner 过目本方案后点头**（可行域扩大+协议箱语义翻转 → 最优解
> 本身可能变，属命题级变更）。批 2 已于 `bb415f1` 收口，本批是它的下一棒。
>
> 裁决依据：`00_owner_adjudications_and_rule_corrections.md`（本目录）+
> `../front_offset_incident_20260718/00` §5 批 0 裁决。

## §1 批 3 几何面：placement_generator 三处改动

1. **`get_port_front_cell`（:81-91）identity 化**：`front = port + DIR_DELTA`
   → `front = (port.x, port.y)`（stored 坐标即带子格）；docstring 里
   "outside-adjacent connector plus outward normal" 的旧语义描述整段重写。
   DIR_DELTA 表保留——`get_edge_ports` 生成口坐标时仍要按边法向定位体外
   第 1 格（那是"把口写在哪"，不是"front 在哪"，两者 identity 后重合）。
2. **`is_edge_starved`（:94-108）判界自动修正**：blocked 判据经 1 变为
   "stored 格出 70×70"。效果 = 墙距 1（口前格恰在最外圈）的 pose 不再被
   剪（owner 五图定谳图 3 坐实合法）→ mandatory 池 66,405 → **68,469**
   （+2,064：3×3 +544 / 5×5 +528 / 6×4 +520 / core +472，对抗席按池
   anchor 分布独立重算过）。体贴边朝外口全死的剪枝（图 2）在新判据下
   自动保留正确。
3. **`gen_protocol_storage_box`（:382+）从零口改为实体口枚举**：owner
   定谳=与制造机 3×3 完全同款 → 复用 `opposite_parallel_sides` 的四模式
   枚举路径（canonical `port_rule` 同步改，见 §2-1）。计数预期：4,624
   anchor × 4 模式 − 面壁死锁剪枝 ≈ **17,952**（与 3×3 制造机同款计数
   规律推得；实际以重生成后审计为准，批内做逐池计数对账）。供电覆盖
   字段不变（箱需电，批 1 前就正确）。

## §2 批 5 语义面：frozen 文本与需求账

1. **canonical_rules.json**：`protocol_storage_box.port_rule`:
   `"omni_wireless"` → `"opposite_parallel_sides"`；semantics 节新增四条
   裁决文（owner 07-18 定谳原文入库）：
   - **仓库桥排除**：桥物理真实（箱/中枢入仓后可从中枢出口+边界口再出）
     但挤占双矿输出产能、产量目标下无可行性 → "产线直连"为正式建模假设；
     产量目标变更（不再 3.0/2.75 线）时本条须重审；
   - **协议箱"无线"重写**：无线仅箱→仓库段（6 缓存格每 10s 瞬传）；
     产线→箱必须带子接实体进口；缓存双向特性属吞吐面（OUT-OF-SCOPE）；
   - **供电源头注记**：中枢为基地电源、杆无条件无限距离取电——"杆罩住
     =有电"模型效果等价（不改代码）；
   - **物品准入口排除**：1×1 过滤直行件不建模（几何/连通与直带等价，
     过滤属吞吐面）。
2. **preprocess_plan.json** `utility_operations`：
   - `protocol_core.generic_input_slots`: **0 → 14**（万能收货进仓库=
     14 口大协议箱；成品可不经箱直接进中枢）；
   - `wireless_sink` 条目改名/改语义为实体口 sink（`generic_input_slots: 3`
     数值不变=每箱 3 实体进口，但"wireless"命名与语义注记按新裁决重写）。
   - ⚠ additive-only 守卫（`preprocess_context.py`）只拦 `recipes`/
     `production_targets`/`commodity_roles` 顶层新键——本改动不触碰这三键，
     但改 frozen 文件本身走完整 freeze ritual。
3. **generic_io_requirements.json 重生成**（`src/preprocess/demand_solver.py`）：
   sink 槽供给账变为 箱×3/箱 + 中枢 14 → **最优解可能零协议箱**（可行域
   放宽方向）。`required_generic_inputs` 的计数语义在 demand_solver 重跑后
   按新供给面固化。
4. **F03/F04 锁链改判（LOCK）**：整条 "routing-free wireless final
   commodity 排除链"（F03-R3-01、F04-R4-01..04）的前提死了——成品
   （电池/胶囊）成为**真商品**：producer 输出口回归 routed source，sink=
   协议箱实体进口/中枢进口。改判面=`extract_port_specs()` 排除逻辑、
   `_filter_pose_binding_domain` 侧通道、deletion-core oracle 可见键、
   pose_bool 输出侧 demand/缓存、separator/L2 商品分类——五处全部从
   "排除 final"翻转为"final 按普通 routed 商品处理 + generic-input sink
   端接入"。dual-role 守卫（final 又当配方输入 → fail-closed）保留。
   ⚠ 这是本批**最大的在线语义改动**（批 2 只修了不可达面，这条在
   certified 主链上），LOCK 逐条改判 + 新增回归矩阵。
5. **specs/06** 协议箱节勘误 + 计数表更新（66,405/4,624 → 68,469/~17,952）。

## §3 Freeze ritual（原子提交内的执行序）

1. 生成器代码改动（§1）+ 语义链代码改判（§2-4）+ canonical/preprocess
   文本（§2-1/2）落盘；
2. `generate_all_pools` 重生成 candidate_placements.json（45MB 级）+
   demand_solver 重生成 generic_io_requirements.json；逐池计数对账
   （mandatory 68,469 / 箱 ~17,952 / 杆不变）+ 抽样几何审计；
3. 三处换钉：preflight `FROZEN_ARTIFACTS`/`EXTERNAL_FROZEN_ARTIFACTS` +
   `certified_artifact_contract.py` 源码常量（路径/sha/size）+ canonical
   双钉（LF 字节，`git show` 口径）；
4. FCL 全池 golden、RAB 哨兵、6 类回归矩阵等 fixture 面按新池重算/反转；
   新增批 5 回归（成品 routed 化的正反哨兵）；
5. obligations sink + V99 floor + strong-status allowlist 受影响条目
   reseal，checker 自钉**最后**；
6. 验收=双 checker + preflight `--full` + `--slow-tests`（rederivation
   此时按新生成器+新池字节比对，PASS 是硬验收）+ 逐池计数对账单。
   全程整树冻结纪律。

## §4 风险与 owner 过目要点

- **命题变更**：可行域三向放宽（+2,064 补域、箱口重生成、中枢 14 进
  sink）→ 此前一切"池内最优/UNSAT/上界"数字对新命题失效（批 4 重跑
  才有终值）；
- **成品 routed 化**是 certified 主链在线改动（非批 2 那种不可达面）——
  routing 连通性约束实打实变多，prod-scale solve 行为可能变（批 4 重跑
  时观测）；
- **磁盘/时长**：45MB 重生成+全链验收预计单机数十分钟级；一次只跑一个
  prod-scale 任务的铁律不变；
- **待 owner 的点**：①本方案整体点头；②`wireless_sink` 操作名是否保留
  （建议改名 `box_sink` 防语义误导，属 preprocess_plan 键名变更，改则
  连带消费点同批改）；③批 4 排期确认（批 3+5 落地后立即开跑历史重判）。

## §5 诚实边界

- 本文档为方案，未动任何代码/frozen 文件；计数 17,952 为推算值，以重
  生成后逐池对账为准；
- F03/F04 改判的完整条款清单以点火时 LOCK 逐条盘点为准（本文档列的是
  已知五处消费面）；
- OQ3-7（belt-belt 细分）仍开放，不阻塞本批（routing 层既有约束裁决）。
