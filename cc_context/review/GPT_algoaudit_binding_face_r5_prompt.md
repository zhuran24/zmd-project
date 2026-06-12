# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 5 (F-BIND-R4 修复确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_fbind_r5_snapshot_54ffa047.zip`, sha256 `54ffa047d9c9fe0e350a8d920d4db1189db0403e8956bca0482e66ff85fbfb01`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面收敛轨迹: r1(2 HIGH)→r2(2)→r3(5)→r4(1), 本轮 r5 = 确认轮

前四轮报告在包内 `cc_context/review/archive/algoaudit_binding_face_r{1,2,3,4}_REVIEW_20260612.md`。主线收敛: 哨兵/loader (r1) → 解析分叉/strict JSON (r2) → 单解析单快照五缝 (r3) → wireless 槽数快照漏注入 = 单快照族第五消费点 (r4)。

本包已落地 r4 修复 (`6628a9d`):
- `PortBindingModel.__init__` 新增 `wireless_sink_generic_input_slots` 显式快照参数 (传入用快照, 未传保留 loader fallback 供非 certified/fixture 路径), 与 loader 共用同一 strict 非负 int 规范化 (`_normalize_wireless_sink_generic_input_slots`)。
- `benders_loop._binding_generic_requirements_kwargs()`: certified + required_generic_inputs 非空时从 `master.wireless_sink_generic_input_slots` 注入 strict 快照, 缺失/bool/非 int/负数 fail-closed RuntimeError; 主 binding 与 overload retry 共用。
- PROJECT_LOCK/specs05 单快照条款扩为 F-BIND-R3/R4 (含「绝不取 import-time 默认 profile, 也不在 binding 时二次重读磁盘」)。
- 回归 4 条: 注入快照覆写磁盘 plan / 主路径 kwargs 带槽数 / retry 同快照 / certified 有 generic inputs 缺快照 fail-closed。

你的任务: 对抗式审查 r4 修复——确认正确且没引入新缝。**若审完无残留, 明确报零** (本面饱和判据 = 连续 2-3 轮独立零 finding; r1-r4 连续出货, 本轮是首个潜在干净轮)。

## 审查重点 (按优先级)

### Q1 r4 修复本身
- 快照注入条件是 `required_generic_inputs 非空`: required_generic_inputs **为空**但 placement 含 wireless_sink 实例 (pose-optional 物化) 的形态存在吗? 那时 binding 不注入快照 → fallback 读磁盘 → 双时间点缝在"空需求但有箱"的形态下复活吗 (先验证这种形态在 certified 路径是否可达)?
- `_normalize_wireless_sink_generic_input_slots` 与 loader 的规范化在所有边界值 (0/大整数) 上行为一致吗? 0 槽快照的下游行为 (`_wireless_sink_input_slot_count` 返回 0 → 虚拟槽 0 个 → 有需求必 INFEASIBLE) 是正确语义还是新缝?
- 非 certified 路径 (legacy fixture/heuristic finder) 走 fallback 读磁盘 — heuristic_feasible_finder 是非 proof 链, 确认它的 fallback 不会间接影响 certified 决策 (其结果有没有被 certified 路径当证据消费)?

### Q2 单快照族终验
r4 后单快照族五个消费点 (master lower bound / outer safe-area / campaign helpers / coordinate stats / binding capacity) 全部注入。请独立重扫 `wireless_sink|generic_input_slots|get_operation_port_profile` 的全部非测试引用, 确认没有第六个 hard consumer; 并验证五个消费点收到的值在同一 session 内**可证明同源** (全部链回 `ExactSearchSession.create` 的同一次 plan 读取)。

### Q3 r1-r4 全弧线交互终验
四批修复全部落在 binding_subproblem/master_model/benders_loop/exact_campaign: 任选 2-3 个修复对组合推演交互 (如哨兵×槽数快照: 槽数 0 时 generic input 槽全空, 哨兵逻辑还成立吗? 如 strict loader×kwargs 注入: 注入路径完全绕过 loader, loader 的 BOM/strict JSON 防御在注入路径上是否不再需要 [快照源头已 strict]?)。

### Q4 薄点抽查
前四轮判干净的结论里抽 1-2 个最薄的独立验证或推翻 (建议: r4 的"AST mutation scan 无生产 mutation"——扫的全面吗, `setattr`/`__dict__` 类间接 mutation 漏了吗? 或 r2 的"`_ordered_generic_slot_commodities` 仅 hint")。

## 明确不要报的

- r1-r4 已修 finding 本体; 三套 strict helper 未统一 (风格); 双 coordinator lockfile (运维挂账); utility roster 扩展 guard (挂账); master_model import-time profile fallback 在 caller 不传时使用 (r4 已判非 proof 路径)。
- 设计决策 (canonical/266/52-Port/omni_wireless); C-1 已 refuted; preprocess/campaign/scheduler/master 几何/routing/cuts 各面。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2944 passed, 0 failed)**; 跑不完就跑专项 (test_binding / test_exact_contract / test_master) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 重扫引用清单与 Q3 交互推演组合。

## 范围边界

- 重点 = R4 修复面 + 单快照族终验 + 全弧线交互; 其余面不审。
