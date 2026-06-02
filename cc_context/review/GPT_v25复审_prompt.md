# 终末地 exact solver — Phase 1.2 spike close gate 复审 (v25)

我有一个项目想请你独立审一个具体的 gate。先把背景和我真正想知道的讲清楚，你别被我带偏，也别因为客气就给我盖章。

## 项目是什么

70×70 网格上 266 个固定设施的 certified-exact 最大空矩形求解器（游戏《明日方舟：终末地》的工业规划器）。目标 `max_lex(area, min_side)`，用 OR-Tools 9.15 CP-SAT + LBBD（Benders）分解。附件 zip 是项目快照（`project/` 是主线代码+数据，`code_context/` 是 review-only 的旁支代码镜像）。

## 我要你审的 gate

项目里有一道工序叫 "prod-scale spike"，目的是在真正动手做下一阶段（P1.3A，真 master 集成 + 多轮 LBBD 收敛）之前，先验证 cut 在生产规模下的 **sizing**（build/translate/solve 耗时、proto 大小、RSS）扛不扛得住。spike 自己的结论是 **GO_WITH_MINOR**，只认 sizing 这一层，把收敛性和对抗鲁棒性 defer 到下一阶段。

这道 gate 已过多轮独立审查。**最近三轮都判了 B**：第九审 catch 4 条 soundness + 1 条 sizing 口径（出了 v23）；v23 再送审判 **B** catch 7 条（出了 v24）；v24 再送审（这次两份独立审查都 substantive、结论一致）又判 **B**，catch 了 7 条，**都是证据精度 / 工件可复现 / gate 锁门类，没有 soundness 洞、不改方向**。**v25（本附件）是这 7 条修后的版本。**

这里我要对你完全坦白一件事，因为它正是本轮最该被你审的：**v23 之后我新加了一个 sizing cheap-gate 脚本来量化 cut body 大小，那个脚本我自己写错了——bitset 解码用了 MSB-first，而项目真源是 LSB-first，导致 term 数偏高约 10x，并据此得出一个"F1/F9 大池子 → 100K 约 1.9GB 会爆"的结论。那个数字是假的。** v23 审查方独立按 LSB 重算 catch 了它，我对真源码核实属实、修正了（真实 region 大池子是 ~264 term 不是 2026，纠正后 fixture 尺度根本不爆）。我把这个写出来，是要你**别因为我"诚实地修了自己的 bug"就放松**——请你独立验证修正后的数字和结论本身对不对。

包里 README + verdict.md 记录了每轮 catch 了什么、改了什么。**你不用、也别假设你看过前面任何一轮——就当第一次看，独立判断现在 v25 的状态。** 前几轮 finding/修复都在 git 历史和 README 里，是给你 source-check 的事实素材，不是要你接谁的话往下说。

我想知道的就一件事：**以 v25 现在的状态，这道 spike close gate 还有没有未闭的 soundness / 完整性 / scoping finding？** 两个具体角度都欢迎挑战：(a) 下面「v24 → v25 修了哪 7 条」是不是**真修对了、修到位了**；(b) 修正后的 sizing 结论（compact lowering 全族便宜；expanded lowering 预算 = term × per-term字节，**按约束类型分**（linear ~4B / BoolOr no-good ~10–11B），cap 按 max/p99、跨**所有**族）是 sound 的，还是仍有藏雷。下面同时保留 v23→v24 的 7 条（历史），但本轮重点是 v24→v25。

### v23 → v24 修了哪 7 条（给你核，不是要你认）

- **F1 可复现**：sizing gate 脚本原来硬编码读一个不在包里的外部 v22 zip 取 fixture → 包内审者跑不了。改成读包内 `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` + `data/preprocessed/candidate_placements.json`。
- **F2 bitset 字节序（最重，就是上面说的我的 bug）**：MSB-first → LSB-first，与真源 `src/cuts/oracles/region_capacity_oracle.py` 的 `_encode_region_bitset`（`arr[idx//8] |= 1<<(idx%8)`）一致。
- **F3 scope 过窄**：原说"只 F1/F9 会爆、其余 7 族任意 lower 都安全"不成立——blow-up 是 region-size×pool 的函数、跨所有族。改成：compact (witness/no-good) lowering 全 9 族安全；任何族走 expanded (全 pose-overlap) lowering 才需设 per-cut term cap。
- **F4 F9 没真测**：sizing gate 原对 `density_envelope` 退回 compact witness 计数（4），没测 window→pose overlap。补了真实计数（10×10 window 大池子 ~360–524 term）。
- **F5 remap telemetry 没进 artifact**：translator 早有 unknown-pose remap 计数字段，但 ramp artifact 没写出。补：`scale_ramp` jsonl 加 `n_pairs_remapped`/`true_registry_bound`，新增 `data/cuts/spike/remap_audit.json`（50 cert 150 pair 中 **36 个 unknown-remapped**，density 24 + port 12）→ 让 "B2 cut_count_applied=100%" 不再静默掩盖"literal 没绑真 registry"。
- **F6 verdict writer 没锁**：`spike_prod_scale_runner.py` 的 G10 原硬编码 PASS、Finding5#2 模板原写 YES（只手改的 verdict.md 是 PARTIAL）→ 重跑会回归。改成 G10 从 A3 fixture 真算（≥45 / 0 unsound / 0 schema_err / ≥9 family），模板写 PARTIAL。
- **F7 malformed scope**：文案明确 toy_translator 只有 F3 `port_exposure` malformed fail-closed，非 F3 仍走 synthetic fallback——不泛化成"全局 fail-closed"。

### v24 → v25 修了哪 7 条（本轮重点，给你核）

- **P1 proto bytes/term 按约束类型分**：v24 把 100K proto 估成 `term × 4–6 B`，但这只对 linear constraint 成立。实测 OR-Tools 9.15：`AddBoolOr` no-good ~**10–11 B/term**（linear ~3–4）。v25 把投影按约束类型分开（linear ~4 / BoolOr ~11），结论也据此重写。
- **P2 F9 补测跑全 6 条**：v24 的 sizing gate 只打印前 2 条 `density_envelope`（`[:2]`）。v25 删掉 `[:2]`，跑全 6 条：scoped(manufacturing) **max 784**（不是 v24 写的 360–524），all-type 上界 **max 3341**。
- **P3 remap 字段精确化**：v24 README 说"scale_ramp jsonl 加了 remap 字段"，但包内 checked-in `scale_ramp_results.jsonl` 其实没有（代码加了、历史 artifact 没重跑）。v25 文案改成实情：字段在 `scale_ramp.py` 代码 + 独立 `remap_audit.json`（36/50 unknown）承载，历史 ramp jsonl 未重跑不带。
- **P4 G10 reader 硬化**：`_read_a3_fixture_stats` 原来坏 JSON 行 `continue`（不计）、缺 `validator_kind` 默认当 ok（fail-open）。v25 改成坏 JSON / 缺字段都计 `schema_err`、只精确 `"ok"` 才过。
- **P5 A3 emitter 自身锁 family**：`oracle_emit_fixture.run_emit()` 的 pass 原只查 total/unsound/schema_err，没查 family≥9（只 runner 查）。v25 在源头也加 `family≥9`。
- **P6 verdict writer 锁**：writer 的 Finding5#2 模板引用了 "Layer-2 risk #6" 但 risk list 只 emit 1–5（dangling）。v25 把 risk #6 纳入 writer；并在 verdict 顶部加 banner 说明"第九审/v23/v24/v25 修正段是 post-run 手写 addenda，writer 不生成、重跑会覆盖"。
- **P7 框架措辞**：term cap 按 **max/p99** 不按 family-avg；`0.1–0.3GB` 改成按约束类型条件化。

### 纠正后的 sizing 结论（请重点审这个对不对）

(a) 全 9 族 compact (witness/no-good) lowering → 100K 便宜（~1–4 MB，**任何**约束类型）；(b) expanded (full pose-overlap) lowering 的 100K proto 预算 = **(per-cut term，随 region/window × pool-density 变) × (per-term 字节，按约束类型：linear ~4B / BoolOr no-good ~11B)**：fixture F1/F9 scoped **max 784** term/cut → 走 linear ~0.3 GB / 走 **BoolOr ~0.86 GB**；routing / all-type UB（F4 5429 / F9 3341 term/cut）走 BoolOr **~3.7–6 GB**；大 region/window 趋近全 pool（~16–18K term）任何类型都数 GB。→ P1.3A lowering 设计硬约束 = 对**任何**族的 geometric/expanded lowering，**按约束类型分别**设 per-cut term cap + cumulative proto budget（cap 按 max/p99 非 family-avg），超 cap 就 compact fallback/reject/defer；compact lowering 全族安全。证据脚本 `project/docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`（v3），在 `project/` 根下可直接跑复现（输出 784 / BoolOr 11 / 全 6 条 F9）。

## 真正的瓶颈（免得你往错方向使劲）

项目的根本难点不是这个 spike，是：master CP-SAT 在 prod 规模 single-solve 解不动——latency-bound 工作负载（~280K pose registry，two-watched-literal 随机指针追逐，working set 溢出 L3）。试过 27 条求解 paradigm，绝大多数 NOT_GO，死因分类在 `project/docs/项目说明/03_paradigm_death_baseline.md` 和 `project/docs/research/`。当前主线是 cut-family LBBD：9 个 cut family（F1–F9）当 Benders cut 喂回 master。这个 spike 在验这些 cut 的工程可行性。

## 已经死掉的方向（别重新推荐）

除非你能指出之前 NOT_GO 论证里有**具体技术漏洞**（见最后一节形式化要求），否则别 resurrect：

- 单机扩 RAM：augmented master / GOC / PGW 全在 25–32 GB 上界，机器 48 GB，撑不住。
- 重写求解器：HiGHS 等 LP-MIP 对 dense linear constraint 不适合（实测 42 GB > 现 OR-Tools 30 GB）。
- 让 pose-bool master 自己持有 port direction / pole selection / belt routing：6 条 paradigm 撞同一面墙（master 表达力 fundamental 不够），全死。

## 重点看这几层（不限于此）

1. **我的 bitset 修复对不对（最高价值）**：自己按 LSB（`1<<(idx%8)`，idx=x*70+y）重算 `region_capacity` 那条 cert 的 region→各设施 pose overlap，核对 sizing gate v2 报的数（region 大池子 manufacturing ~264）。再确认整个脚本不再有别的 endian/index 错。**直接在 `project/` 根下跑 `python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`**，看输出是不是 LSB 数（含 264、不含 2026）。
2. **假证据 / fail-closed**：`toy_translator` malformed（坏 base64/非 dict root/缺字段）是否真 fail-closed（F3 已加 `validate=True` + 12 case，但只 F3——非 F3 是 synthetic fallback，这点 F7 已在文案承认；你看有没有别的绕过把合成数蒙成 sizing）。A3 "0 unsound" 立不立得住。
3. **主线 src soundness 守卫**：F7/F8 cut family 的 `_validate_facility_cells_match_pose_registry` 是否真把 `facility_cells` 绑回真实 pose registry（伪造坐标能不能骗过 → false-positive cut → 破坏 FP=0）。这块两轮没动，你独立判。
4. **完整性 + scope 诚实度**：剩余 sizing 项（真 prod registry 建 var / build·proto·RSS·solve / active filter / feasible case 避 INFEAS 早停）真覆盖了吗？F3/F5/F6 的修复让"100K applied=100%"不再误导（remap_audit 暴露 36/50），这个透明度够不够？还有没有同类被偷偷豁免的？

## 我面前的选择

spike close 之后下一步是 P1.3A 主体。我卡在：能不能拿现在 v25 的状态当进入 P1.3A 的依据。

- A：v24→v25 的 7 条 patch 真闭 + 纠正后的 sizing 结论（按约束类型分预算、cap 按 max/p99、跨全族）sound，spike close 成立，进 P1.3A。
- B：还有没修对 / 没修到位 / 新的未闭 finding（请指出 + 反例），再修。
- C：纠正后的 scope/framing 仍划错（比如"按约束类型分 + max/p99 cap 跨全族"这个 framing 不对，或 Finding5#2 标 PARTIAL 还不够/过头）。

我不预设你选哪个。

## 硬性输出约束（两条）

1. **不可达断言要形式化**：任何 "X 不可达 / 必然失败 / 这道 gate 该 NOT_GO 因为 P1.3A 根本走不通" 的断言，请**形式化**：给 complexity reduction、proof-system lower bound、resource inequality，或 cite 文献。不接受 "我觉得 / 直觉 / 大概率"。
2. **给出补丁，并把文档和补丁打成压缩包**：不只指出问题，还要给出能直接落地的**具体补丁**（哪个文件、改成什么，最好是可直接 apply 的 diff 或替换用的代码/文案片段，可标把握度）。补丁跟 finding **不必一一对应**——一个补丁可以覆盖多条 finding，怎么组织你定。**最后请把你的说明文档和这些补丁以压缩包（zip）的形式给出**，方便我直接下载落地。

除此之外 finding 怎么报、报几条、格式你自便。

## 包里怎么核 / 怎么复现

> 解包后得到 `_phase1_2_pkg_v25/` 目录，主线代码在它下面的 `project/`，以下路径相对 `_phase1_2_pkg_v25/`。

- sizing cheap gate（本轮重点，v3 = LSB + bytes/term-by-kind + 全 6 F9，**包内可直接跑**）：`project/docs/research/p1_2_spike_sizing_gate_20260601/`（`sizing_gate.py` + `RESULTS.md`，含 MSB→LSB 对照表 + BoolOr/linear 字节模型）
- spike 自我结论 + G 标准表 + Layer-2 defer + 第九审/v23 修正节：`project/docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- remap 审计（F5）：`project/data/cuts/spike/remap_audit.json`
- spike 实现代码镜像（review-only，**不是** master 合并目标）：`project/code_context/spike/`（含修复后的 `toy_translator.py` / `scale_ramp.py` / `spike_prod_scale_runner.py` + 12-case 自测 `test_toy_translator_f3_malformed.py`）
- 主线 soundness 守卫：`project/src/cuts/families/power_hitting_set.py` 和 `power_grid_reach.py` 的 `_validate_facility_cells_match_pose_registry`；真 bitset 编码：`project/src/cuts/oracles/region_capacity_oracle.py`
- 回归测试：`project/src/tests/cuts/`；跑：`cd project && python -m pytest src/tests/cuts/ -q`（实测 414 passed）

## 包 sha256（核对上传完整）

- `phase1_2_spike_review_v25.zip`：`f245bc9cf1b05e2ee4a1f27288ddc986c58ca416e974f089cc6d4810200750b0`

（依赖 wheel 分 3 块 `deps_linux_py313.zip.001/.002/.003` 与本包一起打在外层 zip 里；解包后 `cat` 三块合并成 `deps_linux_py313.zip` 再离线 `pip install --no-index --find-links` 装，详见包内 README "怎么跑"节。）
