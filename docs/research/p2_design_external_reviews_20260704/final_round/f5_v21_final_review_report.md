# F5 轨道提升 soundness 论证稿 v2.1 终审报告

## 总体判定

- 定理层：修后可靠。三前提结构本身足以证明轨道提升 soundness；v2.1 的证明主线可成立，但需把 `immutable_scope` 白名单、presence-key alias、canonical re-query 一致性补成明文前提/实施义务，避免第四前提漂在实现里。
- 实施规格层：修后可靠。当前源码仍是 pre-P1.3 形态，不满足 v2.1 新规格：legacy `query(core,state)`、validator 不禁 `(group,pose)`、只有 sort+dedup、没有 `orbit_homogeneity_digest`。这些是 v2.1 已承认的待实现点，但作为唯一规格，文本还必须把“未核实/待门控”的项写清。

## 一、v1 审查发现修复保真终验

### BLOCK-1: liftable-reject 量词缺失

判定：PARTIAL。

v2.1 已把 liftable-reject 升为定理 2 前提：`docs/research/p1_3_f5_orbit_lift_soundness_design_v2.md:50-56`，并在证明中用它推出 `σ(A)` 不可行：`..._design_v2.md:56-58`。这修复了 v1 中“oracle 对 partial core 的 reject 可读 mutable state”的核心缺口。

剩余缺口：`immutable_scope` 只被描述为“冻结工件与候选级常量，ghost rect 经 scope 绑定”：`..._design_v2.md:54-54`，白名单不够认证级；§6 又把白名单留给 P1.3 定：`..._design_v2.md:87-87`。源码也仍是 legacy 协议：`src/cuts/oracles/pattern_nogood_oracle.py:73-79` 定义 `query(core,state,deadline)`，generator 调用时传入 `state`：`src/cuts/oracles/pattern_nogood_oracle.py:173-175`，validator re-verify 也传 `state`：`src/cuts/families/pattern_nogood.py:339-342`。

结论：定理语义修了，实施契约未充分定义。补丁见 `f5_v21_design_v2_1_review.patch` 的 §2.3 与 §4 修改。

### BLOCK-2: multiplicity 坍缩

判定：PARTIAL。

v2.1 采用方案 A：禁止重复 `(group_id, pose_id)`，并保留既有禁止重复 `(group_id, slot_index)`：`..._design_v2.md:52-54`。现有 validator 的确已禁 slot 复用：`src/cuts/families/pattern_nogood.py:193-195` 维护 `seen_slots`，`src/cuts/families/pattern_nogood.py:254-265` 拒绝重复 slot。但当前源码还没有禁重复 `(group_id, pose_id)`，也没有 canonical 形检查：`src/cuts/families/pattern_nogood.py:183-288` 只检查 triple、slot、pose_domain。

master 侧的 alias fail-close 属实：mandatory duplicate presence key 在 `src/models/exact_coordinate_master.py:7013-7016` 返回空，optional duplicate 在 `src/models/exact_coordinate_master.py:7034-7037` 返回空，`add_benders_cut` 收到空 entries 返回 False：`src/models/exact_coordinate_master.py:7056-7058`。presence nogood 的 shape 是 `sum(present_lits) <= len(present_lits)-1`：`src/models/exact_coordinate_master.py:7050-7077`。

剩余缺口：仅写 `(group_id, pose_id)` 不够强，实施层真正需要禁止重复的是 master attach 抽象后的 `presence_key=(group_id, attach_pose_key(pose_id))`。若两个不同 pose_id 解析到同一 attach key，boolean presence 仍会坍缩。当前 exact master 对 pose_idx alias fail-closed，v2.1 文本应把这一点提升为规格。补丁见 §2.3/§4。

### CONCERN-1: canonical relabel 定义不足

判定：FIXED as design, PARTIAL as sole implementation spec。

v2.1 定义了 idempotent `canonical_relabel`，要求 slot 重标为 `0..k_g−1`，并覆盖 generator、minimizer trial、oracle query、cert 存储：`..._design_v2.md:70-72`；validator 也要检查 `cert == canonical_relabel(cert)`：`..._design_v2.md:72-72`。这比 v1 的 sort-only 更正。

源码仍是旧实现：`canonical_sort_assignment` 只按 `(group,slot,pose)` 排序并 `dict.fromkeys` 去重：`src/cuts/helpers/bounded_core_minimizer.py:115-125`；cut 构造仍用它：`src/cuts/oracles/pattern_nogood_oracle.py:229-237`。silent dedup 对 multiplicity 审计不理想，validator 也不能“重标后继续”，必须拒绝非规范 cert。

补丁把 canonical_relabel 写成“不 silent-dedup、每次重标后必须重新复验”的硬规则。

### CONCERN-2: P-HOM 门覆盖 runtime pose pool artifact/digest

判定：PARTIAL。

正文承认 runtime pose 池不在验证范围：`..._design_v2.md:44-47`，并要求 `candidate_placements.json.facility_pools` 与 `orbit_homogeneity_digest` 进入 preflight/cut scope：`..._design_v2.md:46-46`、`..._design_v2.md:70-70`。

但 v2.1 顶部仍写“P-HOM 全量验证”：`..._design_v2.md:5-5`，标题也容易读成 P-HOM 已验证：`..._design_v2.md:30-30`。本审包未包含 `candidate_placements.json`、`placement_generator.py`、`binding_subproblem.py`、`routing_subproblem.py`；脚本输出为 `UNKNOWN_MISSING_ARTIFACT`，不能视作 P-HOM 全前提闭合。

当前 lifecycle 只有 generic `source_digest`，包含 `candidate_placements` 等字段：`src/cuts/lifecycle.py:92-101`、`src/cuts/lifecycle.py:504-520`；cert schema 没有 `orbit_homogeneity_digest` 字段：`src/cuts/cert_schema.py:69-75`。v2.1 作为规格应定义 digest payload 与 replay 位置。

### CONCERN-3: CP-SAT `symmetry_level=3` 定位

判定：FIXED。

v2.1 明确它是 solver 内部搜索/预处理策略，不是建模层第二全序；条件是 TIMEOUT/UNKNOWN 不产 cut，只有可复验 INFEASIBLE 产 cut：`..._design_v2.md:60-62`。这与 v1 审查要求一致。未发现新增缺口。

### CONCERN-4: 组合计数

判定：FIXED。

复算结果：manufacturing_3x3 八组 `log10(34!²·18!·17!·11!·6!³)=123.4708919507474`；全 mandatory 19 组 `log10 Π n_g! = 243.5039160328895`；`(34)_8 = 732,058,145,280 = 7.3205814528×10^11`。v2.1 的 `123.47/10^123.5` 与 `7.32×10^11` 写法正确：`..._design_v2.md:19-21`、`..._design_v2.md:78-83`。

### NOTE-1: mandatory P-HOM 数据本身无违例

判定：FIXED, 但受 CONCERN-2 限制。

本地复算：`mandatory_exact_instances.json` 为 266 条、19 个 `(facility_type, operation_type)` 组，除 `instance_id` 外逐字段违例 0。manufacturing_3x3 计数为 34/34/18/17/11/6/6/6，合计 132。

### NOTE-2: 定理 2 注入证明补严

判定：FIXED。

v2.1 证明步骤可追溯：多重集包含给出承载 slot 集；无重复前提给出注入；补全为每组置换；liftable reject 给出 `σ(A)` 不可行；P-HOM/定理 1 把不可行性传回 A：`..._design_v2.md:56-58`。

## 二、v2.1 新缺陷狩猎

### NEW-CONCERN-A: 谓词审计表有三行不可在本审包中核实

`placement_generator.py`、`binding_subproblem.py`、`routing_subproblem.py` 不在附件中，但 v2.1 直接引用这些文件作为 label-invariance 依据：`..._design_v2.md:36-40`。可核实的只有部分支撑：

- placement_rule: manufacturing 实例由 `instance_builder.py:48-70` 生成，记录字段无 per-instance 规则；template 规则在 `rules/canonical_rules.json:38-114`。
- operation profile: profile 由 recipe/utility operation 构造：`src/preprocess/operation_profiles.py:78-110`，需求聚合按 operation_type：`src/preprocess/operation_profiles.py:148-189`。
- power: `needs_power` 按 template：`src/models/master_model.py:2422-2424`；power support 扫描按 template/pose_idx：`src/models/master_model.py:3733-3794`。

binding domain 与 routing port specs 尚未闭合。建议把表格改为“当前证据状态 + 必过结构门”，不要把缺失源码当已证锚点。

### NEW-CONCERN-B: `immutable_scope` 定义不足

v2.1 的 `immutable_scope` 只说“冻结工件与候选级常量，ghost rect 经 scope 绑定”：`..._design_v2.md:54-54`，但未列出禁止项，也未说明 ghost rect、exterior_blocks、blocked_cells_hash 的 replay 关系。现有 BState 明确含 mutable `selected_poses` 与 `cell_owner`：`src/cuts/lifecycle.py:405-409`；现有 digest 刻意排除 `selected_poses`：`src/cuts/lifecycle.py:487-500`。这说明白名单必须写死。

ghost rect 应算 immutable only after scope binding：`CutScope` 保存 `ghost_rect_id/blocked_cells_hash/exterior_blocks_hash/source_digest`：`src/cuts/lifecycle.py:175-188`，Step 6 replay 检查这些字段：`src/cuts/lifecycle.py:941-984`。没有绑定时，ghost 相关 oracle reject 不能 lift。

### NEW-CONCERN-C: 方案 A 不过严，但应按 presence_key 表述

构造检验：同组 demand=2，cert 为 `[(g,0,p),(g,1,q)]`，p 与 q 不同。正确 cut 是“p 与 q 同时出现不可行”。现有 multiset evaluator 统计 `(group_id,pose_id)` demand：`src/cuts/lifecycle.py:1045-1069`；master presence nogood 会生成两个 presence lit 并施加 `sum<=1`：`src/models/exact_coordinate_master.py:7050-7077`。只出现 p 或只出现 q 不触发，所以禁重复 `(group,pose)` 不会误杀这种不同-pose 场景。

真正的边界不是“不同 pose 是否被禁”，而是两个不同 pose_id 是否 alias 到同一 attach presence key。v2.1 应显式禁止 presence-key alias。

### NEW-CONCERN-D: v2.1 仍把 F5 当前源码状态和 P1.3 目标状态混在一起

当前源码状态：validator 没有 `(group,pose)` 检查；oracle 协议仍读 state；canonical 仍 sort+dedup；cert schema 无 orbit digest。检查脚本输出：`validator_has_seen_group_pose_check=false`、`oracle_protocol_still_takes_state=true`、`canonical_sort_only_sort_dedup=true`、`cert_schema_has_orbit_homogeneity_digest=false`。

这不直接驳倒定理，因为 v2.1 标明 F5 尚未接生产。但作为“唯一规格”，应把这些列为 MUST, 而不是留给读者从历史源码推断。

## 三、补丁摘要

详见 `f5_v21_design_v2_1_review.patch`。核心替换：

1. 把“P-HOM 全量验证”改为“mandatory-side P-HOM 验证”；§2.2 表格增为“当前证据状态 + P1.3 必过结构门”。
2. §2.3 前提 2 改为禁止重复 slot、重复 raw `(group,pose)` 与重复 master `presence_key`。
3. §2.3 前提 3 增加 `INFEASIBLE` 的“无完整扩展”语义与 `immutable_scope` 白名单/黑名单。
4. §4 把 canonical_relabel 写成 no silent-dedup、每次重标后必须重验；validator 必拒非规范 cert；adapter 必使用 `query_liftable`。
5. §6 不再把 immutable_scope 白名单与 F5 re-query canonicalization 留作开放问题。

## 四、可复跑脚本

`f5_v21_review_checks.py` 可从任意目录运行：

```bash
python3 f5_v21_review_checks.py /path/to/repo/root
```

在本审包上的输出保存在 `f5_v21_review_checks_output.json`，关键结果为：mandatory 266/19/0，manufacturing_3x3 log10=123.4708919507474，`(34)_8=732058145280`，candidate_placements 缺失为 UNKNOWN，三份谓词审计引用源码缺失。
