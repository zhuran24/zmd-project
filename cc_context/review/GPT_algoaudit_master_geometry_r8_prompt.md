# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 8 (终饱和轮·R7-HINT 修复确认 + 对称破缺与 mandatory 装配本体 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_37b84be0.zip`, sha256 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master (`src/models/exact_coordinate_master.py` + `src/models/master_model.py`), 收敛轨迹 1→1→1→0 (r7 零), 本轮 = 终饱和轮 (连零 2 达标轮)

本面近 4 轮 (报告在包内 `cc_context/review/archive/`): r4/r5 = power pole family 通道系列; r6 = F-GM-R6-01 (cut 后旧 solver witness); **r7 = 零 soundness finding (首个干净轮)**: R6-01 修复确认 (solve 派生字段 10 行处置全表) + ghost 编码本体 (anchor 枚举完整/body-only 互斥全 7 模板族实证/max_lex 无加权目标/无 exterior 约束) + hint 通道 (永不约束实证) + LOW F-GM-R7-HINT-01 已修 (malformed hint [非 int/越界 pose/不存在 anchor] 统一降级 skip 不再 solve 前抛异常; ghost anchor 不再写全 0 矛盾 hint; 该修复在本包内, lock 有对应条款)。**本轮 r8 = 终饱和轮: HINT 修复确认 + 一个未直审本体 + 自由攻击角, 目标确认连零 2**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-RT / F-CUT 系列含 PCR-CUT-R6-H1 / F-PRE 系列条款), 这些面各有自己的线, 别在本轮重报。master 几何主体自 r7 hint 修复后零代码变化。

## 审查重点 (按优先级)

### Q1 F-GM-R7-HINT-01 修复确认 (攻击面, LOW 修复轻确认)
① skip 语义的连带: exact mandatory hint 的 `grouped_hints` 排序后与 slot `zip` 配对 — 某 pose skip 后列表缩短, zip 截断的配对漂移会不会把 hint 配错 slot (hint 配错只影响速度, 但请确认没有借 hint 配对推导其它东西的路径)? ② 越界/非 int 检查的覆盖: skip 判据 (int() 失败 / 不在 `_template_pose_tuple_by_idx[tpl]`) 与 r7 报告所列三类 malformed 全对上吗, 有没有第四类 (负数 idx? float 形如 2.0?) 还能穿; ③ ghost anchor skip 后 `ghost_anchor_hint_applied` 的 telemetry 标注真实吗 (skip 了还标 applied = 误导诊断, 非 soundness)。

### Q2 对称破缺与 mandatory 装配本体 (新角度; 从未独立深审)
① **对称破缺**: `enable_symmetry_breaking` 相关约束 (canonicalization/字典序/slot 排序类) 的形态 — master 在固定 (w,h) candidate 下是可行性判定, 对称破缺必须保证「每个可行解等价类至少一个代表存活」: 找出每条对称约束, 论证它只删等价副本不删整类 (删整类 = false-INFEASIBLE = 漏真矩形)。特别核 mandatory group 内同构 slot 的字典序约束与 pose/坐标域的交互 (字典序 + 域裁剪的组合会不会把唯一代表裁掉)。② **mandatory 装配计数**: 266 实例→group→slot 的装配链 (38×manufacturing_6x4 / 46×boundary 等): group slot 数与 `mandatory_exact_instances.json` 逐 facility_type 对照; 每 slot 的 ExactlyOne/域非空; group 内 slot 与 instance 的对应是「计数」还是「身份」(计数口径下 instance 身份信息丢失对 binding 侧回读有影响吗 — binding 面已审过自己那半, 这里只审 master 侧给出的 contract)。③ **residual/optional slot 语义**: optional slot 的 active literal 与几何约束的 OnlyEnforceIf 挂接 — inactive slot 的几何约束全部失效吗 (残留一条 = 对 inactive 也约束 = 收紧方向), active 时全部生效吗 (漏一条 = inactive 幽灵占地)。

### Q3 自由攻击角 (终饱和轮惯例: 你自己选最薄弱的缝)
以上之外, 用你自己的独立判断选 1-2 个你认为本面还没被审透的点深挖 (例: AddAllowedAssignments 稀疏域表的生成口径; power coverage witness 表与 footprint channel 的对接; build 顺序依赖 [某约束依赖另一族先建好的变量]; `upper<fixed` 之外的 bound 通道; 或对 r3-r7 某个历史修复设计你自己的新攻击)。说明你为什么选它、攻击了什么、结论是什么。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r7 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线); PCR patch 模型 (cuts 面)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- canonicalization 不受 enable_symmetry_breaking 控制 (已判配置语义 — Q2① 审的是对称约束本身的保代表性, 不是这个配置归属); `upper<fixed` 真 INFEASIBLE + 诊断建议 (已挂账); 非矩形 footprint bbox 保守口径 (lock 已接受, false-INF 方向)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2988 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 对称约束逐条保代表性论证、装配计数对照表、Q3 选点理由与攻击过程。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = HINT 修复确认 + 对称破缺/装配本体 + 自由攻击角; 其余面不审。
