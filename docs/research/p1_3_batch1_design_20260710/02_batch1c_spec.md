# 批 1C 实现规格书：解级 power-pole dominance normalization（剪杆）

> 2026-07-10 主会话亲写定稿。上游：任务书 §三/§五/§六/§七.1C（`00_batch1_workplan.md`）。
> 基线 commit：`54b486a`（1B 已收口，慢 lane 30/30）。行号锚点均按此 HEAD 核实过。
> 实现范围：**只改 `src/search/benders_loop.py` + 新建一个测试文件**。义务条目正式 reseal 在 1E；benders_loop source pin 重钉由主会话终审时做，实现员不碰 scripts/data。

## §0 设计拍板（主会话核实源码后定案，实现员不得偏离）

1. **落点 = routing FEASIBLE 之后、`return RUN_STATUS_CERTIFIED, solution` 之前**（`_run_exact_binding_and_routing` 内，当前 `benders_loop.py:7000-7017`）。理由（核实过的硬约束）：
   - certified_exact 的 CERTIFIED solution **唯一生产点**就是这里（`:5382-5383` 只是转发它的返回值，不另产 solution）；
   - **不得在 extract（`:5180`）后立即剪**：binding/routing INFEASIBLE 时 whole-layout nogood 从 solution 反推 master literal（1B 第三轮刚修复 C1 杆 `pose_idx→p_k` 解析链）。剪后 solution 与 master 变量赋值失配 → nogood 覆盖不到 master 当前解 → 潜在死循环。剪杆必须只发生在**不再生成任何 cut** 的出口路径上。
   - 「先验证后剪」的正确性由复验义务保证：binding（端口）不涉及杆（power_pole 无端口责任）；routing（连通）删杆只释放格子、已验证路径仍有效；coverage 由剪后复验重新证明。
2. **exploratory 路径（`:4775`）不剪**：exploratory 永不产证据，其 CERTIFIED 在 `outer_search.py:2892-2909` 被静默降级为 UNPROVEN（铁律 §1），不进 proposal sink。
3. **无开关、无新 EXACT_\* env**：剪杆是 representation-independent 的通用封口（任务书 §六.1），C1 与旧 witness 编码统一经过。「默认路径生产零变化」纪律在此不适用的论证：M4 对抗审查阻断项就是「master 到 seal 之间没有剪杆步」，terminal verifier 的 `unforced_power_pole_instance` fail-closed 已在执法——剪杆把「seal 时 fail」变成「产出时正规化」，且复验 fail-closed 保证剪杆自身缺陷最坏产 UNKNOWN、绝不产坏 CERTIFIED（soundness 单向安全）。禁止为它新增任何 env 面（1D 的 canonical env 工作面不因 1C 扩大）。
4. **不碰 `outer_search.py`**：strong-status allowlist 对它有 30+ 条「文件 sha+绝对行号」锚（`data/proof_obligations/strong_status_write_allowlist.json`），改一行就要重钉几十条 entry。任务书 §七.1C 的「防御性验证/telemetry（如需要）」裁量为**不需要**——sink 不可绕过由「唯一生产点已剪 + 端到端测试锚定」保证。
5. **不碰 `exact_campaign.py`**：terminal verifier 语义只对照、不抽 helper（benders_loop → exact_campaign 会反向 import 成环；exact_campaign 侧 `_pose_power_coverage_cells` 是模块私有）。剪杆在 benders_loop 侧自带同语义严格解析，语义一致性由测试钉住（见 T12）。
6. **required>0 时整批不剪、只复验**：1B 已把 required 语义原生化为「恰好 N 杆」（`master._exact_required_pose_optional_counts["power_pole"]` 为权威源，C1 发 `Σp_k == N`；旧编码 required 槽同义）。杆数是实例义务不是冗余，删一根即破 terminal 的 `missing_required_optional_instance` 下界检查。若 required 布局本身过不了 unforced 复验 → fail-closed（这是实例数据语义矛盾，不由剪杆掩盖）。
7. **mandatory 杆（`is_mandatory=True` / `bound_type=="exact"`）绝不剪**，但参与 coverage/unforced 计算（terminal verifier `:1192-1205` 收集所有 power_pole 不分 mandatory/optional——语义必须对齐）。存在 unforced mandatory 杆时复验失败 → fail-closed None。

## §1 手术点清单

### S1 模块级纯函数（新增，benders_loop.py）

```python
def normalize_certified_power_pole_dominance(
    solution: Mapping[str, Mapping[str, Any]],
    *,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    templates: Mapping[str, Mapping[str, Any]],
    grid_w: int,
    grid_h: int,
    required_power_pole_count: int,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
```

返回 `(normalized_solution, summary)`；任何 fail-closed 情形返回 `(None, summary)`（summary 里带 `verdict` 与失败原因码）。**不 mutate 输入**（返回新 dict；entry 浅拷贝即可，剪杆只删 entry 不改 entry）。

语义（与 terminal verifier `exact_campaign.py:1192-1253` 逐条对齐）：

1. **收集**：遍历 solution，`facility_type=="power_pole"` 的 entry 进杆集；其余 entry 若 `templates[facility_type].get("needs_power", False)` 为真进 powered 集（注意 terminal 是 `elif`——杆自身即使模板标 needs_power 也不进 powered 集）。
2. **严格解析（fail-closed）**：每个杆/powered entry 取 `pose_idx`，必须是非负 int 且在 `facility_pools[facility_type]` 界内；`entry["pose_id"]` 必须与 `pool[pose_idx]["pose_id"]` 一致（防 pool/solution 漂移）；杆的 coverage = `pool[pose_idx]["power_coverage_cells"]`（裁剪到网格内，与 terminal `:1200-1204` 同义），powered 的 occupied = `pool[pose_idx]["occupied_cells"]`；cells 必须是 `[x,y]` 数对列表、int、非 bool——任何 malformed → `(None, summary)`。杆 coverage 网格内裁剪后为空不是错误（可为空集，照参与）；powered 的 occupied 为空 → fail-closed（几何异常）。
3. **required 分支**：`required_power_pole_count > 0` → 跳过删除（`pruned_pole_count=0`），直接进第 5 步复验。
4. **迭代删除（确定性）**：候选 = optional 杆（`is_mandatory` 不为真且 `bound_type=="exact_pose_optional"`）。循环：按 `sorted(instance_id)` 扫描，找到第一根「不是任何 powered instance 的唯一 coverer」的候选杆（即不存在 powered p 使 coverers(p)=={该杆}），删除之并重算 coverer 映射；无可删杆时终止。powered 集为空时所有 optional 杆都可删（全删）。26 杆规模 O(P²·C) 毫秒级，无需优化。
5. **复验（三条 terminal 同义 + 两条保持性，任一失败 → None）**：
   - R1 coverage 保持：每个 powered instance 至少有一个 coverer（terminal `:1239-1240` 同义）；
   - R2 杆数上界：剩余杆数（含 mandatory）≤ powered instance 数（terminal `:1245`）；
   - R3 unforced：每根剩余杆覆盖至少一个 powered，且是至少一个 powered 的唯一 coverer（terminal `:1246-1253`）；
   - R4 required 保持：`facility_type=="power_pole"` 的剩余 entry 数 ≥ `required_power_pole_count`；
   - R5 非杆 entry 保持：输出 solution 的非 power_pole entry 与输入逐 key 相同（函数内部自证，防实现错误删错类型）。
6. **summary**（strict-JSON 友好，全 int/str/bool）：`{"verdict": "normalized"|"noop"|<失败原因码>, "pole_count_before": int, "pole_count_after": int, "pruned_pole_count": int, "prune_iterations": int, "powered_instance_count": int, "required_power_pole_count": int, "mandatory_pole_count": int}`。失败原因码风格与仓库一致（如 `"power_pole_pose_invalid"`、`"power_pole_dominance_reverify_failed"`、`"required_power_pole_reverify_failed"`）。

### S2 controller 薄 wrapper（新增 LBBDController method）

`_normalize_certified_solution_power_poles(self, *, solution, iteration)`：从 `self.master` 取数据源（`facility_pools`、`templates`、`grid_w`、`grid_h`、required 用 `getattr(self.master, "_exact_required_pose_optional_counts", {})` 后 `.get("power_pole", 0)`——属性缺失按 0 处理但要在 summary 记 `required_source_missing: True` 便于审计），调 S1，前后各发一次 `_emit_heartbeat(stage="power_pole_dominance_normalization", event="start"/"complete", iteration=iteration, extra=<summary 摘要>)`（heartbeat 先例 `:5181-5189`）。返回 `(normalized_solution_or_None, summary)`。

### S3 生产点接线（`_run_exact_binding_and_routing` routing FEASIBLE 分支，当前 `:7000-7017`）

```
if routing_status == "FEASIBLE":
    normalized, prune_summary = self._normalize_certified_solution_power_poles(...)
    if normalized is None:
        self.last_proof_summary = {  # 结构仿既有 fail-closed 分支（如 :5216-5233 power_placement）
            "mode": "certified_exact", ..., "stage": "power_pole_dominance_normalization",
            "power_pole_dominance": prune_summary, "master_follow_up": "fail_closed_unknown", ...
        }
        return RUN_STATUS_UNKNOWN, None
    self.last_proof_summary = { ...既有全部字段..., "power_pole_dominance": prune_summary }
    return RUN_STATUS_CERTIFIED, normalized
```

既有 last_proof_summary 的全部字段一个不动，只**新增** `power_pole_dominance` key（下游 `outer_search.py:1007-1020` 对 proof_summary 是 dict 展开、无 schema 拒绝，已核实安全）。exploratory `:4775` 与其余任何 return 点不动。

### S4 禁碰面（红线，违者打回）

- 不改 `src/search/outer_search.py`、`src/search/exact_campaign.py`、`src/models/*`、`scripts/*`、`data/*`、`src/cuts/*`。
- 不动 benders_loop 里 checker 的字面 needle：`_CERTIFIED_KNOWN_ENV_NAMES`、`_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`、env blocker 代码串、`partial_due_to_time_budget` 谓词（不得删改也不得在新代码里复制这些字面量）。
- 不新增/改动任何 `EXACT_*` env 读取；不动 canonical env 结构（`:985-1021`）、env guard（`:1328-1420`）、attach gate（`:7734-7914`）、`_framework_target_poses`。
- 不动既有三个 CERTIFIED return 之外的控制流；INFEASIBLE/UNKNOWN/cut-added 路径的 solution 保持未剪。
- 不做 git 操作；测试一律 `.venv/bin/python`。

## §2 测试计划（新文件 `src/tests/test_power_pole_dominance_normalization.py`）

纯函数直调为主（构造小 facility_pools/templates/solution 字典，不跑 CP-SAT），端到端两个。fixture 风格参照 `test_c1_power_coverage.py`。

- T1 冗余杆剪除：2 杆覆盖同一 powered 机器 → 剪到 1 杆，R1-R5 全过，非杆 entry 逐字节不变。
- T2 极简集 no-op：每杆已是唯一 coverer → `verdict="noop"`、`pruned_pole_count=0`、输出内容等于输入。
- T3 不动点迭代：构造删 A 后 B 才变唯一的 3 杆链 → `prune_iterations >= 2`、终态过 R3。
- T4 无 powered 设施：optional 杆全删（0 杆 ≤ 0 powered，R2 边界），summary 记全剪。
- T5 mandatory 杆不剪：mandatory 冗余杆场景 → 复验 R3 失败 → `(None, ...)`；mandatory 杆 + optional 冗余杆 → 只删 optional。
- T6 required>0 no-prune：required=2 + 2 杆（其一冗余）→ 不删、复验跑；若复验过则原样返回。
- T7 required 复验矛盾：required=2 但布局 unforced 不可救 → `(None, "required_power_pole_reverify_failed"…)`。
- T8 malformed fail-closed（参数化）：pose_idx 越界 / pose_id 失配 / coverage cells 非数对 / powered occupied 为空 → 全部 `(None, ...)`，绝不抛异常出函数边界。
- T9 确定性：同输入调两次，输出 solution 与 summary 逐字节（json.dumps sort_keys）一致。
- T10 端到端 CERTIFIED 已剪（C1 路径）：小实例（参照 test_c1_power_coverage 的 ghost+lex fixture）跑 `run_benders_for_ghost_rect` 到 CERTIFIED → 返回 solution 逐杆满足 R3（unforced 复验器在测试里按 terminal 语义独立实现一份作对照），且 `last_proof_summary["power_pole_dominance"]["verdict"]` ∈ {normalized, noop}。
- T11 端到端旧编码同过：同 T10 但 `c1_power_pole_representation=False`——剪杆对两种编码统一生效。
- T12 语义平价锚：构造同一 solution 的 terminal-verifier 形态输入，断言剪杆复验的 R1-R3 判定与 `exact_campaign.py` terminal 段（`:1227-1253`）对同场景的接受/拒绝一致（至少覆盖：接受极简集、拒绝 unforced 杆、拒绝 coverage 缺失三例；可通过构造 final_result 调 campaign 侧现有校验入口，或按其语义在测试内复刻断言——取实现成本低者，但必须在注释里注明对齐的 terminal 行号段）。
- T13 fail-closed 出口：monkeypatch S1 强制返回 None → `_run_exact_binding_and_routing` 出 `RUN_STATUS_UNKNOWN`、`last_proof_summary["stage"]=="power_pole_dominance_normalization"`、无 CERTIFIED。

## §3 验收命令（实现员必跑全绿后交付）

```bash
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/b1c \
  src/tests/test_power_pole_dominance_normalization.py \
  src/tests/test_c1_power_coverage.py \
  src/tests/test_c1_pole_representation_scaffold.py \
  src/tests/test_master.py \
  src/tests/test_exact_contract.py \
  src/tests/test_binding.py src/tests/test_routing.py -q
.venv/bin/python -m ruff check src/search/benders_loop.py src/tests/test_power_pole_dominance_normalization.py
```

（`test_binding.py`/`test_routing.py` 需要 candidate_placements.json 在位——本机在位。）交付报告附 pytest/ruff 尾部原文 + 每个手术点的落位行号。

## §4 主会话终审 + reseal 清单（实现员不做）

1. 终审抽查：S3 落点正确性（FEASIBLE 分支唯一、cut 路径未剪）、S1 与 terminal 语义逐条对照、T10/T11 真实性。
2. reseal：benders_loop source pin 三处（checker `:12971` floor、manifest JSON pin、strong-status allowlist **不动**——benders_loop 不在其模块列表，已核实）→ semantic digest 不动点收敛 → checker 自钉最后。
3. preflight staged + `--full`；慢 lane（1C 必跑批，动了认证核心）。
4. 义务条目 `PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION` 与 REQUIRED_OBLIGATION_IDS 更新**留 1E**（任务书 §七.5）；本批测试命名要稳定（1E 的 required_tests 将按名引用）。
