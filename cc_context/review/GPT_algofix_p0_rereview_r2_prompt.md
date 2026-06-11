# 终末地 IndustrialPlanner 精确求解器 — P0 修复面第二轮再审（零 finding 确认轮）

## 任务性质（新会话零历史，独立对抗审查）

附件是完整项目快照 zip（zip 内 `project/` 为仓库根；ZIP_LZMA，用 `python -m zipfile -e <附件>.zip .` 解包）。依赖 wheels 在本 Project 文件区，沙盒 Python 3.13，离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

这是 P0 修复面的**第二轮**独立审查。第一轮再审验真了修复主体并挖出 2 个新问题，**两者都已修复并落地在本包里**。owner 要求按"安全修复完整性"原则再来一轮：**整个 P0 修复面（原 3 修复 + 第一轮再审的 2 个修复）**的对抗式确认。如果你审完确认无残留 soundness 缺陷，明确报零——这轮的零 finding 声明是 owner 判定修复批次"完成"的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`，266 强制设施，OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。宪法 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 默认姿态。

## 修复面全景（审查对象，说明文档在包内）

- 修复批次说明：`cc_context/review/algofix_p0_FIXES_20260611.md`（原 3 个 P0）
- 第一轮验收：`cc_context/review/algoaudit_verification_results_20260611.md`

**原 3 个 P0 修复**：
1. **P0-1**：`src/models/routing_subproblem.py` — solve() 接受 incumbent 前按 commodity 重建选中 route-state 有向图、检查 source→sink 可达；不可达加 selected-positive nogood 重解；预算耗尽 TIMEOUT。
2. **P0-2**：`src/models/exact_coordinate_master.py` — footprint token + 包围盒 channel（`mode → dx_min/dy_min/w/h` 走 AddAllowedAssignments），no-overlap 用 variable-size interval，power witness 用 footprint span；缺 footprint 证据构建期 raise。
3. **P0-3**：`src/search/benders_loop.py` — `binding_selection_safe_reject=True` 且有 binding 替代时先 binding-level nogood 枚举，穷尽后才落 whole-layout 路径；重解超时 UNKNOWN。

**第一轮再审追加的 2 个修复（本轮重点新鲜面）**：
4. **非矩形 power witness 回退**：`_supports_rectangular_power_coverage()` 现在额外要求**所有 powered template 候选 footprint 都是满矩形**才走几何 witness，否则 fail-closed 回退到精确 `(pole_pose, powered_pose)` coverer 表。（第一轮发现：bbox 复用到 power coverage 存在性见证时安全方向反了——L 形 footprint 的 bbox 洞被 pole 覆盖也算供电。）
5. **guard 验收标志**：`_connectivity_guard_accepted` —— solve() 开始置 False，只有 guard 验收 connected 后置 True；`extract_routes()` 要求该标志，guard-TIMEOUT 后返回 []。

**配套已验真**：`_all_powered_slots` 过滤 empty-domain slot（第一轮穷举验证安全）；footprint channel 无 off-by-one；P0-1 guard 图语义与模型同构；P0-3 ladder 无 over-cut 复活。

## 本轮重点（按优先级）

### R1 第一轮追加修复本身的对抗审查（最新的代码 = 最少被审过）
- **矩形性检查的完备性**：`_supports_rectangular_power_coverage()` 的 powered footprint 矩形性检查是否覆盖**全部** powered template 的**全部**候选 pose？有没有 pose 缺 `occupied_cells`、空池、缓存/记忆化导致检查被绕过的路径?检查发生在 footprint domain 构建之前还是之后,顺序有没有缝?回退到 table witness 后,table 路径自身对非矩形 footprint 的覆盖语义是否精确(逐 pose coverer 表 vs 真实占格)?
- **guard 验收标志的状态机**:`_connectivity_guard_accepted` 有没有任何路径被错误置 True(重解循环、异常、INFEASIBLE 分支、多次 solve() 复用同一对象)?除 `extract_routes()` 外还有没有别的消费点读取 stale `_solver`/`_status`(如 build_stats、诊断导出、conflict 提取)?
- 两个新修复对 env-off / 既有行为的影响是否真为零?

### R2 修复面整体的残留缝扫描
把 5 个修复当成一个整体攻击面,找第一轮没攻过的角度:多次 solve() 调用复用、异常路径中途退出、build/solve 顺序假设、与 exploratory 路径共享代码的串扰、修复之间的交互(如 footprint raise 与 binding ladder 的 UNKNOWN 路径叠加时状态是否一致)。

### R3 回归测试的盲区补强(可选)
第一轮指出现有测试不覆盖:guard-timeout 双层语义、multi-commodity guard、binding 重解 TIMEOUT、枚举耗尽落 whole-layout、singleton fixed binding。若你能写出有判别力的补充回归(修复正确则过、能抓未来回归),附上;不强求。

## 明确不要报的（已知/已裁决,报了不算 finding）

- proof-carrying certificate(候选自带可独立重验证明)是已知 future work。
- P0-1 guard 的完整性代价(可行布局可能 UNKNOWN)是已知裁决:最终修复(lazy max-flow cut → 全量 flow 编码两步走)已排期,不在本轮范围。
- P0-1 nogood 是 selected-positive subset nogood(禁超集)——措辞已修正,第一轮已论证无误删实证;除非你有**新的实证反例**(构造出被它误删的合法 connected incumbent),否则不要重报。
- 上轮已 refuted 的三个误判:binding output 满占(52-port 不变量)/routing port 单次偏移/pose-bool 被 guard 拦截。
- 已修复的第一轮 Finding 1/2 本身(但它们的**修复**是 R1 重点)。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `python -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py` 应 **5 passed**。
- `data/preprocessed/candidate_placements.json`(53.6MB)外置不在包内,**不准伪造**。已知环境性失败(非 finding):test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1;其余约 2838 应过。
- finding 必须带可复现 probe 或严谨数学论证(具体到 file:line);实证推翻了你的怀疑就不要报。

## 交付物

- `REVIEW.md`:逐条 finding——严重度(**algorithmic/soundness** vs 工程 vs 文档)、`file:line`、probe/论证、建议修法;有把握的附 unified diff + regression。
- **所有关键论证写在回复正文**(不要只塞附件)。
- **若审完整个修复面无残留 soundness 缺陷,明确写"本轮零 soundness finding"** + 列出实际审过的面、构造过的攻击输入、论证依据。这句话是 owner 的"修复完成"判定输入,跟找出 finding 同等重要。不要硬凑低价值 finding。

## 范围边界

- P1.3B(`step_8_apply_to_master`)仍被 owner gate 阻塞,不审。
- exploratory 路径只审"能否污染 certified 面"。
- 不审 P0 修复面之外的求解器模块(那是另外的审查线)。

包 sha256:`56c3f3fd40f3e8ee9342347977bec6adff81be8dc15e22f268fa25f6166f1ab9`
