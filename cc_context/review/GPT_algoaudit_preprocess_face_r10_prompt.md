# 终末地 IndustrialPlanner 精确求解器 — preprocess 链面 round 10 (饱和确认轮·r9 修复确认 + pose 几何变换数学本体角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_70457b5e.zip`, sha256 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: preprocess 链, r1-r9 已收敛, 本轮目标第 2 个干净轮

preprocess 面历史 9 轮 (报告在包内 `cc_context/review/` 与其 `archive/`, 文件名 `algoaudit_preprocess_face_r{1..9}_REVIEW_2026061x.md`): r1-r4 修掉 wireless routing-free 链 4 批; r5 零 finding; r6 抓 R6-F-01 (plan 静默覆盖 canonical + hash 闭包缺口, 已修); r7 零 finding; r8 抓 F-PRE-R8-01 (再生成链 4 装载点默认 `json.loads`, 已修 = 共享 strict loader); **r9 抓 F-PRE-R9-01 (strict JSON 未拒数字上溢: `1e309` 经 `json.loads` 成 `inf` — `parse_constant` 只拦拼写常量没设 `parse_float`; 且 `build_current_preprocess_context.py` 复用的 writer 无 `allow_nan=False` → 上溢值可流入 context/parity 工件写出非标准 `Infinity`; 已修 = `parse_float` 拒非有限 + 本地 strict atomic writer 保 fsync + `allow_nan=False`)**。r8 已审枚举完备性 (独立重建 66403 池零差) 与 ceil 数学; r9 已审装载/写出点穷举、三件套×canonical 交叉一致性 12 行矩阵、再生确定性 (固定枚举序, 无随机/时间戳)。**本轮 r10 = r9 修复确认 + 刻意换新角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND-R1..R5 / F-BL-R3/R4 / F-GM-Q3 系列 / F-RT-R2..R4 / F-CUT-R2 + CUT-R3-H1/CUT-R4-H1 系列条款), 这些面各有自己的线, 别在本轮重报。preprocess 链自 r9 修复后零代码变化。

## 审查重点 (按优先级)

### Q1 F-PRE-R9-01 修复确认 (攻击面)
把 r9 修复当攻击面打: ① `parse_float` 拒非有限的实现 — 正常 float (含科学计数法/负数/极小值/`-0.0`/长精度) 行为是否真的零变化? `parse_int` 路径有没有对偶缝 (Python int 无上限, 但有没有 int 字面量被 `parse_float` 路径意外接管或反之)? `-1e309` / 嵌套数组里的上溢 / 字符串里的 "1e309" (合法, 不应拒) 三类是否都判对? ② strict atomic writer — fsync/rename 原子语义是否保住 (崩溃窗口)? `allow_nan=False` 是否覆盖该 writer 的全部调用方? 还有没有别的 preprocess 写出点绕过它? ③ r9 宣称「当前冻结工件干净 + 修复后再生 hash 字节级不变」— 独立复核。

### Q2 pose 几何变换数学本体 (新角度)
`src/placement/placement_generator.py` 从 canonical facility 模板 (w/h/端口表) 生成 66403 个 candidate pose 的**几何变换数学**此前从未被独立审过 (r8 审的是池大小/anchor 域/等价类计数, 不是坐标变换正确性)。请独立从 canonical 模板出发重推: ① rotation/orientation 的坐标变换 (90°/180°/270° 旋转下 w/h 交换、cell 坐标映射、端口 (x,y) 映射) 是否数学正确 — 选若干非对称模板手算对照; ② 端口 `dir` (N/E/S/W) 随旋转的方向映射是否与 cell 坐标变换一致 (port 在北边缘→旋转 90° 后应在哪条边、dir 应变成什么; **方向极性错误是本项目曾真实发生过的缺陷形态**, routing 面 F-RT-R2-01 即 sink front 极性反向); ③ orientation 等价类去重 (对称模板少生成的 pose) 是否真的等价 — 有没有「看似对称实则端口布局打破对称」的模板被错误折叠? ④ port_mode/输入输出口集合在不同 pose 间是否保持模板语义 (口数/商品/侧别不漂)。

### Q3 schema 校验 vs 实际消费的滞后面 (新角度)
preprocess 工件有 schema 校验 (jsonschema), 消费侧 (preprocess_context / placement_generator / instance_builder) 实际读的字段集是否与 schema 锁的字段集对齐: ① 有没有消费侧读了 schema 没锁的字段 (schema 漂移不报错, 字段静默缺失走默认值 = fail-open 方向)? ② 有没有 schema 锁了但消费侧不读的字段 (维护性噪声, 顺带列出)? ③ schema 对数值的约束 (非负/整数/范围) 是否弱于消费侧假设 (例如消费侧假设 count>=1 但 schema 只说 integer)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r9 已修 finding 与已审结论 (报告在包内, 重复报不算)。
- binding/master/campaign/scheduler/routing/cuts 各面 (各自有线; lock 末新条款即它们的产物)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- commodity_demands.json 不在 hash 闭包 (r7 已判 diagnostic-only, 再审触发条件 = 未来 certified 分支依赖它)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2968 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉 candidate_placements 再生或登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 实际手算对照过的模板/旋转组合清单与 Q3 字段对齐矩阵。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = r9 修复确认 + pose 几何变换数学 + schema/消费对齐; 其余面不审。
