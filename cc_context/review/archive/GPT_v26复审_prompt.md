# 终末地 exact solver — Phase 1.2 spike close gate 复审 (v26)

我有一个项目想请你独立审一个具体的 gate。先把背景和我真正想知道的讲清楚，你别被我带偏，也别因为客气就给我盖章。

## 项目是什么

70×70 网格上 266 个固定设施的 certified-exact 最大空矩形求解器（游戏《明日方舟：终末地》的工业规划器）。目标 `max_lex(area, min_side)`，用 OR-Tools 9.15 CP-SAT + LBBD（Benders）分解。附件 zip 是项目快照（`project/` 是主线代码+数据，`code_context/` 是 review-only 的旁支代码镜像）。

## 我要你审的 gate

项目里有一道工序叫 "prod-scale spike"，目的是在真正动手做下一阶段（P1.3A，真 master 集成 + 多轮 LBBD 收敛）之前，先验证 cut 在生产规模下的 **sizing**（build/translate/solve 耗时、proto 大小、RSS）扛不扛得住。spike 自己的结论是 **GO_WITH_MINOR**，只认 sizing 这一层，把收敛性和对抗鲁棒性 defer 到下一阶段。

这道 gate 已过多轮独立审查。**最近四轮都判了 B**：第九审 catch 4 条 soundness + 1 条 sizing 口径（出 v23）；v23 再审 **B** catch 7 条（出 v24）；v24 再审（两份独立）又 **B** catch 7 条（出 v25）；v25 再审（又两份独立、都 substantive）再 **B**，catch 了 6 条并集，**都是证据精度 / scoping / gate 锁门 / 守卫硬化类，没有 soundness 洞、不改方向**。**v26（本附件）是这 6 条修后的版本。**

这里我要对你完全坦白两件事，因为它们正是本轮最该被你审的：

1. **v23 之后我新加了一个 sizing cheap-gate 脚本来量化 cut body 大小，那个脚本我自己写错过一次——bitset 解码用了 MSB-first，而项目真源是 LSB-first，导致 term 数偏高约 10x，得出过一个"F1/F9 大池子 → 100K 约 1.9GB 会爆"的假数字。** 已在 v24 按 LSB 修正（真实 region 大池子 ~264 term，纠正后 fixture 尺度根本不爆）。
2. **v25 审查方又指出：那个 sizing gate 数的是 facility *type* 级 pose pool overlap（type-pool 总 81,795），但真 pose-bool master 是按 mandatory `(facility_type, operation_type)` *group* 建变量，concrete literal 数约 4× type-pool（~325,747）。** 所以脚本报的 "all-type 上界"数（F9 3341 / F4 5429 / ~16–18K）**不是真-master 的 concrete literal 上界，只是 cheap proxy**。v26 据此把脚本和结论改成同时报 type-pool 与 group-expanded concrete，并把 P1.3A 的 cap 输入收紧成"真 translator group/template/optional 展开后的 concrete literal vector 长度"。

我把这两件写出来，是要你**别因为我"诚实地修了自己的问题"就放松**——请你独立验证修正后的数字、机制、结论本身对不对。

包里 README + verdict.md 记录了每轮 catch 了什么、改了什么。**你不用、也别假设你看过前面任何一轮——就当第一次看，独立判断现在 v26 的状态。** 前几轮 finding/修复都在 git 历史和 README 里，是给你 source-check 的事实素材，不是要你接谁的话往下说。

我想知道的就一件事：**以 v26 现在的状态，这道 spike close gate 还有没有未闭的 soundness / 完整性 / scoping finding？** 两个具体角度都欢迎挑战：(a) 下面「v25 → v26 修了哪 6 条」是不是**真修对了、修到位了**；(b) 修正后的 sizing 结论（compact lowering 全族便宜；expanded lowering 预算 = **concrete literal 数（group 展开后，不是 type-pool）** × per-term 字节（按约束类型：linear ~4B / BoolOr no-good ~10–11B），cap 按 max/p99、跨**所有**族）是 sound 的，还是仍有藏雷。

### v25 → v26 修了哪 6 条（本轮重点，两份独立审查并集，给你核不是要你认）

- **A-F1（最重）concrete literal vs type-pool**：sizing gate 之前只报 type-pool overlap。v26 加 group 乘数（从 `data/preprocessed/mandatory_exact_instances.json`：266 instance → 19 group，mfg_3x3=8 / mfg_5x5=4 / mfg_6x4=5 / protocol_core=1 / boundary_storage_port=1），多报一列 `exp_group_all` + concrete proxy 总数 325,747；F9 single-group 784 → group 展开 11,644，F4 5429 → 20,157。结论改成：**all-type UB 是 type-pool proxy，不是真-master literal 上界；P1.3A cap 输入 = `len(final_concrete_literals)`（group/template/optional 展开后）**。
- **A-F2 F9 window_rect 读序**：真 schema 是 `[x,y,h,w]`，脚本原读成 `[x,y,w,h]`（现 fixture 全 10×10 方形故数字不变，非方形会错）。已修正。
- **A-F3 mirror runner 可复现**：review 镜像 `code_context/spike/spike_prod_scale_runner.py` 原 import `scripts.spike_prod_scale_lib`，从镜像位置跑不了。加了 namespace-package shim（production import 优先，仅 mirror 布局 fallback），覆盖全部 import 站点。
- **B-F1 summary 表锁门**：sizing gate 的 family summary 行原把 F9 `density_envelope` expanded 显示成 compact witness `4.0`（因 `cut_cells()` 对 F9 返回空 → fallback），与详细 F9 表（784/3341）自相矛盾。v26 让 summary 承载真实 window→pose overlap（用正确 `[x,y,h,w]`）。
- **B-F2 OR-Tools 实测可复现**：bytes/term 原只 hardcode 4/11。v26 加可选 OR-Tools 实测段（OR-Tools 可 import 时实测 81,795 var 高 index tail：linear ~4.03 / BoolOr ~10.01）。**实现注意**：9.15.6755 的 `model.Proto()` 返回的 `CpModelProto` pybind **没有** `ByteSize`/`SerializeToString`，所以用 `model.ExportToFile(.pb)` 量字节（直接调 `.ByteSize()` 会 AttributeError）；无 OR-Tools 时 fail-soft 跳过。
- **B-F3 F7/F8 duplicate pose_id 守卫硬化**：`_validate_facility_cells_match_pose_registry` 原"找到第一个 pose_id match 就比 cells 并 return"，对 registry 里 duplicate pose_id 不 fail-closed。当前 `candidate_placements.json` 无 duplicate（故非现有 false-positive cut 漏洞），但"绑回真 registry"应含唯一性。v26 改成 collect matches + 要求 `len(matches)==1` 否则 unsound + 2 个回归测试（cuts 414 → **416**）。

### 纠正后的 sizing 结论（请重点审这个对不对）

(a) 全 9 族 compact (witness/no-good) lowering → 100K 便宜（~1–4 MB，**任何**约束类型）；(b) expanded (full pose-overlap) lowering 的 100K proto 预算 = **(per-cut concrete literal 数，= 真 translator group/template/optional 展开后的 vector 长度，不是 type-pool 数) × (per-term 字节，按约束类型：linear ~4B / BoolOr no-good ~11B)**。type-pool 数（F9 single-group 784 / region LSB ~264）是真实的单 group / region 尺度信号；但 all-type UB（F9 3341 / F4 5429 / ~16–18K）是 type-pool proxy，group 展开后约 4×（F9 11,644 / F4 20,157 / 满 mfg 池 ~295,700）。→ P1.3A lowering 设计硬约束 = 对**任何**族的 geometric/expanded lowering，**在 concrete literal vector 上**、**按约束类型分别**设 per-cut term cap + cumulative proto budget（cap 按 max/p99 非 family-avg），超 cap 就 compact fallback/reject/defer；compact lowering 全族安全。证据脚本 `project/docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`（v5），在 `project/` 根下可直接跑复现（输出 concrete 325747 / F9 784 与 group 11644 / OR-Tools 实测 4.03·10.01 / 全 6 条 F9）。

## 真正的瓶颈（免得你往错方向使劲）

项目的根本难点不是这个 spike，是：master CP-SAT 在 prod 规模 single-solve 解不动——latency-bound 工作负载（~280K pose registry，two-watched-literal 随机指针追逐，working set 溢出 L3）。试过 27 条求解 paradigm，绝大多数 NOT_GO，死因分类在 `project/docs/项目说明/03_paradigm_death_baseline.md` 和 `project/docs/research/`。当前主线是 cut-family LBBD：9 个 cut family（F1–F9）当 Benders cut 喂回 master。这个 spike 在验这些 cut 的工程可行性。

## 已经死掉的方向（别重新推荐）

除非你能指出之前 NOT_GO 论证里有**具体技术漏洞**（见最后一节形式化要求），否则别 resurrect：

- 单机扩 RAM：augmented master / GOC / PGW 全在 25–32 GB 上界，机器 48 GB，撑不住。
- 重写求解器：HiGHS 等 LP-MIP 对 dense linear constraint 不适合（实测 42 GB > 现 OR-Tools 30 GB）。
- 让 pose-bool master 自己持有 port direction / pole selection / belt routing：6 条 paradigm 撞同一面墙（master 表达力 fundamental 不够），全死。

## 重点看这几层（不限于此）

1. **concrete-literal vs type-pool 对不对（最高价值）**：自己读 `mandatory_exact_instances.json` 核 group 乘数（mfg_3x3=8 等），读真 master 建 pose 变量的代码（`project/src/models/exact_coordinate_master.py` / `master_model.py`）确认它确实按 `(facility_type, operation_type)` group×pose 建 var（不是按 type）——从而判断 sizing gate 的 group-expanded 数（325747 / F9 11644 / F4 20157）是不是对的 cap 输入，type-pool UB 当真-master 上界是不是确实低估。**在 `project/` 根下跑 `python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`**。
2. **bitset 修复仍对**：按 LSB（`1<<(idx%8)`，idx=x*70+y）重算 `region_capacity` 那条 cert 的 overlap（region 大池子 ~264，不是 2026），确认脚本没别的 endian/index 错。
3. **假证据 / fail-closed**：`toy_translator` malformed（坏 base64/非 dict root/缺字段）是否真 fail-closed（F3 已 `validate=True` + 12 case，只 F3——非 F3 是 synthetic fallback，已在文案承认）。A3 "0 unsound" 立不立得住。
4. **主线 src soundness 守卫**：F7/F8 `_validate_facility_cells_match_pose_registry` 是否真把 `facility_cells` 绑回真实 pose registry（伪造坐标 / duplicate pose_id 能不能骗过 → false-positive cut → 破坏 FP=0）。v26 刚加了 duplicate pose_id 唯一性守卫，你独立判它够不够、有没有 over-restrict。
5. **完整性 + scope 诚实度**：剩余 sizing 项真覆盖了吗？remap_audit 暴露 36/50 让"100K applied=100%"不再误导，够不够？跨文档（sizing_gate / RESULTS / verdict / README）的数字一致吗、有没有残留废数字（1.9GB / 2026 / "只 F1/F9"）？还有没有同类被偷偷豁免的？

## 我面前的选择

spike close 之后下一步是 P1.3A 主体。我卡在：能不能拿现在 v26 的状态当进入 P1.3A 的依据。

- A：v25→v26 的 6 条 patch 真闭 + 纠正后的 sizing 结论（concrete-literal cap、按约束类型分预算、cap 按 max/p99、跨全族）sound，spike close 成立，进 P1.3A。
- B：还有没修对 / 没修到位 / 新的未闭 finding（请指出 + 反例），再修。
- C：纠正后的 scope/framing 仍划错（比如 concrete-literal 的 group 展开口径不对、或 Finding5#2 标 PARTIAL 还不够/过头）。

我不预设你选哪个。

## 硬性输出约束（两条）

1. **不可达断言要形式化**：任何 "X 不可达 / 必然失败 / 这道 gate 该 NOT_GO 因为 P1.3A 根本走不通" 的断言，请**形式化**：给 complexity reduction、proof-system lower bound、resource inequality，或 cite 文献。不接受 "我觉得 / 直觉 / 大概率"。
2. **给出补丁，并把文档和补丁打成压缩包**：不只指出问题，还要给出能直接落地的**具体补丁**（哪个文件、改成什么，最好是可直接 apply 的 diff 或替换用的代码/文案片段，可标把握度）。补丁跟 finding **不必一一对应**——一个补丁可以覆盖多条 finding，怎么组织你定。**最后请把你的说明文档和这些补丁以压缩包（zip）的形式给出**，方便我直接下载落地。

除此之外 finding 怎么报、报几条、格式你自便。

## 包里怎么核 / 怎么复现

> 解包后得到 `_phase1_2_pkg_v26/` 目录，主线代码在它下面的 `project/`，以下路径相对 `_phase1_2_pkg_v26/`。

- sizing cheap gate（本轮重点，v5 = LSB + bytes/term-by-kind + 全 6 F9 + **concrete/group-expanded** + **OR-Tools ExportToFile 实测**，**包内可直接跑**）：`project/docs/research/p1_2_spike_sizing_gate_20260601/`（`sizing_gate.py` + `RESULTS.md`）
- spike 自我结论 + G 标准表 + Layer-2 defer + 历轮修正节（含 v25 外审 concrete-literal 段）：`project/docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- remap 审计：`project/data/cuts/spike/remap_audit.json`
- spike 实现代码镜像（review-only，**不是** master 合并目标）：`project/code_context/spike/`（含 `toy_translator.py` / `scale_ramp.py` / `spike_prod_scale_runner.py`（含 mirror import shim）+ 12-case 自测）
- 主线 soundness 守卫：`project/src/cuts/families/power_hitting_set.py` 和 `power_grid_reach.py` 的 `_validate_facility_cells_match_pose_registry`（含 v26 新 duplicate pose_id 守卫）；真 bitset 编码：`project/src/cuts/oracles/region_capacity_oracle.py`；真 master 建 var：`project/src/models/exact_coordinate_master.py`
- 回归测试：`project/src/tests/cuts/`；跑：`cd project && python -m pytest src/tests/cuts/ -q`（实测 **416 passed**，含 2 个新 duplicate-pose_id 测试）

## 包 sha256（核对上传完整）

- `phase1_2_spike_review_v26.zip`：`fb69415272d8a7759c76d8283b0fab6da8dc4fce1f63a956ea81c7d0a296e00f`

（依赖 wheel 分 3 块单独上传：`deps_part1.zip` / `deps_part2.zip` / `deps_part3.zip`；按顺序 `cat deps_part1.zip deps_part2.zip deps_part3.zip > deps_linux_py313.zip` 合并后再离线 `pip install --no-index --find-links` 装，详见包内 README "怎么跑"节。）
