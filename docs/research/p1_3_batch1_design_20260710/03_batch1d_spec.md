# 批 1D 实现规格书：C1 默认化 + canonical env 收缩 + attach 回归 + F5 adapter TCB

> 2026-07-10 主会话亲写。上游：任务书 §七.4/§六.1（owner 拍板旧 witness 不留）。
> 基线 commit：`24372cf`（1C 已收口）。行号按此 HEAD 核实。
> 改动面：`src/models/master_model.py`、`src/models/exact_coordinate_master.py`、`src/search/benders_loop.py`、既有测试文件的默认翻转适配 + 新增回归测试。checker 的 F5 classification 与全部 reseal 由主会话终审做，实现员不碰 scripts/data。

## §0 设计拍板

1. **翻默认（本批核心）**：`c1_power_pole_representation` 默认 False→True，共四处同步：
   - `src/models/master_model.py:2298`（dataclass 字段默认）、`:2315`（__init__ 参数默认）、`:2630`（build 入口参数默认）；
   - `src/models/exact_coordinate_master.py:764` 的 `getattr(owner, ..., False)` fallback → True；
   - `src/models/master_model.py:2813` 的 `getattr(core, ..., False)`（checkpoint/core 恢复路径）→ True。**恢复路径必须与构造路径同默认**，否则 resume 的 campaign 掉回旧编码 = 同一 campaign 两种语义（fail-closed 原则：宁可全 True）。
   - 向后兼容注意：恢复**旧 checkpoint**（core 无该属性，1A 前生成）时 getattr fallback=True 会用 C1 重建 master——这是正确语义（master 是重建的、不是反序列化的，编码跟当前代码走；1C 的剪杆同理 representation-independent）。
2. **旧 witness 保留形态**：函数本体留在 master（等价性测试直调），certified 生产不可达。显式 `c1_power_pole_representation=False` 传参仍合法（测试用）——**但 certified 入口加防御断言**（见 S4）。
3. **witness-only canonical env 锁移除（7 个全撤）**：`_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS` 的 7 个 env（family lookup / shell distance / witness encoding / block geometry / block size / block templates / selected interval）全部只被旧 witness 路径消费（C1 下不可达）。处置 = **从 canonical defaults 与 `_CERTIFIED_KNOWN_ENV_NAMES` 两处同步移除**：certified 下这些名字从此按 unknown EXACT_* fail-closed（比原 canonical 锁更严，符合 deny-unknown 铁律）；exploratory 功能不受影响（守卫是 certified 专用，`_collect_forbidden_certified_master_domain_env_overrides` 只在 certified 入口跑）。env 名常量与消费点代码保留（exploratory/测试仍用）。**警告：绝不允许「从 canonical defaults 移除但 known names 保留」的中间态**——那会让这些 env 在 certified 下变成无校验放行（比现状更松），实现时必须两处原子同改。
4. **不为 C1 建任何新 EXACT_* env**（owner 拍板延伸）：C1 无 runtime 开关面，翻默认后它就是 certified 唯一编码。
5. **attach gate 本批不改代码**：验收「F1/F5/F6/F7 经 validated gate」由回归测试在 C1 默认下重验（attach 链与杆编码的交互面 = `_framework_target_poses` 从 solution 解析 target poses，C1 的 pose_optional 杆 entry 形态与旧编码一致，1C 双审已确认该面）。
6. **F5 adapter TCB classification（主会话终审做）**：checker `:12815` 一带 `'src/search/f5_binding_empty_domain_adapter.py': 'out_of_scope_future_phase3b'` → 正式登记（外审要求）；随本批 reseal 一起落。实现员不碰。

## §1 手术点

### S1 翻默认（五处，见 §0.1）
全部 False→True，无其他逻辑改动。

### S2 canonical env 收缩（benders_loop.py）
- `_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS` 收缩为空 dict——**保留常量本身与消费它的守卫代码结构**（checker needle 锚着 env guard 的字面结构；空 dict 让 1406 的 canonical 校验循环自然变 no-op），并在常量处留注释记录 7 个锁的移除依据（owner 2026-07-10 拍板 + C1 默认化后 witness 路径 certified 不可达）。
- `_CERTIFIED_KNOWN_ENV_NAMES` 同步移除同 7 个名字。
- 若 7 个 env 名常量在 benders_loop 侧因此失去全部引用，用 `del` 还是保留？——保留常量定义（master 侧消费点仍 import 或复制了这些名字；且删名会碰 checker needle 风险面）。ruff 报 unused 就加显式 `# noqa` 或在收缩注释里引用。
- **禁碰**：checker needle 字面量（`_CERTIFIED_KNOWN_ENV_NAMES`、`_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`、两个 blocker code、`EXACT_COMMUNITY_BLUEPRINT_HINT_PATH`、`GATE_WORKER_PEAK_RSS_GIB`、`partial_due_to_time_budget` 谓词）必须原样存活。

### S3 skip_power_coverage×C1 交互确认
`exact_coordinate_master.py:2299` 的 `if self.owner.skip_power_coverage and not self.c1_power_pole_representation: return`——翻默认后 skip_power_coverage 场景走 C1 分支的行为要有明确回归测试（skip 语义在 C1 下应同样跳过 coverage 约束发射；若实测语义不对，修复方案报回主会话裁决，不得自行扩大改动面）。

### S4 certified 防御断言（benders_loop.py）
certified_exact 路径 master build 完成后断言 delegate 的 `c1_power_pole_representation` 为 True（旧 witness 意外进 certified → fail-closed UNKNOWN，原因码 `power_witness_representation_not_certified` 风格）。落点：master build 后、进 benders 迭代前的既有校验区。exploratory 不查。

### S5 测试默认翻转适配
原则：**显式传 `c1_power_pole_representation=False/True` 的测试语义不变；吃默认值的测试预期按 C1 翻转**。已知面（实现时全量排查）：
- `test_c1_pole_representation_scaffold.py` / `test_c1_power_coverage.py`：大多显式传参，不动；有「默认=旧编码」锚定的（如 build_stats 默认无 c1 key 的断言）翻转为「默认=C1、build_stats 含 c1 审计」。
- `test_master.py` / `test_exact_contract.py` / `test_coordinate_no_overlap_dedup.py` 等吃默认构造的：预期按 C1 行为更新（杆槽不再出生、residual slot 结构变化、build_stats 新 key）。
- 1C 的 T10/T11：T10（C1 端到端）不动；T11（旧编码端到端到 CERTIFIED）会撞 S4 防御断言——**T11 改为显式断言「certified 下旧编码被 fail-closed 拒绝」**（防御断言的回归钉），旧编码的剪杆纯函数覆盖已由单元级测试保住。
- 新增：默认构造的 master 其 `c1_power_pole_representation` 为 True 的直接断言（防未来默认被无声翻回）。

## §2 验收命令

```bash
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/b1d \
  src/tests/test_c1_power_coverage.py src/tests/test_c1_pole_representation_scaffold.py \
  src/tests/test_power_pole_dominance_normalization.py \
  src/tests/test_master.py src/tests/test_exact_contract.py \
  src/tests/test_coordinate_no_overlap_dedup.py src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_binding.py src/tests/test_routing.py \
  src/tests/cuts/test_step_8_apply_to_master.py src/tests/cuts/test_f7_helper_vs_master_power_equivalence.py -q
.venv/bin/python -m ruff check src/models/master_model.py src/models/exact_coordinate_master.py src/search/benders_loop.py <新/改测试文件>
```

全绿后交付；报告附每个手术点落位行号 + 测试翻转清单（哪些测试改了预期、为什么）+ pytest/ruff 尾部原文。禁碰面同 1C（不动 outer_search/exact_campaign/scripts/data/src/cuts 代码，不做 git 操作）。

## §3 主会话终审 + reseal 清单（实现员不做）

1. 终审：翻默认五处核对、canonical 收缩两处原子性、S4 防御反向复现（certified+旧编码 → UNKNOWN）、测试翻转清单逐条裁决。
2. F5 adapter classification 更新（checker V99 floor `:12815` 一带）+ 义务锚定文字。
3. reseal：master_model.py / exact_coordinate_master.py / benders_loop.py 三文件 pin（checker floor + manifest JSON）→ checker 自钉；**golden digest 预期再漂**（玩具链默认编码翻成 C1，candidate records/witness projection 必变）——重钉前照例玩具链 dump 验明差异恰好是编码翻转、无杂质。
4. preflight（base 解释器！）+ 慢 lane（1D 必跑批）。
5. 义务层正式条目仍留 1E。
