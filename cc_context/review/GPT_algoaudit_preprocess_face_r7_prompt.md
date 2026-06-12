# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 7 (R6-F-01 修复确认轮 + hash 闭包泛化审查)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_v80_impl_full_20260612_single.zip`, sha256 `ca38fe30dfa01708cb95db0e2d699d52f2ee2d3aa4d59ca312f55ce56561f213`。**开工前先校验 sha256, 对不上停下来报告** (文件区可能残留老包, 以本 sha 为准)。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 背景: r6 出了 R6-F-01, 本包刚落地其修复

preprocess 面修复链 (归档在包内 `cc_context/review/algoaudit_preprocess_face_r{1..6}_REVIEW_20260612.md`): r1-r5 = wireless 弧线已收口 (r5 零 finding); **r6 (非 wireless 角度) 抓到 R6-F-01 HIGH**: `preprocess_plan.json` 经 `_merge_overlay` 可静默同名覆盖 canonical 的 recipes/production_targets/commodity_roles (probe: packaging_battery 输入 15→5 让 input_slots 3→1 静默接受 = 欠约束/false-CERTIFIED 方向), 且 plan 不在 exact campaign hash 闭包 (`EXACT_HASH_FILES`) 也不在 preflight 冻结登记——同一 campaign hash 可对应两种运行时端口语义 (operation_profiles 在 import 时从 plan 派生 + binding 直读 plan utility slots)。

本包已落地修复 (commit 链尾):
- `src/interchange/preprocess_context.py`: plan 携带 `recipes`/`production_targets`/`commodity_roles` 任一键 → ValueError fail-closed (additive-only; 三类事实只从 canonical 派生, metadata source 标记改 `canonical_rules`);
- `rules/preprocess_plan.schema.json`: 删除三个 override 节;
- `src/search/exact_campaign.py`: 新增 `OPTIONAL_EXACT_HASH_FILES` 把 `rules/preprocess_plan.json` 纳入 `compute_exact_artifact_hashes()` (文件缺失记 sentinel `__MISSING_OPTIONAL_EXACT_ARTIFACT__` 保 synthetic 测试工程);
- `scripts/preflight_gate.py::FROZEN_ARTIFACTS`: 登记 plan hash `1BCF0D13…`;
- PROJECT_LOCK §2A 条款重写 + specs/04/18/19/20 同步 (含纠正 specs18 旧「PreprocessContext 仅管再生」论断);
- 新增回归: `test_preprocess_context.py` 三键拒绝参数化 + `test_preprocess_plan_exact_hash.py`。

你的任务: 对抗式审查 r6 修复——确认正确且没引入新缝, **并把同类问题泛化穷举**。**若审完无残留, 明确报零** (面饱和计数因 r6 非零已清零, 本轮零 finding 重新计第 1 轮)。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 R6-F-01 修复本身
- 拒键检查的位置 (`build_preprocess_context_from_rules_and_plan`) 是否覆盖**所有** plan 装载路径 (load_default / from_paths / 任何直接调 builder 的入口)? 有没有路径在拒键检查**之前**就消费了 plan 的三键内容?
- `OPTIONAL_EXACT_HASH_FILES` + missing sentinel 语义: sentinel 字符串会不会与真实 sha256 撞 (不可能, 但确认格式); 文件存在但是 symlink/不可读时的行为是否 fail-closed; resume 比较是 dict 全等吗——旧 state 无 plan key 必须 mismatch (不能被 dict 子集比较放过)?
- schema 收紧与 builder 拒键是否一致 (schema 校验在哪一步跑? 有没有不经 schema 校验直接 json.load 的装载点导致两层防线只剩一层)?
- 回归测试判别力: unpatched 下这些测试会红吗 (口头判断即可, 不必真退补丁)?

### Q2 泛化: 还有哪些影响 certified runtime 语义的输入不在 hash 闭包? (最重要)
R6-F-01 的本质 = 「影响 runtime 证明语义的文件逃逸在 stale 检查之外」。请全仓穷举**所有**在 certified exact 运行时被读取、且其内容变化会改变求解/绑定/路由/证明行为的文件或配置源, 对每一个判定: 它在 `EXACT_HASH_FILES`/`OPTIONAL_EXACT_HASH_FILES`/`FROZEN_ARTIFACTS` 闭包内吗? 不在的话是否构成同类缝? 候选方向 (不限于):
- `rules/*.json` 其它文件 (schema 文件本身? viewer/export 相关 rules?)
- `data/preprocessed/` 之外被运行时读的 data 文件 (hints? telemetry 配置?)
- env 变量已有 deny-unknown allowlist 兜底 (V80), 但 allowlist 自身的语义对吗 (有没有 operational 名实际影响证明)?
- python 模块级常量/表 (代码本身在 git 内, 不算; 但若有从非 hash 文件加载的表要算)
- `preprocess_plan.schema.json` 改了会怎样 (schema 不在 hash 闭包——它影响校验行为吗)?

### Q3 r6 其余复核结论抽查
r6 报告 Q1-Q5 零 finding (demand 数学 266=219+46+1 / 池 66403 / 52 槽平衡 / 确定性 / 三件一致)。抽查其中 1-2 个你认为论证最薄的, 独立验证或推翻。

### Q4 文档一致性
PROJECT_LOCK §2A 新条款 / specs/04/18/19/20 措辞与代码行为一致 (列多/列少都报)。

## 明确不要报的

- wireless 链主体 (r1-r5 已收口); 设计决策 (canonical 17-recipe / 266 口径 / omni_wireless, owner 已定)。
- 旧 campaign state resume 因新 hash key 而 mismatch——这是预期 fail-closed 行为, 不是 bug。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); 根目录裸 pytest 误收集 `补丁包/` 归档 (已知); 已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2912 passed, 0 failed)**; 跑不完就跑专项 + 如实声明。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件 (canonical_rules / preprocess_plan / preprocessed 三件), 交付必须含再生步骤 + 期望 sha256/字节数 + 要同批推进的登记位置清单 (`FROZEN_ARTIFACTS` / `EXACT_HASH_FILES` 族 / PROJECT_LOCK / specs)。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 实际穷举过的 runtime 输入面清单。

## 范围边界

- 重点 = r6 修复面 + Q2 hash 闭包泛化; P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; postprocess/adapter 不审。
