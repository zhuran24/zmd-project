# RFC-001/002/003 采纳度评估（2026-07-10 主会话技术预判）

> 对 GPT-5.6 Pro 复审三份 RFC 的逐份消化与项目语境化。**性质：通电线（M3 续/attach
> 晋升）开工时的设计输入预决策草案**；最终采纳在通电线规格书定稿，涉 PROJECT_LOCK
> 的部分挂 owner。

## RFC-001（typed validate-and-compile 收口）——方向采纳，分阶段

- 诊断成立：body/cert 双可写真相是 I-1 的结构根源；手工拼 gauntlet（I-5）与裸 tuple
  （I-2 温床）都是「类型系统不挡漏步」的同族病。
- **阶段 A ≈ 我们的修复批**（`01_fix_batch_spec.md` F1-F3）——批 1 后立即做，已规格化。
- **阶段 B（ValidatedStateSnapshot/ConstraintPlan/单入口 + 迁 F1/F6/F7）= 通电三硬门
  之一的本体**——通电线第一批。项目化调整两点：①`CompiledCut` 构造器不公开在 Python
  只能软约束（命名+lint+测试钉），文档点破而不假装硬边界；②测试义务里的
  differential test（plan 语义 vs master 实际约束小实例等价）与既有 helper-vs-master
  等价回归（M2 遗留义务）合并成同一族，别做两套。
- 阶段 D（schema v2 持久化）与通电解耦，后置。
- **FamilyCapabilityRegistry 取代「冻结 9 族」触碰 PROJECT_LOCK CUT-* 条款**——
  registry 若成为族数权威，锁条款要随之改写 = owner 拍板项，进通电 checklist。

## RFC-002（F5 独立 proof verifier）——立即策略零成本照做，verifier 通电线做

- 诊断完全成立，其中「adapter 的 operation mapping 藏在实例私有字段、不进 scope/digest」
  是实锤设计缺陷（跨 session 复用旧 mapping 的风险真实存在）。
- **立即策略 = 现状已满足**：attach 整体在 certified unsafe map，F5 无晋升路径；
  显式化「F5 晋升前置 = 独立 verifier 落地」进通电 checklist 即可，零代码成本。
- `binding_empty_domain_v1` 专用 proof + 独立匹配 verifier（RFC 估 2-4 人日）通电线做。
  关键采纳点：**verifier 若复用 `enumerate_pose_level_port_bindings()` 就必须列 TCB
  并加第二实现 differential 对照**——这与 I1 reverifier 的独立性哲学同构，照此执行。
- 与 1D 的 F5 adapter TCB classification 交互：classification 值的选择要体现
  「TCB 成员但 shadow-only、未独立验证前不 mutate master」的现状。

## RFC-003（ledger/epoch/dedup）——dedup 先行，epoch 概念按项目语境简化

- 「状态机在物理层没闭环」批判成立，但**项目语境收窄它**：certified 链每个 ghost rect
  的 master 是独立 build 的（run_benders_for_ghost_rect 级），「每次 master build =
  天然 epoch」已经成立；RFC 假想的「常驻 pool 跨 epoch 失效撤回」场景在当前架构里
  主要收窄为同一 controller 生存期内的 cut 失效。全盘 SQLite ledger 偏重。
- **采纳序**：①semantic fingerprint 严格等价去重（I-8 止血，指纹禁含时间戳/iteration，
  RFC §5 形态照抄）——通电线早批；②JSONL append-only 最小 ledger（APPLIED 记录 +
  restart 全链 replay，「不能直接相信上次 APPLIED」这条照单全收）——通电时；
  ③selector 打分/六维 watcher/family dominance——后置（RFC 自己也这么排）。
- 测试义务里最值钱的一条先记下：**batch0/C1 基线 cut off/on A/B（目标值+独立复验
  等价）**——这与 1F smoke 和 M5 A/B 可以共用基线数据，排期时合并。

## 通电前 checklist（汇总版，替代零散记录）

1. 修复批 F1-F4（`01_fix_batch_spec.md`，批 1 后）
2. RFC-001 阶段 B：typed 单入口 + immutable snapshot + F1/F6/F7 迁移 + differential 族
3. RFC-002：binding_empty_domain_v1 独立 verifier（F5 晋升前置）
4. RFC-003：semantic dedup → 最小 JSONL ledger + restart replay
5. owner 拍板项：PROJECT_LOCK CUT-* 条款 vs capability registry 权威；attach 晋升本身
   （lock 既有要求：family ladder + helper/master 等价回归 + owner 决定）
6. 5.6 Pro 原三硬门（原子封口/F5 独立/ledger+dedup+epoch）由 1-4 覆盖，rollback 演练
   （关 family 后从 ledger 重建 clean epoch）纳入 4 的验收
