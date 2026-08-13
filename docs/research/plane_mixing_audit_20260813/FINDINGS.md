# 三面防污染架构审计——发现与挂账登记（2026-08-13）

> **性质**：一次性审计证据（historical timepoint evidence）＋挂账登记。方法＝三席审计（codex 标本核实 / codex 批次落地状态 / opus 开放缺口侦察）＋ codex 异源对抗核查（opus 七条初判：4 WEAKENED / 3 REFUTED / 0 以原强度 CONFIRMED）。
> 本页「当前」均指 2026-08-13 HEAD（`52d5295` 时点）的字节实况。**挂账行的现行入口＝`27_status_dashboard.md` §9 A12**；owner 同日三笔拍板见 `00_master_roadmap.md` 文末（`5191abe` / `b3500cc`）。

## 1. 挂账（未做，带触发器）

| # | 内容 | 触发器（将来谁必须看到） |
|---|---|---|
| D1 | **三门 PASS 文案不自带「不证什么」限界**（FIRST_PRINCIPLES_DESIGN §1.9 义务未实施）：`check_p1_2_proof_obligations.py:14348-14355`、`check_strong_status_write_allowlist.py:774-777`、`preflight_gate.py:1207-1209` 成功输出均只报喜；且 preflight `:554-555` 只转发子 checker stdout 最后一行（子 checker 早行免责声明会被丢弃） | 三文件均 byte-pin（obligations checker 受 manifest 钉、allowlist checker 受 checker:12928 钉、preflight 受 Chain C parity 钉）——**挂下一次触及任一文件的 Chain B/C 批顺走，不单开** |
| D2 | **`EXACT_MASTER_FRONT_CLEAR_LIFT` 残余风险**（对抗核查后降为中低）：它是 V80 operational allowlist 55 项中唯一「效果为加约束」的项（`benders_loop.py:1359-1368`，命中即 `:1578` continue 跳过判定），放行后无机制周期性复证其计数等价定理前件（demand SSOT 漂移＝超杀方向，`test_front_clear_lift_demand_ssot.py:10` 自认）；最强的 full-pool 双向 golden（`test_front_clear_lift_full_pool_golden.py`）未接活门禁。已有防线：F-GM-FCL-01（PROJECT_LOCK:425）＋runtime guards（`exact_coordinate_master.py:3827-3910,:3982-4030`）＋双向测试 | **redesign 批 5/6（方向暴露/哨兵）范围** |
| D3 | **零税措辞止血批（待做，无 owner 依赖）**：①`src/rules/semantic_validator.py:5-92` 七处「违反冻结真理」文案簇——发布面登记纪律穿游戏语义口吻，且桥文案与 `canonical_rules.json:444-445` 的「无物理高度」澄清直接矛盾；②`scripts/package_review_snapshot.py:378-386` 把结构收据命名为 `proof_checker`（被指 checker `:4-6` 自认 not a theorem prover）；③`scripts/b_design_v2_exit_criteria.py:94-100` **真 bug**——Criterion #1 自称「boundary 语义冻结」，pose count 不符只写警告仍返回 PASS（PASS 强度低于自报判据）。另两处**存疑**挂各自 reseal 批：`certified_artifact_contract.py` 的「theorem」措辞、`power_hitting_set.py:160-166` 的「truth」（均 V99 pin，纯文案也触发 Chain B） | ①②③不在 FROZEN/V99 名单，独立小批可做（仍改 certified source digest，认证跑期间勿动）；存疑两处挂各自 reseal 批 |

## 2. 幸存缺口（对抗核查后仍站住的）

- **主缺口**：`model_stricter_faces` 完备性条款（`canonical_rules.json:433`「Absence from the ledger is not evidence of equivalence」）**零机器强制**——全仓唯一消费点是一条测试注释；6 个在册面全为自由文本，无结构化 `wlog_bundle` 类字段；**不存在「源码收窄约束全集 ↔ 台账」的对账装置**。承载＝已立项 redesign 线的正当表/MODEL_CORRESPONDENCE 与批 2/3/6。
- 次级：无通用「模型变严检测器」（D-19 是设计规格非现行闸，FINAL_DESIGN:3-10,:185-191）；proof obligations 75 处 `docs/research/**` evidence_paths 只验存在性（`check_p1_2_proof_obligations.py:3107-3110`，currency 债，低——authority 隔离已由 `code_assets.json:562-577` 覆盖）。

## 3. 被推翻/降级的初判（登记以防将来再立案）

- **整条推翻**：①对称破缺无 WLOG 载体——F-GM-R8-SYM-01（PROJECT_LOCK:398）＋full-pool same-order gate（`exact_coordinate_master.py:2829-2889`）＋反过剪测试（`test_master.py:1213-1270`）都在；「per-slot bucket_region 破坏可互换性」系读错（region 是 group-level）。②过严侧无 soundness 学说——PROJECT_LOCK `:364/:386/:389/:394/:398` 五条拒真条目＋可行性回归＋26 手册:207-213「过严+最优性证明=假证书」都在。③cut assumption verifier 不验前件数字＝洞——F1 真承重量由 typed validator 从冻结快照重算（`region_capacity_typed.py:240-294`），冗余注记字符串不承重，最多 LOW 级元数据债。
- **勿动清单（已覆盖，别再开药）**：V80 env 守卫本身（真 deny-by-default、双向完整）；cut 层过剪方向天然双向防线；候选池 rederivation 比对（`pr2_l0_artifact_core.py:622-648`，静默收窄不可能）；`semantics.boundary_placement`＝全仓「反过剪纪律＋实现锚点」齐全的样板条款；B15 处置链完整（env 门控＋default-OFF＋可执行 fallback ladder＋独立复验隔离＋F-BIND-R8-01——历史指控「ladder 只在 docstring」对当前树**不成立**）。

## 4. owner 拍板与下游义务指针

- 立项／账本接口联合结论四条／semantics 拆分「先实验后拍板」：`00_master_roadmap.md` 文末两条（`5191abe` / `b3500cc`）。
- **档案面批（OWNER_RULING_EVENT）开工时须知**：回填 `data/knowledge/decisions.jsonl` 的 `ruling_event_id` 并将整本翻转为 GENERATED_PROJECTION 或退役；`representation_class` 的 enum 扩类裁定权在该批。操作文本＝文档评审线交接文档 §8（`~/下载/zmd_文档补丁链落地评审交接_20260813.md`，将随 GPT Pro 适配批入仓）。
- 重设计线门牌已同步：`OWNER_DECISION_SUMMARY.md` 头部 2026-08-13 状态追记。
