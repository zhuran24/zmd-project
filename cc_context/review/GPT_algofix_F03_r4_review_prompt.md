# 终末地 IndustrialPlanner 精确求解器 — wireless 修复链 round 4 (F03-R3 residual 修复审查, 零 finding 确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

修复链背景 (归档全在包内 `cc_context/review/algoaudit_preprocess_face_r{1,2,3}_REVIEW_20260612.md`): r1 = F-01/F-02 (协议箱 omni_wireless 几何) → r2 = F-03 (无线终品生产端输出口经 `extract_port_specs` 泄入 routing) → r3 = F03-R3-01 (**RAB build-time 侧门**: `_filter_pose_binding_domain()` 不经 port specs、独立消费端口 front 可达性, `EXACT_B1_ROUTING_AWARE_BINDING` 开启时把被堵的无线终品输出 front 剪成假空域/假证书) + H03-R3-02 (语义校验不挡未来 dual-role generic_input)。本包刚落地 r3 两项修复:
- `_filter_pose_binding_domain()` 只按 **routing-visible ports** 过滤 (input 全保留 + 非 routing-free 的 output); RAB blocker 证书同样只看 routing-visible ports;
- `semantic_validator` fail-closed 守卫: `sink_kind="generic_input"` 商品同时出现在任何 recipe input → 拒绝;
- PROJECT_LOCK / specs/05 修正措辞: 排除必须覆盖**所有**端口 front 消费点 (撤销了早先错误的「单通道」论断)。

你的任务: 对抗式审查 r3 修复——确认正确且没引入新缝。**若审完无残留, 明确报零** (owner 判 preprocess/wireless 修复链收口的输入)。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 端口 front 消费点的穷尽性 (最重要)
r2 修了 `extract_port_specs`, r3 修了 RAB build-time filter + 证书——**还有没有第四处**独立消费「端口 front 可达性/占用」语义的代码? 请全仓穷举 (grep front / port 可达 / blocker / is_port_front_usable / routing_binding_context 等), 对每一处判定: 它对 routing-free 无线终品输出口的处理是否与新契约一致 (PROJECT_LOCK「exclusion must hold at EVERY consumer」)。特别看: `routing_binding_context.is_port_front_usable` 的其它调用点、patch/PCR 分离器、heuristic_feasible_finder、master 侧 boundary-port 可行性筛、flow 诊断。

### Q2 RAB 过滤修复本身
- routing-visible 集合构造对不对: input 全保留是否正确 (有没有 input 侧也该 routing-free 的形态)? output 过滤是否恰好 `routing_free_sink_commodities`?
- 过滤后 RAB 的语义还是「保守剪枝」吗——会不会把本应剪的 pattern 留下 (RAB 是性能优化, 留多 = 慢但 sound; 剪多 = unsound; 请确认方向)?
- env off (默认) 路径行为零变化?

### Q3 语义守卫
- 守卫位置 (semantic validator) 是否在所有 canonical 装载路径上都生效 (有没有绕过 validator 的 rules 读取)?
- 守卫的判定是否恰好 = 「会让排除断料」的形态, 有没有误杀合法未来扩展?

### Q4 回归与文档
新增 2 回归 (RAB 540-pattern 保留 / dual-role 拒绝) 判别力; PROJECT_LOCK/specs05 修正后措辞与代码一致性。

## 明确不要报的

- 设计决策 (canonical omni_wireless / routing-free, owner 已定); r1/r2 主体 (已收口, 除非与 r3 交互出新缝)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); data/hints stale (已档); 已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量应 **全绿 (≈2903 passed, 0 failed)**; 任何 failed 都值得查。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; 关键论证写正文。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列实际穷举过的 front 消费点清单。

## 范围边界

- 重点 = r3 改动面 + Q1 的全仓 front 消费点穷举; P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

包 sha256: `a5a7e2d7b66917b1f77d621f5e5da83978948cc8bf9ea3437dbaeff9e0e40d46`
