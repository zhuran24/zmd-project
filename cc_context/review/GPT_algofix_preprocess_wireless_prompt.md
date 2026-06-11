# 终末地 IndustrialPlanner 精确求解器 — 委托实现: preprocess F-01/F-02 完整修复 (omni_wireless 候选几何 + binding 无线消费语义 + 工件/lock/spec/test 三件套)

## 任务性质 (新会话零历史, 委托实现 + 自验)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

上一轮 preprocess 链审查发现 2 个真缺陷 (F-01 P0 / F-02 P1), 验收方已在本地逐条复现坐实 (probe 输出与冻结工件 hash bit 级吻合)。审查原文与生成器补丁已归档在包内:
- `cc_context/review/algoaudit_preprocess_face_r1_REVIEW_20260612.md` (完整论证)
- `cc_context/review/algoaudit_preprocess_face_r1_20260612.patch` (生成器侧补丁, **已验证可干净 apply 且行为符合声称** — 21 tests passed / probe 0/0/0 / 新池 hash `adcc2a6e…`)
- `cc_context/review/algoaudit_preprocess_face_r1_probe.py` (不变量 probe)

你的任务: 以该补丁为起点, 完成**整条修复链**, 使 certified 路径在新候选几何下端到端自洽。审查方刻意没有伪造假端口绕过 binding——那个缺口现在由你按下面**已定死的设计决策**正式建模。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD master→binding→routing→flow)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 已定死的设计决策 (不要重新辩论)

**服从 canonical**: `rules/canonical_rules.json` 声明 `protocol_storage_box.port_rule = "omni_wireless"`; `rules/preprocess_plan.json` 给 `wireless_sink` 3 个 generic input slots、0 输出。语义 = **协议箱无任何实体端口, 其 generic input 消费是 routing-free 的 (无线, 不需要皮带送达)**。证据链四处一致 (canonical + schema enum + preprocess_plan + 生成器文件头注释), 唯一相反文本是 `gen_protocol_storage_box()` 里被改写过的 docstring (审查已证伪)。**不要**走"给箱子保留端口/撤销 omni_wireless"的反方向。

## 工作项 (全部必做)

### W1 生成器侧 (起点补丁, 直接采纳)
Apply 包内归档补丁 (`git apply cc_context/review/algoaudit_preprocess_face_r1_20260612.patch`):
- `gen_protocol_storage_box()` → 3×3 无端口全 anchor 枚举 (68×68=4624, orientation=0, port_mode='omni');
- `is_edge_starved()` → 按 routing front (port + DIR_DELTA[dir]) 越界过滤 (整边全部 front 越界才剪);
- 自带 4 条几何契约回归 (`src/tests/test_preprocess_candidate_geometry_contract.py`)。
补丁后池闭式: m3x3 4·68·64 / m5x5 4·66·62 / m6x4 4·65·63 / protocol_core 2·58·58 / box 68·68 / pole 69·69 / boundary 2·67, 总 66403。

### W2 binding 无线消费语义 (本任务核心)
`src/models/binding_subproblem.py` `_build_generic_input_domains()` (~:510-550) 当前从 `pose["input_port_cells"]` 生成 wireless_sink 槽——新几何下箱子无端口 → 0 槽 → `_add_generic_input_requirements` 的 `sum([]) == required` 全局 INFEASIBLE。改为:
- 对 `operation_type == "wireless_sink"` 的实例, 槽位**虚拟化**: 每个被选实例固定生成 `preprocess_plan.json → utility_operations.wireless_sink.generic_input_slots` (=3) 个槽, **不挂任何 port cell / 坐标 / 方向**, 不经过 routing front 过滤 (`is_port_front_usable` 不适用);
- 槽仍参与 commodity 绑定数学: `AddExactlyOne(commodities + __unused__)`、`sum(commodity vars) == required` 不变;
- `extract_port_specs()` (~:763-819) **不得**为虚拟槽产出 port spec → routing/flow 自然收不到无线商品的 sink 需求 (这正是 routing-free 的实现);
- `extract_selection()["generic_inputs"]` 仍报告虚拟槽绑定 (slot_id 约定可保留 `{instance_id}:in:{k}`); 核对 `add_nogood_cut()` / conflict summary / 任何消费 selection 的下游对"无坐标槽"的兼容性;
- 实体模板 (boundary/protocol_core 的 generic output 槽) 语义**严格不动**。

### W3 routing/flow 一致性核对
- 确认 routing 模型对无线商品**不会**出现 sink front (port_specs 缺位即足够——逐路径核实, 包括 `run_exact_routing_precheck` 与 flow 诊断子问题);
- 回归: 选中 wireless box 的 tiny 实例, routing port_specs 无该商品 sink、routing FEASIBLE 不依赖任何通向箱子的皮带。

### W4 冻结工件 + lock/spec/docs 三件套 (PROJECT_LOCK 级, 必须同 commit)
- 重新生成 `data/preprocessed/candidate_placements.json` (新 hash 应 = `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes; 该文件本身不入交付包, 验收方本地再生成核对);
- 同步更新所有登记点: `PROJECT_LOCK.md` (旧 hash 行标 superseded + 新 hash), `specs/06_candidate_placement_enumeration.md` (hash + 池计数闭式 + §6.5.1 front 规则 + 协议箱 pose 空间), `specs/05` 如涉及 wireless_sink 语义陈述, `docs/exact_campaign_operations.md`, `docs/README.md` (expected size/sha/恢复说明), `FILE_STATUS.md`;
- 老 campaign state 因 artifact hash 变更自然失效 (campaign resume 有 hash 兼容性检查, 行为应是 fail-closed 拒绝 resume——加一条回归锁住这个行为而不是绕过它)。

### W5 hint 链残留 (做不了的明确文档化)
- `scripts/blueprint_to_master_hint.py` 把社区蓝图 rotation 映射到协议箱 port_mode pose——新几何下箱子只有 omni pose, 映射需改为"任意 rotation → 同 anchor 的 omni pose";
- `data/hints/blueprint_2026_05_13_master_hint.json` 内的 pose_idx 按旧池索引, 全体失效。蓝图源文件不在包内 → 你**无法**重新生成; 在 FIXES 文档里明确标注该 hint 文件 stale、需本地用源蓝图重跑转换脚本 (CP-SAT hint 是 advisory, stale hint 不伤 soundness 只伤搜索效率, 但必须留痕)。

### W6 自验 (全部跑并附日志)
- 新增/既有回归: 几何契约 4 条 + `test_p0_certified_soundness_fixes.py` 12 条全绿; binding 无线虚拟槽回归 (新增: 正向绑定成功 + port_specs 无虚拟槽 + required==0 时 `__unused__` 行为 + resume hash fail-closed);
- 全量 `python -m pytest -q -p no:randomly src/tests/` 回环境基线 (已知环境性失败: test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1——**注意**: 这些多半吃外置 candidate_placements, 你重新生成工件后其中一部分可能转绿, 如实报告增减并解释);
- `python scripts/check_p1_2_proof_obligations.py` pass; `python -m ruff check` 改动文件; `python scripts/gen_authoritative_numbers.py --check`;
- e2e probe: tiny 项目 (1 wireless box + 正 required_generic_inputs + 1 制造机 + boundary) **修复前** INFEASIBLE (或绑到伪端口) / **修复后** CERTIFIED 且无任何通向箱子的 route——前后对照日志。

## 红线 (PROJECT_LOCK)

- exact 与 exploratory 严格分离; 不引入 exploratory cap;
- 不碰 `src/cuts/lifecycle.py` `step_8_apply_to_master`; 不碰 campaign hash 计算逻辑本身 (只让它自然换值);
- 不加新 `EXACT_*` env (allowlist 封闭); fail-closed 行为不得放宽;
- `rules/canonical_rules.json` **一个字节都不改** (本任务是让代码服从它, 不是改它);
- 17-recipe canonical 投影不扩。

## 交付物

- unified diff (可 `git apply`) + `FIXES.md` (逐工作项: 改了什么/为什么 sound/probe 输出/W5 残留声明);
- 全部自验日志; 新增回归测试清单;
- **关键论证写在回复正文** (尤其 W2 虚拟槽不破坏 binding 数学、W3 routing 无线商品零需求的论证)。

包 sha256: `8fb4641df23249888e06dfa4ed5371ac4d1d9ecae0eb6af271ff63446bbea075`
