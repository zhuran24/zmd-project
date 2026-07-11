# 诊断侦察·replay_verdict（Fable，2026-07-09）

## Headline

历史候选回放假设被证据否定后反转：cuts_6x6.json 只能按已 superseded 的 53MB 旧工件解码、且记录的是缩减问题（72 台机器+599 电线杆，非当前 266 实例），而原机 24h campaign 对完整模型同样零候选——「当前模型过约束（历史可行解不再可行）」失去全部证据基础，「完整 266 实例 master 从未在任何机器出过首解」成为新基线；真正可执行的回放实验是对已在手的 3 份当前编码几何零冲突重建布局做强制验证（presolve-off + assumption core，≤90min 出 FEASIBLE=战场开 / INFEASIBLE=约束族点名的判决）。

## 硬事实

- cuts_6x6.json 每条 conflict_set 是 865 个键（266 mandatory 实例 + 599 个 power_pole_001..599），不是文档说的 266；5 条 cut 两两只差 1-4 个 power_pole_598/599 条目
  - 出处: data/solutions/cuts_6x6.json（脚本实测；mandatory id 集合与 data/preprocessed/mandatory_exact_instances.json 266 条完全相等）
- cut 内 132 个 manufacturing_3x3 实例只映射到 34 个唯一 pose_idx（最多 8 个不同 family 实例共用同一 idx，如 678）；5x5 49→21、6x4 38→17；每个 family 的值列表是同一按类型排序序列的前缀；34/21/17 恰为各类型最大 family 尺寸
  - 出处: data/solutions/cuts_6x6.json cut0 实测（crusher_blue_iron=[678,698,...,2426] 与 refinery_blue_iron 完全相同等）
- 当前模型 pose_idx 语义 = candidate_placements.json facility_pools[类型] 列表的枚举下标（一类型一共享池），同类型两实例同 idx 物理上同格必重叠
  - 出处: src/models/exact_coordinate_master.py:1705-1719（for pose_idx, pose in enumerate(pool)）
- 按当前工件（45,774,305B/a914ba63）解码 5 条 cut：每条 2278 个占用格冲突；按拐角修复前 boundary 位移假设（旧 idx 0-66→+1、67-133→+2）解码：2276 个冲突——两种现存编码下都是几何乱码
  - 出处: 离线重建脚本 /tmp/claude-1000/.../scratchpad/replay_geometry.py 输出；拐角双 pose 插入位置=当前池 idx 0 与 68（(0,0) left_base/bottom_base）
- 在 /mnt/winc/claude pj/zmd/data/preprocessed/candidate_placements.json 找到 superseded 旧工件实物：53,594,995 字节、SHA256 d5e3911fc1bc...（与 README 记载的 fail-closed 拒绝对象一致）；其池规模 3x3=17952/5x5=16896/6x4=16900/core=7200/box=17952/pole=4761/boundary=134
  - 出处: sha256sum 实测 + README.md:179
- 按 53MB 旧工件解码 5 条 cut：唯一 pose 集合 0 重叠，占用恰 3854 格 = 34×9+21×25+17×24+46×3+599×4+81，且每张图恰有 1-2 个 6×6 空矩形（锚点 (64,63)/(64,64)）——cuts 的编码属旧工件，且记录内容是缩减问题（72 台机器而非 219 台）
  - 出处: 离线解码实测；占用恒等式逐项核对（旧/新工件 footprint 相同：pole 2x2、boundary 3 格、core 81 格）
- 完整 266 mandatory（3544 格）+ 599 个互不重叠 2x2 电线杆（2396 格）= 5940 > 4900 棋盘总格——cuts_6x6.json 数学上不可能是完整 266 实例问题的一张图
  - 出处: 占用不变量 3544（m5_phase1_verdict.md 结构性背景 + 当前工件 footprint 实测求和=3544）
- legacy 实例宇宙只有 50 个 power_pole 可选实例（exploratory cap），cuts 里 599 个 pole id 超出该宇宙 → cuts 产自更早的 Codex 时代代码（≤2026-05-06，随 'migrate from Codex workspace' 初始提交进库）
  - 出处: /mnt/winc/claude pj/zmd/data/preprocessed/all_facility_instances.json（Counter: power_pole 50）+ 该仓 git log 初始提交 270bb2d 2026-05-06
- 原机 24h certified campaign（2026-05-06→07，266 mandatory + d5e3911f 工件）：final_status UNKNOWN、campaign_time_budget_exhausted、全部 15 个候选 ghost 零 exact_safe cut、benders_cuts.jsonl 0 行——原机也从未对完整模型产出过 master 首解
  - 出处: /mnt/winc/claude pj/zmd/data/checkpoints/exact_campaign_state.json + benders_cuts.jsonl（wc -l = 0）
- cuts_6x6.json 无 soundness 暴露：无 source_mode/exact_safe 字段 → from_dict 默认 exploratory/False，certified 回放门槛硬拦（cut_not_exact_safe/cut_mode_pollution）；且运行时 cut 持久化路径是 checkpoints/benders_cuts.jsonl，src/ 无任何代码读 data/solutions/cuts_*.json；另外当前坐标 master 对同 (group,pose_idx) 重复的 persisted cut 直接 fail-closed 拒绝表示
  - 出处: src/search/benders_loop.py:2103-2118；src/models/cut_manager.py:410；src/models/exact_coordinate_master.py:7022-7061
- 现成的当前编码回放对象已存在：hint_anchor{132,133,134}.json（各 266 实例），离线几何验证 3/3：0 重叠、占用恰 3544、自由格 1356、各含 688-718 个 6×6 空洞位置
  - 出处: <external-m5-runs>/rebuilt_hints/ + 本次离线重建实测；产出脚本 docs/research/p1_3_m5_convergence_20260708/linux_tools/extract_rebuilt_hints.py
- _validate_coordinate_forced_hint 支持程序化 solver_parameter_profile（cp_model_presolve 开关、probing/symmetry level、branching、workers、random_seed）与 use_assumptions=True 提取 infeasible assumption core——生产 ghost-aware 调用传空 profile + 2s 默认（这是此前 32 个假阴性 UNKNOWN 的根因），但探针直调可完全绕开该限制
  - 出处: src/models/master_model.py:1665-1718（profile 应用）、7933-7944（签名）、8477-8495（core 提取）、92-94（2.0s 默认）、10788-10792（生产调用点空 profile）

## 实验设计

## 前提（已由本次只读侦察完成，无需重跑）
- cuts_6x6.json 直接回放已判死刑：它的 pose_idx 只能按 superseded 53MB 工件（d5e3911f，在 /mnt/winc/claude pj/zmd/data/preprocessed/candidate_placements.json 找到实物并验过 hash）解码，且解码后是一个「34+21+17 台机器 + 46 港口 + 核心 + 599 电线杆」的缩减问题布局（占 3854 格、ghost 在 (64,63)/(64,64)），不是当前 266 实例问题的解——完整 266 mandatory(3544 格)+599 个不重叠 2x2 电线杆(2396 格)=5940 > 4900 格，数学上不可能同为一张图。按当前工件解码则 2278 个格重叠 = 乱码。结论：**「历史 master 出过 6×6 候选」不构成当前模型曾有首解的证据**，5/5 INFEASIBLE 的原设判读标准作废（那只会是编码不兼容的假阳性）。
- 真正可回放的对象已在手：<external-m5-runs>/rebuilt_hints/hint_anchor{132,133,134}.json（07-09 由 linux_tools/extract_rebuilt_hints.py 产出，当前编码、266 实例、离线几何验证 0 重叠、占用恰 3544、各含 ~700 个 6×6 空洞）。

## Phase A：重建布局强制验证（主实验，换硅脂后跑，预计 ≤90min 上限、乐观情形分钟级）
写入 docs/research/p1_3_m5_convergence_20260708/probes/m6_replay_forced_validation.py：

```python
import json, os, sys, time
sys.path.insert(0, "<repo-root>")
os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
os.environ["EXACT_CP_SAT_WORKERS"] = "1"
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession

session = ExactSearchSession.create("<repo-root>", solve_mode="certified_exact")
master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(6, 6))
if not getattr(master, "_built", False):
    master.build()

PROFILES = [
    {"profile_id": "replay_presolve_off_fixed", "cp_model_presolve": 0,
     "search_branching": "fixed", "worker_count": 1},          # 主判据 cell：全钉死模型靠纯传播出结论
    {"profile_id": "replay_diet", "cp_model_probing_level": 1, "symmetry_level": 1,
     "search_branching": "fixed", "worker_count": 1},          # 对照 cell
]
for anchor in (132, 133, 134):
    hint = json.load(open(f"<external-m5-runs>/rebuilt_hints/hint_anchor{anchor}.json"))
    for prof in PROFILES:
        t0 = time.perf_counter()
        res = master._validate_coordinate_forced_hint(
            solution_hint=hint, ghost_anchor_hint_idx=anchor,
            time_limit_seconds=900.0, require_complete=True,
            solver_parameter_profile=prof, force_fields=("x", "y", "mode"))
        print(json.dumps({"anchor": anchor, "profile": prof["profile_id"],
            "status": res.get("status"), "accepted": res.get("accepted"),
            "reason": res.get("reason"), "attempted_solver": res.get("attempted_solver"),
            "branches": res.get("branches"), "conflicts": res.get("conflicts"),
            "wall": round(time.perf_counter()-t0,1), "dtime": res.get("deterministic_time"),
            "response_stats": res.get("response_stats", "")[:2000]}, ensure_ascii=False), flush=True)
        if res.get("status") == "INFEASIBLE" and res.get("attempted_solver"):
            core = master._validate_coordinate_forced_hint(
                solution_hint=hint, ghost_anchor_hint_idx=anchor,
                time_limit_seconds=900.0, require_complete=True,
                solver_parameter_profile=prof, force_fields=("x","y","mode"),
                use_assumptions=True)   # 拿 SufficientAssumptionsForInfeasibility core
            print(json.dumps({"anchor": anchor, "core_status": core.get("infeasible_assumption_core_status"),
                "core": core.get("infeasible_assumption_core", [])[:50]}, ensure_ascii=False), flush=True)
```

跑法：`cd <repo-root> && nohup python3 docs/research/p1_3_m5_convergence_20260708/probes/m6_replay_forced_validation.py > docs/research/p1_3_m5_convergence_20260708/results_scan/m6_replay.log 2>&1 &`；prod-scale 一次只跑这一个（串行铁律）。耗时估算：session+build 数分钟（Windows 侧同路径 warm-start 全程 423s 含 161 次重建，纯 build 更短）；presolve-off cell 若「全钉死→传播毫秒级」成立则秒级出判决，否则 fixed search 在 900s 内跑剩余 pole/witness 空间；上限 3 anchors × 2 profiles × 900s = 90min。

## 判读标准
1. **任一 anchor FEASIBLE** ⇒ 首解直接到手、战场开：该 hint 即「已验证 master-可行」的完整布局，可作 incumbent/warm-start（EXACT_COMMUNITY_BLUEPRINT_HINT_PATH 或直接续接 benders 链），M5 A/B 立即解锁；同时否定「当前模型对 6×6 过约束到不可行」。
2. **3/3 INFEASIBLE（attempted_solver=true）** ⇒ 不是历史回放意义的过约束实锤（greedy 布局本来就不保证供电/端口约束），但 assumption core labels 直接点名杀手约束族（供电 witness / 端口计数 / 其它）⇒ 病因定位成功，下一步对该族做人工松紧审计（对照 rules/canonical_rules.json 与 PROJECT_LOCK §1A 语义）+ 修 greedy 重建器让它产可行布局。
3. **precheck 直接 INFEASIBLE（attempted_solver=false）** ⇒ reason 字段（same_x_strip_fixed_ghost_capacity_conflict / ghost_overlap_forced_domain_infeasible）即零成本病因判决。
4. **presolve-off 下仍 UNKNOWN** ⇒ 全钉死模型连传播都跑不完 = 编码病理红旗（比过约束更严重的 efficiency 议题），用落盘的 response_stats 定位烧在哪个 propagator，升级为独立课题。

## Phase B：叙事修正（纯文档，无 solve，可立即做）
m5_phase1_verdict.md「历史战场证据」段与 memory 卡 p1-3-m5-phase1-verdict 中「historical 6×6 候选」表述需要修正：cuts_6x6.json 记录的是缩减问题（72 机器+599 杆、53MB 工件时代、2026-05-06 前的 Codex 时代产物）；且原机 24h certified campaign（05-06→07，266 实例、d5e3911f 工件）final_status UNKNOWN、零 cut、benders_cuts.jsonl 空——**没有任何机器曾对完整 266 实例模型产出过 master 首解**，首解难是问题本征而非本机/OS 特有。可选考古：用 legacy 工件把 5 条 cut 解码成物理坐标 JSON 存 scratchpad 留档（只读挂载源，绝不把 53MB 工件拷入 zmd-pj/data/preprocessed/）。

## 风险

- 本机硅脂期不稳：Phase A 是真 CP-SAT solve（prod-scale build + 传播），必须等换硅脂/压核后单发串行跑，不能与任何 master solve 并发（47.7GB 双杀教训）
- hint_anchor{N}.json 的 N 是 build 时 _ghost_domains 的 rect_idx：若此后 pools/rules/枚举有任何 reseal 变更，anchor idx 语义会漂移，需先重跑 extract_rebuilt_hints.py（build-only 无 solve）再验证
- _validate_coordinate_forced_hint 是私有诊断 API：FEASIBLE 结果只能当 warm-start/战场开门用，不具证明力，不得写成任何 certified 断言（三权分立与 P1.2 纪律不变）
- 若不落地 Phase B 的叙事修正，m5_phase1_verdict.md 与 memory 卡「历史出过 6×6 候选」的错误前提会继续污染后续决策（例如误判 6×6 是『历史战场』而优先攻坚该尺寸——实际上历史 6×6 证据属于另一个更小的问题）
- 53MB 旧工件是 fail-closed 拒绝对象：考古解码只能在 scratchpad 做，绝不能拷入 zmd-pj/data/preprocessed/（artifact_hash_mismatch 是刻意设计，别『好心』复活旧工件）
- presolve-off 下若剩余 pole/witness 搜索空间本身就是难点，900s fixed search 可能仍 UNKNOWN——此时结论是『病灶在 pole 覆盖子空间』而非无信息，需把 response_stats 落盘后再判，不要直接加预算重试
- use_assumptions=True 的强制是假设文字面而非硬等式，显著慢于硬钉死——只用于 INFEASIBLE 后的 core 复核步，别用它跑首轮
- 结论依赖 /mnt/winc NTFS 挂载在位（legacy 工件与 checkpoint 证据都在那边）；跨系统接续前留意两侧 git log 谁新用谁的既有纪律