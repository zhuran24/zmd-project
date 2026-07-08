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

## 生产轴预算验证（26×26，已完成）

26×26 ghost、master 1800s / binding 600s / routing 600s、max_iterations 3、workers 4、attach on（`results_scan/cell_g26x26_prod_on.json`）：**仍 UNKNOWN**——master 烧满 1800s（lbbd_wall 1829.7s，1 轮），binding/routing 未开审，attach 零触发。

**结论 4**：本机（Windows / 24 逻辑核 / workers=4）连生产轴预算（1800s）都解不动 26×26 的冷启动 prod-scale master 单轮。600s→1800s 三倍预算无任何进展信号。

## 进行中：降尺寸扫描（8/12/16 见方，workers=12）

思路：ghost 越小 → 留给 266 设施的面积越大 → master 打包越容易。之前扫描下界只到 20×20；若 8×8/12×12 能出解，LBBD 真正转起来，那就是 attach 的有效战场（M5 测的是 attach 机制的收敛影响，任何能让 LBBD 迭代的 cell 都是有效数据点）。同时把 workers 提到 12（可行性优先，归因其次）。

分支预案：
- 小 ghost 出解 → 锁定尺寸带跑正式 on/off A/B 矩阵。
- 全 UNKNOWN → 「本机任何 ghost 尺寸都解不动冷启动 master」成立；排查生产是否依赖跨 ghost warm-start（孤立 cell 测量设计可能需改 mini-campaign 形态），带完整数据向 owner 要资源方案（Linux 机 / 超长预算 / 测量形态改造）。

## warm-start 机制诊断（探针实测 + 源码，2026-07-08）

探针（`build_exact_candidate_warm_start` 只建不解，`scratchpad/m5_warmstart_probe.py`）坐实：

1. **greedy hint 存在且完整**：266 实例全量 hint，0.4s 建成，`mandatory_hint_occupied_cell_count=3544`——设施占 4900 格的 72%（布局不变量：全盘空格恒 1356，ghost 面积上限 ≈36×36）。
2. **ghost-aware 修复机器整体被跳过**：`EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS=64`（`master_model.py:89`），而 26×26 有 2025 anchor、8×8 有 3969 → 任何现实 ghost 都 `skipped_anchor_limit`，pose-order portfolio / local repair / coordinate validation 全零尝试。master 拿到的 hint 永远「不管 ghost」，要自己在 72% 满的盘上腾洞。
3. **生产同样如此**：wrapper 只设 `EXACT_CP_SAT_WORKERS`/`EXACT_PARALLEL_PROCESSES`，不抬 anchor 限——生产靠 24h+ 时长 + 多进程多 ghost 并行硬磨。
4. **worker 链正常**：stage env → `EXACT_CP_SAT_WORKERS` → 默认 8（`cp_sat_worker_config.py:52-60`），harness 设置有传导。
5. **早退 UNKNOWN 已解释（headline 发现）**：16×16 的 `last_solve` 显示 `wall_time=530.9s、user_time=530.9s（单线程）、deterministic_time=18.8、branches=0、conflicts=0、booleans=0`——**CP-SAT 全程卡在单线程 presolve，搜索根本没开始**（0 布尔变量 = presolve 未完成即返回），12 workers 全程闲置。solve() 在 exact 模式强制 `probing_level>=3`、`symmetry_level>=3`（`master_model.py:11527,11533`），9196 interval 的模型上正是 presolve 时间黑洞。**600s 预算 ≈ 全交 presolve 税；生产轴 1800s 也要先交 ~500s+ 税**（26×26 prod cell 烧满 1829s，presolve 后的实际搜索时间未知——当时无 last_solve 遥测）。

可试旋钮（全在 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`，certified 合法）：`EXACT_MASTER_CP_MODEL_PRESOLVE`（关 presolve）、`EXACT_MASTER_CP_MODEL_PROBING_LEVEL` / `EXACT_MASTER_SYMMETRY_LEVEL`（压到 1，绕开强制 >=3）、`EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS`（解锁 ghost-aware）、`EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS`（默认 8，每 anchor 验证 2s）、`EXACT_MASTER_SEARCH_BRANCHING`（默认 fixed）、`LBBDController(disable_master_warm_start=True)`。

**presolve 探针矩阵（进行中）**：P1 = probing1+symmetry1；P2 = presolve 全关；P3 = presolve 关 + ghost-aware 解锁（anchor 4096/验 32）；P4 = P1 + branching=automatic。各 8×8/600s/w12。另有 build-only 探针单测 ghost-aware 解锁后的修复机器遥测。原 K2/K3 在 presolve 税下无意义已撤销。

**ghost-aware 解锁探针结果（headline 4，`probes/ghostaware_probe_8x8.txt`）**：anchor 限抬到 4096 后修复机器真跑了——161 anchor 尝试重建、32 个重建出**完整布局**（798 字段全钉死）进坐标验证；但验证 mini-solve（`EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS=2.0`，profile 带 presolve on/probing2/symmetry2）**32 个全部 UNKNOWN、branches=0、deterministic≈0.01**——全钉死的模型本该毫秒级传播出 FEASIBLE/INFEASIBLE，2s 全花在 presolve 上。修复机器不是坏的，是它的验证器也在交 presolve 税 ⇒ `none_compatible` 是假阴性。总耗时 423s（anchor 4096/验 32 的 bound 生效）。**验证 profile 追查结论**：调用传的是空 profile，采样值 probing2/symmetry2/presolve-on 全是 CP-SAT 默认——**没有关验证 presolve 的旋钮**，唯二 env = `..._VALIDATION_SECONDS`（默认 2.0）与 `..._VALIDATION_MAX_ANCHORS`（默认 8）。出路 = SECONDS 抬到 presolve 完成量级（~600-900s/anchor）× MAX_ANCHORS 压到 2——贵但决定性：验证 FEASIBLE 一个 anchor = 拿到「已验证可行」完整 hint，master 从可行解起步。

**P2/P4 并发 OOM 崩溃（教训）**：P2（presolve off）与并行加发的 P4（automatic branching）12:36:31 同刻死于 0xC0000409（ucrtbase.dll abort = 原生 `bad_alloc`→terminate 形态，WER 双记录）；本机 47.7GB RAM，两个 prod-scale master 并发 solve 吃穿内存。**教训：master solve 必须串行（一次一个）**；P4 单独重跑排队在 P3 后，带 `EXACT_SUBPROBLEM_MAX_MEMORY_MB=28000` 自限（白名单 env，`master_model.py` solve 里 `apply_subproblem_memory_cap` 消费）。P2（presolve off 是否本身可行）由 P3 的 solve 段代答——P3 独占跑同款 presolve-off。

**P1 结果（headline 2+3）**：probing/symmetry 压到 1 → presolve 税消失，搜索真跑起来（booleans 2.13M、branches 5.59M、conflicts 23.9K、propagations 5.05 亿），但 743s 仍无可行解。`restarts: 0`——fixed 策略无重启。（初判「user_time==wall_time ⇒ 单线程」**存疑收回**：OR-Tools response 的 user_time 未必是聚合 CPU 时间，所有 run 两值微秒级相等更像 wrapper 行为；多线程是否真生效待用任务管理器/Get-Counter 级证据。）

**P4r 结果（单独跑 + 内存帽，exit 0）**：automatic branching 生效（restarts: 5），667s 搜 4.98M branches——与 fixed 无质差。**汇总：fixed/automatic × presolve on-diet/off，8×8 均 ~600-750s 搜索无解**；配置旋钮已基本穷举，剩下的变量只有【更小 ghost（6×6 历史战场）】与【更长预算】。

## 历史战场坐标（headline 5，仓库出土）

`data/solutions/cuts_*.json`（历史 CutManager checkpoint，tracked）：15x15/25x9/36x35/37x36/45x5/70x70 全空 `[]`，**唯 `cuts_6x6.json` 有 5 条真 cut**（whole-layout conflict_set、266 实例、`cut_type: micro`、`iteration: 1`）——历史实跑在 **ghost 6×6**（最小合法尺寸）master 至少出过 5 个候选、全被 binding/routing 否决 = attach 触发点真实发生过的地方。M5 战场坐标 = 6×6 及邻近最小尺寸带；本轮扫描原只探到 8×8。6×6 cell（P1 配置 + 内存帽）已排队在 P4r 之后。

**P3 结果**：presolve-off 单独跑不崩（P2 之死 = 并发 OOM 坐实）；搜索即刻开跑（772s 搜 7.17M branches / 7.7 亿 propagations），仍无可行解；ghost-aware 同样 none_compatible（验证税，同探针）。fixed 单线程无重启的可行性搜索在 8×8 上 ~750s 量级不够。

**6×6 第一发（p1cfg：probing1/symmetry1/600s）**：UNKNOWN 且 branches=0——probing1/symmetry1 在 8×8 够用，在 6×6（interval 11596、anchor 4225，模型更大）又卡回 presolve 死区；deterministic_time 停在 18.759，与默认配置卡死的 16×16（18.7588）同指纹——presolve 的 wall 黑洞对 probing/symmetry 级别只部分敏感、对模型规模强敏感。P3 已证 presolve-off 是唯一可靠让搜索立刻开跑的配置 ⇒ 第二发 = 6×6 + presolve off + master 1800s（搜索独占）+ 内存帽。（另：runner 结果回显此前漏了 max_memory_mb 键，已补——6×6 第一发实际带 28000 帽。）

**6×6 第二发（presolve-off/1800s）**：搜索满跑 2010s（7.17M branches / 2.18M booleans）仍无解。可疑指纹：branches/conflicts 与 8×8 P3 几乎一致（7.17M/~3025）——guided fixed search 不管 ghost 尺寸都走进同一泥潭。

**headline 6：subsolver 过滤器砍掉了首解主力。**`MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX`（`cp_sat_worker_config.py`）过滤 `feasibility_pump`/`violation_ls`（= CP-SAT feasibility-jump，现代首解发现主力）——Phase 3C 为 max_lex 目标调参的决定，但对「找第一个可行解」正好是反向优化。过滤器在 solve() 硬调用、无 env。harness 加 `--no-subsolver-filter`（测量专用 monkeypatch，结果 JSON 透明记录，绝非 certified 旋钮）。

**6×6 第三发（全火力，进行中）**：presolve-off + automatic + 无过滤 portfolio + w12 + 1800s + 内存帽 = 本机可用的最大火力可行性尝试。它若再失败，「本机 <=1800s 单 master 无首解」的 verdict 证据链完整（配置空间已穷举：presolve on/diet/off × fixed/automatic × 过滤/全 portfolio × hint 有/无 × ghost 6-40 × 90-1800s）。

另备 `--search-profile`（三档：guided_branching_v4 / ghost_after_counts_v1 / ghost_first_v1，allowlist env）未试。

**6×6 第四发（presolve-then-portfolio 3600s，重启后重跑）**：solve ~28min 处 `ortools.dll` 内 ACCESS_VIOLATION（0xC0000005，WER 坐实；独占跑、35GB 空闲、非 OOM）——头号嫌疑是 `--no-subsolver-filter` 放回的 `violation_ls`/`feasibility_pump` 在此模型触发 OR-Tools 原生 bug（若坐实，Phase 3C 的过滤清单意外起到了避崩作用，值得记入生产复核材料）。**第五发（隔离验证，最后一发）**：同配置去掉旁路（过滤 portfolio），3600s——**同样 `ortools.dll` 0xC0000005**（solve ~11min，偏移 0x80e689 ≠ 第四发 0x7ae290）。旁路排除；崩因 = 6×6 + automatic + presolve-on 组合在本机 OR-Tools 原生不稳定（P4r 同参数 8×8/600s 干净退出为对照）。**本机逃逸路径全部封死** ⇒ verdict 定稿（见 `m5_phase1_verdict.md`）。

## 判据（M4 卡记载，verdict 时对照）

收敛判据 + telemetry 阈值：cut 计数 >10^5 = 撞墙，<10^3 = 工作区间（`attached_by_family` 数据源已就位）。

## Linux（CachyOS 本机）复测（2026-07-08 晚，同一硬件双系统）

**第一发 `cell_g6x6_linux_p4cfg_1800.json`**（6×6 + probing1/symmetry1 + automatic + w12 + 1800s = Windows 两发段错误的组合）：
1. **不崩**——干净跑满 1800s（exit 0），0xC0000005 确认是 Windows OR-Tools 构建特有，不是组合本身有毒。
2. **真并行**——deterministic/wall = 9461/1807 ≈ **5.2**（Windows 各配置仅 1.1-2.1）：automatic portfolio 在 Linux 真正多 worker 开工。「Windows 上 worker 疑似没生效」由此坐实为 Windows 侧现象。
3. **仍无首解**——4.17M branches / 453 conflicts / 0 restarts，6×6 在 1800s 真多核搜索下 UNKNOWN。

运维事实：12 worker 满载 CPU 95°C（本机今晚已一次过热硬重启，owner 调参后本发扛住）；分离进程 wrapper/日志必须放 `~/m5_runs/`（/tmp 重启即清）。

**第二发（进行中）`cell_g6x6_linux_ghostaware_v600.json`**：ghost-aware 验证加时（`EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS=600`×4 anchor + anchor 限 4096）——Windows 诊断已证重建能产完整布局、验证被 2s 预算掐死是假阴性；若验证过一个 anchor = 已验证可行 hint，master 从可行解起步。

**第三发 `cell_g6x6_linux_ghostaware_v600b.json`**（anchor 限修正为 5000 > 4225，管线真跑）：4 anchor 验收各烧满 600s **全部超时**（warm-start 段 2400s 分毫不差）→ `none_compatible` 仍是假阴性——presolve 黑洞连全钉死模型的 600s 验收都不够。master hint-less 1800s UNKNOWN（conflicts **85008** vs 前几发 453/1009——搜索轨迹方差巨大 ⇒ 种子组合值得赌）。注：第二发 v600 因我把 anchor 限设 4096 < 6×6 的 4225 被整体跳过（作废，等价于重复第一发）。

**过夜队列（进行中，`~/m5_runs/m5_overnight_queue.sh`）**：A = 7200s 长赌 → 不中则 B/C/D = `EXACT_MASTER_RANDOM_SEED` 7/13/42 × 1800s → 任一出解自动跑 attach-off 孪生（凑第一对 A/B）。

## Linux 过夜全战报（2026-07-09 00:00-04:15，BIOS 默认降频期）

**过夜队列（winner=none）**：7200s automatic 长赌 UNKNOWN（dtime 34088 = 1800s 发的 3.6 倍工作量，branches 却几乎持平——深水区打转）；种子 7/13/42 × 1800s 全 UNKNOWN。全夜零崩溃零热重启（BIOS 默认 + 前段 8 核限载）。

**Q2 队列（winner=none，三个新旋钮）**：
- **q2a 重建布局直喂**（抽取探针捞回 anchor 132 完整布局经 `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` 喂入 + `EXACT_MASTER_HINT_CONFLICT_LIMIT=1000` + automatic + w24）：hint 确认加载（214 overrides→266 全覆盖）、branches 13.6M（3 倍吞吐，轨迹剧变），仍 UNKNOWN。解读：greedy 重建布局在完整模型下疑似不可行（不保证供电容量等全局约束——正是验收环节的职责），solver 需在 hint 邻域证伪后逃逸。
- **q2b ghost_first_v1 档**：41s 崩——`exact_coordinate_master.py:3962` `_apply_ghost_anchor_power_capacity_screen` 中 `max_capacity += coeff * int(...)` 的 `coeff` 是 `list_iterator` → TypeError。**非默认 profile 的潜伏 bug 出土**（生产只走 v4 从未触发；sealed 文件，修复归 reseal 批，勿夜战动刀）。`ghost_after_counts_v1` 档因此也存疑待验。
- **q2c 修复上限单变量**（`EXACT_MASTER_HINT_CONFLICT_LIMIT=1000`）：UNKNOWN，无效。

**工具沉淀**：`~/m5_runs/extract_rebuilt_hints.py`——1 秒抽取 N 份 ghost-aware 重建完整布局（135 anchor 尝试出 3 份，anchor 132/133/134；与 Windows 的 128-135 带一致）。

**运维坑（已入环境卡）**：热重启撕裂运行期 `__pycache__` → 先后伪装成 checker 子进程 SIGSEGV 与 master 构建 KeyError；清缓存即愈（源码无恙有 close-kernel 校验背书）。

## 对抗复核（2026-07-09 凌晨，三镜头 opus 工作流）修正记录

- **种子推理反转**：受控种子对照 s7/s13/s42 conflicts = 812/838/818（≈3% 差）——地形对种子高度均匀；我此前引的 453→85008「两个数量级方差」是跨配置错比（85008 来自 restarts=41 的 v600b ghost-aware 发）。
- **q2a 推断撤回**：UNKNOWN≠布局不可行；hint 密度 798/1,549,300（<0.06%——apply_solution_hint 只 hint 每实例 x/y/mode 整数）是更简单解释；「供电容量病因」无区分性证据（greedy 重建同等不保证覆盖/端口/路由）。
- **q2b 改判疑似假崩**：崩点上一行 `coeff = int(...)`（exact_coordinate_master.py:3955）恒 int；`_apply_ghost_anchor_power_capacity_screen` 对所有 profile 无条件调用（:3765）；q2a 默认档同行跑通——Q3z 复现测试裁决。
- **「穷举」证伪，五族未试旋钮出土**：no_overlap_2d 四件套（allowlist benders_loop.py:1303-1306，消费 master_model.py:11567-11613，自述 packing 提速 10-20%）；IGNORE_LP_SUBSOLVERS（:1301，消费 cp_sat_worker_config.py:239-267，LP 在本 packing 模型上自述 weak）；LINEARIZATION_LEVEL（:1302）；SUBPROBLEM_PARAMS 通用注入口（:1319，任意 solver.parameters setattr）；PORTFOLIO 分支值。→ Q3 队列（q3z 复现 + q3a 传播器套 + q3b 无LP + q3c portfolio + q3d 组合拳）实测中。
- 措辞修正：「4 随机种子」→3；「选项 1 已证伪」→「其同硬件短预算单 ghost 切片已证伪，≥24h 多 ghost campaign 轴未测」。

## Q3 队列验尸（2026-07-09 04:37-05:51，复核出土弹药第一轮）

- **q3z（ghost_first 复现测试）**：exit 137 = 内核 OOM kill（RSS 39.3GB @w24，journalctl 坐实）。跑了 ~10 分钟未见 TypeError → **q2b 假崩坐实，「潜伏 bug」记录撤销**（新证据链：q2b 41s 崩 vs q3z 同档 10 分钟无恙）。新教训：**w24 部分配置 RSS 冲 39GB+，CP-SAT 内部 memcap(28000) 拦不住峰值**（软帽周期检查晚于内核 OOM）→ 回 w12 或 systemd-run MemoryMax 硬帽。
- **q3b（无LP）exit 1 @31s / q3c（portfolio）exit 139 段错误 @43s**：紧跟 q3z 的 SIGKILL——「硬杀进程撕裂写入中的 .pyc → 下一发撞缓存鬼」模式再现（q3b 的 TypeError 是 builtins 级荒谬错：`int object is not callable`）。Q4 清缓存复跑裁决。
- **q3a（no_overlap_2d 传播器三件套）**：真生效（参数存在性+env 解析已验证）但**近乎无效果**——branches/conflicts 4.18M/458 vs 不开套装的 4.17M/453，轨迹几乎复制。有效负结果：packing 专用传播器不改变本问题的首解搜索。
- **q3d（套装+无LP 组合）**：UNKNOWN（4.57M branches / 27.7K conflicts——IGNORE_LP 显著改变轨迹但未破局）。
- **Q4 收尾队列（进行中）**：q4a 无LP 复跑 / q4b portfolio 复跑 / q4c ghost_first w12 首次完整跑——全部 w12 + 每发前防御性清缓存。

## Q4 收尾（06:00-06:58）与 ghost_first 关停

- **q4a（无LP，清缓存复跑）**：干净跑满，UNKNOWN（4.17M/465）——q3b 的 TypeError 缓存鬼坐实。无 LP = 有效负结果。
- **q4b（portfolio，清缓存复跑）**：干净跑满，UNKNOWN（4.90M/809）——q3c 的段错误亦缓存鬼。PORTFOLIO 分支 = 有效负结果。
- **q4c（ghost_first w12，清缓存）**：34s SIGSEGV（coredump 在案，死于 import/session 构建段）。**ghost_first 档三跑三死死法各异**（q2b 缓存鬼 TypeError@41s / q3z OOM@10min / q4c 段错误@34s）——本机不可测，关停此线；硅脂期热应力下的硬件级随机错误无法排除（机器同期有 95-100°C 历史）。
- 夜战 Linux 侧有效 cell 总账：12 个干净数据点全 UNKNOWN（p4cfg/v600b/7200s/s7/s13/s42/q2a/q2c/q3a/q3d/q4a/q4b），配置维度覆盖 presolve×branching×hint×LP×传播器×种子×预算(0.5-2h)。
