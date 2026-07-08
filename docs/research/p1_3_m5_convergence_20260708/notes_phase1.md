# M5 收敛实测 · 第一阶段笔记（2026-07-08）

目标：在非 certified 路径上，用真 266 实例 + 真 LBBD 循环实测 cut framework attach 的收敛影响（A/B 对照），为 owner 的升格裁定提供实测数据。harness 合法性论证见 `../p1_3_m4_recon_20260708/m5_harness.md`；红线 = 输出绝不碰 `data/checkpoints`、`data/solutions`、supervisor_seal。

## harness 验证（烟测，✅ 通过）

`m5_cell_runner.py` + `m5_ab_driver.py` 全链工作：session 构造（~45-60s）→ master build（~60-80s）→ LBBD 循环 → 指标采集（per-family 明细直读 `build_stats`，补上「不落盘」的采集缺口）→ JSON 落盘。每 cell 独立子进程（M1 内存滞留隔离）。

## 实测数据（全部 attach 战场未打开）

| cell | ghost | master 预算 | workers | master 首轮结果 | LBBD wall |
|---|---|---|---|---|---|
| smoke off/on | 40×40 | 90s | 1 | UNKNOWN | ~95s |
| scan | 20×20 | 600s | 4 | UNKNOWN | 649s |
| scan | 26×26 | 600s | 4 | UNKNOWN | 643s |
| scan | 32×32 | 600s | 4 | UNKNOWN | 524s（提前放弃） |

**结论 1**：prod-scale master（266 实例全量坐标模型）单轮在本机（Windows / 4 workers）**600s 出不了第一个候选**——binding/routing 不开审，attach 零触发（`coordinate_framework_cut_count` 全 0）。这不是 attach 的问题，是战场还没打开。

**结论 2（成本现实）**：master 单轮需要接近生产轴预算（1800s）。单 cell 数小时级、完整 A/B 矩阵十几小时级（过夜）。本机数据是保守下界（生产 wrapper 是 Linux 导向）。

**结论 3（M5 第一批产出）**：「本机 workers=4 / 600s 解不动 prod-scale master 单轮」本身就是可行性数据点，直接决定实测排期形态。

## 进行中：生产轴预算验证

26×26 ghost、master 1800s / binding 600s / routing 600s、max_iterations 3、workers 4、attach on——分离 pwsh 进程跑（2026-07-08 11:01 启动，最坏 ~2.5h），输出 `results_scan/cell_g26x26_prod_on.json`，完成时 `scan_progress.log` 追加 `=== 26x26_prod done ===`。

分支预案：
- master 出解（status 非 UNKNOWN、binding_status 非 None）→ 锁定该配置为 A/B 战场，`m5_ab_driver` 跑正式 on/off 对照矩阵（过夜级）。
- 仍 UNKNOWN → 实测需要资源方案拍板（更长预算 / Linux 生产机 / 降规模中间验证），带完整数据呈 owner。

## 判据（M4 卡记载，verdict 时对照）

收敛判据 + telemetry 阈值：cut 计数 >10^5 = 撞墙，<10^3 = 工作区间（`attached_by_family` 数据源已就位）。
