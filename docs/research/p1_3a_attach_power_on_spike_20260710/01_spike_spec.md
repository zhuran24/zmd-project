# P1.3A attach 通电 spike 规格书（主会话亲写定稿，2026-07-10 夜）

> 全项目唯一研究级风险的实测批（roadmap §1c/09 号计划 §P1.3A）：cut 体系接上后
> 能否及时变成有效 master 约束、收不收敛没有理论保证。exploratory 下通电，
> certified unsafe-map 禁用不动。HEAD 基线 `5e7c760`。

## §0 唯一问题与 GO/NO-GO（09:15,27-28）

CP-SAT Python 路径能否在预期时机把 cut 变成有效 master 约束？
**GO = prod-scale（266 instance + 目标 ~10K cut）端到端 master cycle 跑通，
wall-clock 退化 <50%**（对照=同参数 attach-off 基线，不是 M5 的 506s master-only）。
NOT GO → paradigm 层风险上桌（09:30-32，退路见 roadmap §4 L11）。

## §1 前置状态（2026-07-10 全绿，当日凑齐）

1. step_8 F1/F5/F6/F7 落地（M3）+ 逐族阶梯（M4）；F8 退役、其余族 fail-closed。
2. 通电前修复批 `68b4557`：F1 BState ghost 轴反置（soundness 级）/F2 scope 全 map
   严格相等/F3 step_8 入口完整性纵深——三 repro 翻绿。
3. **硬性前置①（sizing verdict §3.1）content-addressed literal 复用：M3-2 已落地**
   （exact_coordinate_master.py:776/:7782，p_k 即 content-addressed presence literal）。
4. **硬性前置②（verdict §3.2）active cut 预算：M4-A 已落地**（benders_loop.py:946
   `EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000`，stop-emitting 形态=CP-SAT 不可撤约束
   下唯一 sound eviction；:8054 docstring）。
5. prod-scale master 可出解（M5 归因判决：6×6 w6+automatic/probing1/symmetry1
   506s OPTIMAL；资源条款 42G 帽+20G swap `b25ba1d`）。
6. 通路现状：`EXACT_CUT_FRAMEWORK_ATTACH` env 非 false 即开（:7838），certified
   unsafe-map 拦截不动；`_maybe_attach_framework_cuts` 双接线点（:6323/:7493）。

## §2 实验序列（主会话执行，单发铁律）

- **E1 基线**：exploratory 6×6 LBBD 端到端，attach off。资源条款=42G 帽+20G swap+
  w6+原型参数（M5 第四/五刀同款）；RSS 1s 采样+VmHWM+VmSwap（SOP）。记 wall/内存/
  LBBD 迭代数/终态。
- **E2 通电**：同参数 + `EXACT_CUT_FRAMEWORK_ATTACH=1`（预算 2000 默认）。观测：
  wall 退化 %、`cut_framework_attached` 计数、拒绝 taxonomy 五桶、内存曲线对照、
  **解语义一致性**（exploratory 也验：E2 若出解，其 layout 过与 E1 相同的独立
  校验路径；attach 只应剪支不应改变可行解集）。
- **E3 预算抬档**（E2 达标才跑）：抬 attach 预算扫 5K/10K 档看 proto 劈叉曲线
  （literal 复用后 sizing verdict 预言的量级改善实测）。改动面=预算常量 env 化
  （`EXACT_CUT_FRAMEWORK_ATTACH_BUDGET` 加同名 env 覆盖，certified allowlist
  **不加**——exploratory-only knob 走 deny-unknown 天然拦截即可；此为本批唯一
  生产代码改动，几行）。
- cut 流量前提核查（E1 顺带）：6×6 LBBD 每 attempt 真实产出的 cut 量级未知——
  若天然到不了千级，E3 改造成合成注入（复用 sizing spike 的 m1_*.py 负载形态）。

## §3 三硬门采纳度拍板（TRIAGE §3，5.6 复审建议）

spike=exploratory 实验非生产通电，三硬门是 production integration 的门：
1. 原子封口（RFC-001）：**spike 不做**。F3 已落的 step_8 入口 integrity 纵深+
   接线层 fail-closed（c7cd6a0）构成 spike 级安全面。
2. F5 独立 verifier（RFC-002）：**spike 保持 F5 shadow/不 mutate master**（现状），
   通电族=F1/F6/F7。
3. ledger+dedup+epoch（RFC-003）：**spike 豁免**——单 epoch 单 master 场景，
   ghost conditioning（M4-A）已处理 anchor 切换退役。
三条全部记入 GO 后 production integration checklist（不因 spike 通过而消失）。

## §4 验收清单

- [ ] E1/E2 完成且 E2 wall 退化 <50%（GO 线）；E2 attach 计数 >0（真通电证据）
- [ ] 拒绝 taxonomy 无 integrity 桶异常（有=修复批回归，立停）
- [ ] 解语义一致性核验通过
- [ ] E3（达标时）：预算 env 化小改过 preflight+慢 lane（benders_loop 是钉面→reseal）
- [ ] evidence 文档 02_spike_evidence.md（曲线+判定）；GO/NOT-GO 判词写明
- [ ] 全程单发铁律+树冻结+解释器病 SOP（崩=coredumpctl 定性重跑）

## §5 分工

实验设计+规格书=主会话（本稿）；E1/E2 执行+判定=主会话（prod-scale 长跑+终审）；
E3 预算 env 化小改=codex（几行+测试）；E3 后 reseal=主会话。审查=E3 改动走
opus+codex 双审（纯实验记录不需审）。
