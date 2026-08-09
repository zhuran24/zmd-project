# 诊断侦察·encoding_archaeology（Fable，2026-07-09）

## Headline

编码考古实锤方向正确但年代要修正：历史 6×6 候选出自 ≤2026-05-15 的 pose-indexed set-packing 旧编码时代（非 coordinate_exact_v2 的任何版本，后者自 2026-03 诞生起 prod-scale 零 FEASIBLE），且仓库已有一次同锚受控 A/B（B1 Phase 0：pose-bool 53s OPTIMAL vs coordinate 30min UNKNOWN，~34x）——旧编码以 PoseBoolExactMasterDelegate 活体存留、自由锚已补全，换硅脂后 2 小时机器时即可在 6×6 战场直接裁决"编码代价"假设。

## 硬事实

- cuts_6x6.json 的 5 条 cut 是 bare-list 旧 schema（字段仅 cut_type/conflict_set/iteration/metadata，cut_type 全为 'micro'，iteration=1,1,2,1,1）；当前 CutManager.load 对 bare list 直接判 rejected_legacy，当前生产代码产的 cut_type 只有 power_subproblem_infeasible_nogood/binding_infeasible_nogood/routing_front_blocked_nogood/routing_exhausted_nogood，'micro' 在现源码零产地 —— 5 条 cut 出自已灭绝的旧代码时代
  - 出处: data/solutions/cuts_6x6.json；src/models/cut_manager.py:492-497；src/search/benders_loop.py:5674,6065,6724,7197
- conflict_set 组成：865 键 = 266 mandatory 实例 + 599 个 power_pole（cut2/4 为 864=266+598），值是 pose_idx（pole pose_idx 72-4753，与现 candidate_placements.json pole 池 4761 相容；全池 7 模板共 66,405 poses）——历史 master 输出的是含全部电线杆的 pose-indexed 完整布局，且 iteration=2 证明历史 LBBD 真转到过第 2 轮
  - 出处: data/solutions/cuts_6x6.json（本次解析统计）；data/preprocessed/candidate_placements.json（facility_pools 计数）
- pole 命名考古钉死年代：cut 用 'power_pole_001' 顺序命名，而 2026-05-20 快照已改用 'pose_optional::power_pole::<pose_id>'，现源码只在兼容 shim 里认 'power_pole_' 前缀 —— cuts_6x6.json 早于 2026-05-20，且 2026-05-15 的 Phase 3C 文档记载'AI sidecar 集成 DEFERRED — 现 5 cuts（门槛 1000）'：这 5 条 cut 在 2026-05-15 已存在
  - 出处: docs/research/paradigm_search_review_v12_with_code_20260520/shared_infra/src/models/master_model.py:11720；src/models/master_model.py:12038-12046；docs/phase3c_master_ram_findings_20260515.md:26
- coordinate 编码的 master 从未在 prod-scale 出过 FEASIBLE：baseline（workers=8/1800s/默认 profile）14h 跑 51-78 候选 0 FEASIBLE；2026-05-15 Phase 3C 文档明记'master 当前 0 feasible 找到 → solution callback never fires'；coordinate-encoded master 2026-03-16→03-23 就已 stabilization（M5 verdict 里'coordinate_exact_v2 是 Phase 3C 重做的'表述不准——Phase 3C 只是 May 的调参时代，编码本体 3 月已在）
  - 出处: docs/lever_verdicts.md:9；docs/phase3c_master_ram_findings_20260515.md:104；README.md:216
- 仓库里已存在一次同锚受控编码 A/B（B1 Phase 0，2026-05-17）：pose-bool 形式（x_{group,pose} BoolVar + 每格 AddAtMostOne + 逐 pose 供电覆盖 x<=Σcoverers，~284-296K bool）5 个 anchor 全部 49-53s OPTIMAL 或 20.6s 快 INFEASIBLE，同 anchor coordinate 形式（含 coverage）30min UNKNOWN，~34x；end-to-end 时 master 53s OPTIMAL + binding 0s FEASIBLE。核心归因原文：'AddAtMostOne cell exclusivity 让 CP-SAT propagator 直接 fire — 不需要 AddNoOverlap2D (在 dense packing 弱)'
  - 出处: docs/research/b1_pose_bool_phase0_20260517/README.md:15-21,35,37,42-44,156-158
- 编码差异清单：coordinate_exact_v2 每 slot 建 x/y/mode/order_key/signature/family/footprint 起止宽高等 ~14 个 IntVar + x/y interval，靠 AddNoOverlap2D（6×6 时 11596 interval、1,549,300 proto 变量）+ ghost 4225 anchor u_var/AddExactlyOne + 逐 anchor 供电容量/签名桶 tightening pass + witness 式供电编码；pose-bool/旧 z_var 族为 ~30 万 pose 布尔 + 4900 条每格 sum<=1 + pose-cover 供电 + 同款 ghost u_var —— 前者传播/证明强但首解要在 155 万变量上组合出全一致赋值，后者是 set-packing 原生形，首解主力（feasibility_pump/LNS/clause learning）直接可用
  - 出处: src/models/exact_coordinate_master.py:723-754,762,3468,3717-3769；src/models/master_model.py:4679-4687,4762-4767,4881；docs/research/p1_3_m5_convergence_20260708/notes_phase1.md:66,113
- 四层性能税绑在两后端共享的 MasterPlacementModel.solve() 上且全部在 2026-05-20 快照就已存在（forced probing/symmetry>=3、subsolver 过滤=Phase 3C P0 #3 落地于 ~05-15、hint_conflict_limit>=1000）；过滤清单砍掉的是 rins/rens/graph_arc_lns/graph_cst_lns/feasibility_pump/violation_ls = 全部 LNS + 两个首解主力 —— 但 B1 pose-bool 在同税 solve() 下仍 53s OPTIMAL（税对小模型可承受，对 155 万变量 coordinate 模型是黑洞）
  - 出处: src/models/master_model.py:11525-11534,11479-11480；src/models/cp_sat_worker_config.py:184-192；docs/research/paradigm_search_review_v12_with_code_20260520/shared_infra/src/models/master_model.py:11226,11274-11281
- B1 pose-bool 没死在 master 首解，死在下游收敛：master 不知 port 方向 → 任何 OPTIMAL 布局 ~500-600 port front_blocked → nogood 累积 15 iter 不收敛；Phase 6 path-1（port-selection 进 master，333K vars UNKNOWN）与 path-2（lazy demand cut 10 iter 不收敛）双死后 2026-05-18 判'B1 paradigm 全死'——该判决针对的是端到端收敛，不否定其首解能力
  - 出处: docs/lever_verdicts.md:3,467,573-583；docs/research/b1_pose_bool_phase0_20260517/README.md:171-186
- 旧编码今天可跑：PoseBoolExactMasterDelegate 全量存活（build/extract_solution/add_benders_cut/apply_solution_hint 齐），自由锚 ghost 枚举（4225 u_var + AddExactlyOne + 每格 overlap）已按 F-GM-R12-PB-GHOST-01 补全，R11~R14-PB 假-FEASIBLE 缝已修；env 在 master 构造处直接生效（master_model.py:2598-2606），unsafe-env 闸只在 ExactSearchSession.create/create_exact_search_session/run_benders_for_ghost_rect 三处（benders_loop.py:2211,2293,8071），M5 harness 的直连 LBBDController 路径明记'unsafe-map gate is deliberately not on this path'；from_exact_core 对 pose-bool core 有专门 direct-rebuild 分支；现成单锚生产探针 docs/research/b1_pose_bool_phase0_20260517/phase5_production_trial.py 仍在
  - 出处: src/models/pose_bool_exact_master.py:115-215,431-500,1037-1153；src/models/master_model.py:2598-2606,2831-2860；src/search/benders_loop.py:949-960,2211,2293,8071；PROJECT_LOCK.md:344,361,364,370；docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py（run 前注释）
- 反面警示（探针路线选择依据）：master_model.py 里的旧 exploratory z_var build 路径未优化，B1 Phase 2 实测 prod-scale build '>4min 没出'（瓶颈 _populate_cell_occupancy_terms）——测量探针应走 PoseBoolExactMasterDelegate（原型 build 21-25s），不要走 exploratory 模式
  - 出处: docs/research/b1_pose_bool_phase0_20260517/README.md:138-147

## 实验设计

【探针总设计】用仓库现存活体旧编码（PoseBoolExactMasterDelegate，即历史 6×6 候选所属的 pose-indexed set-packing 编码族的硬化版）在 M5 同一战场跑对照。不要用 docs/research/paradigm_search_review_v12_with_code_20260520 旧快照代码——它缺 F-GM-R11~R14-PB 假-FEASIBLE 修复（如"ghost 吃掉全部 pole pose 仍返 OPTIMAL"），旧快照跑出的"首解"可能是假阳性；且快照只有 5 个 model 文件不成树。活体 delegate 走生产 MasterPlacementModel.solve()（同税：forced probing/symmetry>=3、subsolver 过滤、FIXED_SEARCH），编码差异是唯一自变量，正是我们要的。

【前提】本机停机令生效中（硅脂期，verdict 已定"停止新发射"）——本计划待换硅脂后或移生产机执行；master solve 一次一个（串行铁律）；每发前清 __pycache__（缓存鬼 SOP）；w12 + EXACT_SUBPROBLEM_MAX_MEMORY_MB=28000（q3z w24 OOM 教训）。

【探针脚本】新建 docs/research/p1_3_m5_convergence_20260708/probe_pose_bool_cell.py（仿 m5_cell_runner.py，~80 行）。关键机制：EXACT_USE_POSE_BOOL_MASTER=1 必须在 ExactSearchSession.create() 之前就位（core.master_representation 才会是 pose_bool_exact_v1，from_exact_core 才走 master_model.py:2831 的 direct-rebuild 分支；若 env 在 create 之后才设，会得到 coordinate core + pose-bool delegate 的错配态）。而 create 会被 benders_loop.py:2211 的 unsafe-env 闸 raise → 用测量专用 monkeypatch（与 M5 --no-subsolver-filter 同先例，结果 JSON 如实记录，绝非 certified 旋钮）：

```python
import os, sys, json, time, tempfile
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
POSE_BOOL = True          # False = coordinate 对照
ANCHOR = None             # 单锚 cell 设 (32,32)
os.environ["EXACT_CP_SAT_WORKERS"] = "12"
os.environ["EXACT_SUBPROBLEM_MAX_MEMORY_MB"] = "28000"
if POSE_BOOL: os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
if ANCHOR: os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{ANCHOR[0]},{ANCHOR[1]}"
import src.search.benders_loop as bl
bl._collect_forbidden_certified_master_domain_env_overrides = lambda: []  # MEASUREMENT-ONLY
from src.models.cut_manager import CutManager
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession, LBBDController
session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
print("core repr:", session.core.master_representation)  # 断言 pose_bool_exact_v1 / coordinate_exact_v2
master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
print(json.dumps(master.build_stats.get("exact_core_reuse", {}), default=str))
print(json.dumps(master.build_stats.get("ghost_rect", {}), default=str)[:400])
ctl = LBBDController(master=master,
    cut_manager=CutManager(checkpoint_dir=Path(tempfile.mkdtemp(prefix="pb_")), solve_mode="certified_exact"),
    project_root=PROJECT_ROOT, solve_mode="certified_exact",
    master_seconds=1800.0, binding_seconds=600.0, routing_seconds=600.0,
    max_iterations=3, artifact_hashes=session.artifact_hashes)
t0 = time.perf_counter(); status, solution = ctl.run_with_status()
print("STATUS:", status, "wall:", round(time.perf_counter()-t0,1))
# 落盘 JSON：status、master last_solve 遥测(branches/conflicts/dtime)、迭代数、是否进 binding/routing、
# monkeypatch 与 env 全量记录；输出只写 results_scan/ 新 JSON，绝不碰 data/checkpoints、data/solutions
```

【四个 cell（全部串行，nohup/systemd-run 分离进程 + 日志放 ~/m5_runs/）】
1. PB-anchor：POSE_BOOL=True, ANCHOR=(32,32)（内点，仿 B1 (22,28) interior 方法学），master 600s。预计 <15min 出 verdict（B1 同族 49-53s OPTIMAL / 20.6s INFEASIBLE 为参照）。
2. COORD-anchor：POSE_BOOL=False, ANCHOR=(32,32)，600s——把 B1 的"coordinate 单锚 30min UNKNOWN"对照复刻到 6×6。约 12min。
3. PB-free：POSE_BOOL=True, ANCHOR=None（自由锚 4225 anchor 全量，R12-PB 修复后的新代码路径首次实测），1800s。约 35min（build 预计 2-5min：单锚原型 build 21-25s + 4225 u_var×36 格约束）。
4. PB-free-cold（可选）：同 3 + LBBDController(disable_master_warm_start=True)——对照 q5d"hint 拖慢探索"发现。
总机器时 ≈1.5-2.5h，脚本工作量 ≈30-60min。

【判读矩阵（结果 X ⇒ 结论 Y）】
- cell1 快解（分钟级 OPTIMAL/INFEASIBLE）且 cell2 超时 UNKNOWN ⇒ B1 的 34x 编码差在 6×6 战场复现，编码代价假设在单锚维度实锤。
- cell3 在 1800s 内出首个 master 候选（master FEASIBLE/OPTIMAL、或 LBBD 进 binding/routing、或 iteration>=2、或产出 whole-layout nogood）而 coordinate 14 个干净 cell 全 UNKNOWN ⇒ 即父任务判据"旧编码 600s 能解而新编码不能"级别的实锤：coordinate_exact_v2 编码是首解不可达的直接原因；M5 A/B 战场可以在 pose-bool 后端打开（但注意 F 族框架 cut 在 pose-bool 后端 fail-closed，只有 whole-layout nogood 可测）。
- cell1 快解但 cell3 也 UNKNOWN ⇒ 病因改判"自由锚联合选择维度"（anchor×布局联合搜索才是爆炸主源，编码只是放大器）；对策方向变 anchor 分解/枚举（历史 anchor-slicing 线曾被 KILL，需带此新证据重审），而非整体换编码。
- cell1 也超时 ⇒ B1 时代与当前 rules/实例集已漂移或 6×6 单锚本身远难于 27×15，先复刻 B1 原参数（ghost 27×15 anchor (22,28)，phase5_production_trial.py 加同款 monkeypatch）验证探针本身，再回来判。
【产出去向】结论并入 M5 verdict"可行性瓶颈诊断（选项 5）"，与四层税修复线同批呈 owner；若 cell3 开门，M5 A/B 矩阵形态改为 pose-bool 战场评估后再定。

## 风险

- 本机停机令：硅脂期原生层点火不稳（ghost_first/after_counts 档三跑三死、q5a 校验竞态），实验必须等换硅脂或移生产机；即便跑也要 w12+28000MB 帽+每发清 __pycache__+串行一次一个
- pose-bool 自由锚 prod-scale 是 R12-PB 修复后从未实测的新代码路径，可能撞新工程问题（build 慢、fail-closed raise、内存峰值未知）——cell3 失败要先区分'编码解不动'与'探针工程债'（看 build_stats 与崩溃形态）
- 假阳性风险：任何'旧编码赢'的结果必须出自现 tree 的硬化版 delegate；用 2026-05-20 旧快照代码复跑会带着 pre-R11 假-FEASIBLE 缝（如 ghost 吃光 pole pose 仍返 OPTIMAL），赢了也不可信
- 外推限制：cuts_6x6.json 时代的实例集/规则与今不完全同（865 键、旧命名、可能旧 rules 版本），'历史出过候选'不能直接换算成'今日 6×6 同难度'；B1 数据全部单锚 27×15 带，6×6 自由锚是新外推
- 即便编码代价实锤，pose-bool 也不是现成生产出路：certified 路径被 pose_bool_master_not_certified 闸死、B1 端到端死于 routing 收敛（port 方向盲）、F1-F9 框架 cut 翻译在 pose-bool 后端 fail-closed（add_region_capacity_cut 仅 coordinate 实现）——M5 A/B 全矩阵不能原样搬上 pose-bool 战场，诊断结论与生产采纳要分开呈报
- monkeypatch 绕 unsafe-env 闸属测量专用旁路，虽有 --no-subsolver-filter 先例，仍需在结果 JSON 与呈报中如实标注，绝不能流入任何 certified/生产配方；探针输出严禁写 data/checkpoints、data/solutions
- M5 verdict 卡里'coordinate_exact_v2 是 Phase 3C 重做的'表述与考古不符（编码本体 2026-03 已在，Phase 3C 是 May 调参时代），后续引用该卡时需带此修正，避免把'Phase 3C 调参可回退'误解为'编码可轻易回退'