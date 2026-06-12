# 终末地 IndustrialPlanner 精确求解器 — binding 建模忠实度面 round 6 (饱和确认轮·R5 修复确认 + 单快照族终验 + binding 数学换角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_bind_r6_snapshot_ec504afe.zip`, sha256 `ec504afe704b4a1cea6597a3956d7e68fd5adc195961cd4724e69cd354ffb50f`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: binding 建模忠实度 (PortBindingModel + 其 proof 输入链), r1-r5 收敛轨迹 2→2→5→1→1

binding 面历史 5 轮 (报告在包内 `cc_context/review/algoaudit_binding_face_r{1..5}_REVIEW_20260612.md`): r1 = F-BIND-R1-01/02 (`__unused__` 哨兵 + loader fail-closed); r2 = F-BIND-R2-01/02 (master loader 分叉 + strict JSON); r3 = F-BIND-R3-01..05 (单解析/单快照族五连: binding 收 master 快照 / master `_load_json` strict / 槽数 strict int / wireless 槽数参数化流入四消费点 / campaign helper 走共享 loader); r4 = F-BIND-R4-01 (wireless 槽数漏注入 binding = 第五消费点); **r5 = F-BIND-R5-01 (outer_search 的 certified frontier 候选域在 session 之外直读 wireless 槽数 + parallel worker 自建 session 无 hash 一致性回报; 已修 = outer domain snapshot 封印 [hashes+generic_io+槽数] + 每次 session 创建后全等校验 fail-closed RuntimeError + worker 接收 expected hashes 不一致即 STARTUP_ERROR)**。**本轮 r6 = r5 修复确认 + 单快照族终验 + 刻意换角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BL-R3 / F-GM-Q3 / F-RT-R2 / F-CUT-R2 / F-PRE-R8 系列条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-BIND-R5-01 修复确认 (攻击面)
把 r5 修复当攻击面打: ① outer domain snapshot 封印的字段集 (artifact hashes + generic_io_requirements + wireless 槽数) 是否**漏了会影响候选域形状或候选证明语义的第四类 proof 输入** (如 canonical rules 本体、mandatory instance 集、admissibility 参数)? ② 「每次 session 创建后全等校验」是否真覆盖**所有** session 创建/ensure 路径 (有没有旁路构造 ExactSearchSession 而不过校验的生产代码)? ③ worker STARTUP_ERROR 路径: expected hashes 从 coordinator 到 worker 的传递链有没有可篡改/可缺省点 (缺省时是 fail-closed 还是静默跳过校验)? ④ 校验失败的 RuntimeError/STARTUP_ERROR 在上层是否被吞 (被 except 接住降级继续 = 封印形同虚设)?

### Q2 单解析/单快照族终验 (R3→R4→R5 三轮连挖后的收口问)
这族已连续三轮各挖出新消费点。请做**终验级穷举**: 全仓搜索每一处读 `generic_io_requirements` / wireless 槽数 / artifact hash 的代码 (含测试外的 scripts/ 与 src/render/ 等 postprocess), 按「proof 输入 (必须走快照/共享 loader) vs 非 proof 引用 (diagnostic/render, 可独立读)」二分逐个判读。若全部消费点已收口, 明确写出清单与判读依据; 若仍有残留, 给 probe。

### Q3 binding 模型数学忠实度换角度 (r2 审过结构假设 7 项, 本轮审「枚举与对称」)
① binding alternatives 枚举: `add_nogood_cut(selection)` 排除一个 selection tuple 后重解, 枚举是否保证**不重不漏** (CP-SAT 重解会不会回到同构但变量不同的等价 selection 造成 alternatives 计数虚高, 或 nogood 形状意外排除未证伪的邻近 selection)? 与 F-BL-R3-01 (cap 命中 → UNKNOWN, 穷尽证明唯一来源 = 重解 INFEASIBLE) 的 binding 侧语义是否一致 — binding model 里有没有自己的内部 cap/早停会先于外层 cap 触发? ② 槽-商品分配的对称性: 同 facility 多个等价 generic 槽间的置换对称, binding 是否会把同一逻辑分配的置换变体当不同 alternatives 枚举 (纯性能噪声还是会影响「alternatives 穷尽」证明的正确性 — 置换变体被 nogood 排除后其镜像仍可行, 这是预期行为, 但确认穷尽循环最终会逐个排掉而不是提前误判穷尽)? ③ `__unused__` 哨兵与精确计数约束的交互在**需求 < 槽数**的非满额配置下 (当前 base 52=52 满额, 但 fail-closed 不应依赖巧合): 计数约束 + 哨兵 + ExactlyOne 三者联立是否对任意 R<=S 配置都恰好编码「R 个真实商品 + S-R 个空置」?

### Q4 r1-r5 修复交互抽查
五轮修复全部叠加后: loader fail-closed (r1/r2) × 快照注入 (r3/r4) × 域封印 (r5) 三层在同一次 certified run 里各自触发的异常类型/时机不同 — 有没有组合次序使一层的失败被另一层的 except 误吞? 抽查 2-3 个组合即可 (全组合不要求)。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r5 已修 finding 与已审结论 (重复报不算)。
- preprocess/master 几何/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- generic utility roster 扩展时的 profile-driven guard 建议 (r2 已挂账, owner-gate 扩展时同步)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2951 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 终验穷举清单 (消费点 × proof/非 proof 判读)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R5 修复确认 + 单快照族终验穷举 + binding 枚举/对称数学 + 修复交互抽查; 其余面不审。
