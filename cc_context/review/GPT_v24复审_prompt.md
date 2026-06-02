# 终末地 exact solver — Phase 1.2 spike close gate 复审 (v24)

我有一个项目想请你独立审一个具体的 gate。先把背景和我真正想知道的讲清楚，你别被我带偏，也别因为客气就给我盖章。

## 项目是什么

70×70 网格上 266 个固定设施的 certified-exact 最大空矩形求解器（游戏《明日方舟：终末地》的工业规划器）。目标 `max_lex(area, min_side)`，用 OR-Tools 9.15 CP-SAT + LBBD（Benders）分解。附件 zip 是项目快照（`project/` 是主线代码+数据，`code_context/` 是 review-only 的旁支代码镜像）。

## 我要你审的 gate

项目里有一道工序叫 "prod-scale spike"，目的是在真正动手做下一阶段（P1.3A，真 master 集成 + 多轮 LBBD 收敛）之前，先验证 cut 在生产规模下的 **sizing**（build/translate/solve 耗时、proto 大小、RSS）扛不扛得住。spike 自己的结论是 **GO_WITH_MINOR**，只认 sizing 这一层，把收敛性和对抗鲁棒性 defer 到下一阶段。

这道 gate 已过多轮独立审查。**最近两轮都判了 B**：第九审 catch 了 4 条 soundness + 1 条 sizing 口径问题（已修，出了 v23）；v23 再送审又判 **B**，catch 了 7 条。**v24（本附件）是这 7 条全修后的版本。**

这里我要对你完全坦白一件事，因为它正是本轮最该被你审的：**v23 之后我新加了一个 sizing cheap-gate 脚本来量化 cut body 大小，那个脚本我自己写错了——bitset 解码用了 MSB-first，而项目真源是 LSB-first，导致 term 数偏高约 10x，并据此得出一个"F1/F9 大池子 → 100K 约 1.9GB 会爆"的结论。那个数字是假的。** v23 审查方独立按 LSB 重算 catch 了它，我对真源码核实属实、修正了（真实 region 大池子是 ~264 term 不是 2026，纠正后 fixture 尺度根本不爆）。我把这个写出来，是要你**别因为我"诚实地修了自己的 bug"就放松**——请你独立验证修正后的数字和结论本身对不对。

包里 README + verdict.md 记录了每轮 catch 了什么、改了什么。**你不用、也别假设你看过前面任何一轮——就当第一次看，独立判断现在 v24 的状态。** 前几轮 finding/修复都在 git 历史和 README 里，是给你 source-check 的事实素材，不是要你接谁的话往下说。

我想知道的就一件事：**以 v24 现在的状态，这道 spike close gate 还有没有未闭的 soundness / 完整性 / scoping finding？** 两个具体角度都欢迎挑战：(a) 下面列的 7 条是不是**真修对了、修到位了**；(b) 修正后的 sizing 结论（fixture 尺度全族 compact lowering 便宜、expanded lowering 跨**所有**族随 region×pool 变、需 per-cut term cap）是 sound 的，还是仍有藏雷。

### v23 → v24 修了哪 7 条（给你核，不是要你认）

- **F1 可复现**：sizing gate 脚本原来硬编码读一个不在包里的外部 v22 zip 取 fixture → 包内审者跑不了。改成读包内 `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` + `data/preprocessed/candidate_placements.json`。
- **F2 bitset 字节序（最重，就是上面说的我的 bug）**：MSB-first → LSB-first，与真源 `src/cuts/oracles/region_capacity_oracle.py` 的 `_encode_region_bitset`（`arr[idx//8] |= 1<<(idx%8)`）一致。
- **F3 scope 过窄**：原说"只 F1/F9 会爆、其余 7 族任意 lower 都安全"不成立——blow-up 是 region-size×pool 的函数、跨所有族。改成：compact (witness/no-good) lowering 全 9 族安全；任何族走 expanded (全 pose-overlap) lowering 才需设 per-cut term cap。
- **F4 F9 没真测**：sizing gate 原对 `density_envelope` 退回 compact witness 计数（4），没测 window→pose overlap。补了真实计数（10×10 window 大池子 ~360–524 term）。
- **F5 remap telemetry 没进 artifact**：translator 早有 unknown-pose remap 计数字段，但 ramp artifact 没写出。补：`scale_ramp` jsonl 加 `n_pairs_remapped`/`true_registry_bound`，新增 `data/cuts/spike/remap_audit.json`（50 cert 150 pair 中 **36 个 unknown-remapped**，density 24 + port 12）→ 让 "B2 cut_count_applied=100%" 不再静默掩盖"literal 没绑真 registry"。
- **F6 verdict writer 没锁**：`spike_prod_scale_runner.py` 的 G10 原硬编码 PASS、Finding5#2 模板原写 YES（只手改的 verdict.md 是 PARTIAL）→ 重跑会回归。改成 G10 从 A3 fixture 真算（≥45 / 0 unsound / 0 schema_err / ≥9 family），模板写 PARTIAL。
- **F7 malformed scope**：文案明确 toy_translator 只有 F3 `port_exposure` malformed fail-closed，非 F3 仍走 synthetic fallback——不泛化成"全局 fail-closed"。

### 纠正后的 sizing 结论（请重点审这个对不对）

fixture 尺度下：(a) 全 9 族 realistic compact (witness/no-good) lowering → 100K 都便宜（~1–3 MB）；(b) expanded (full pose-overlap) lowering 随 region-size×pool-density 变，fixture 尺度 region (139 cells)/window (10×10) 给 ~百级 term/cut（region 大池子 ~264 / cutset ~173 / F9-window ~360–524 / power 小池子 16）→ 100K ~0.1–0.3 GB，可控；只有大 region/window 趋近全 pool（~16–18K term/cut）才到数 GB。→ P1.3A lowering 设计硬约束 = 对任何 geometric/expanded lowering 设 per-cut term cap + cumulative proto budget（跨所有族，不止 F1/F9）。证据脚本 `project/docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`（v2 LSB），在 `project/` 根下可直接跑复现。

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

spike close 之后下一步是 P1.3A 主体。我卡在：能不能拿现在 v24 的状态当进入 P1.3A 的依据。

- A：7 条 finding 真闭 + 纠正后的 sizing 结论 sound，spike close 成立，进 P1.3A。
- B：还有没修对 / 没修到位 / 新的未闭 finding（请指出 + 反例），再修。
- C：纠正后的 scope 仍划错（比如"expanded lowering 跨所有族设 cap"这个 framing 不对，或 Finding5#2 标 PARTIAL 还不够/过头）。

我不预设你选哪个。

## 唯一的硬性输出约束：不可达断言要形式化

任何 "X 不可达 / 必然失败 / 这道 gate 该 NOT_GO 因为 P1.3A 根本走不通" 的断言，请**形式化**：给 complexity reduction、proof-system lower bound、resource inequality，或 cite 文献。不接受 "我觉得 / 直觉 / 大概率"。除此之外 finding 怎么报、报几条、格式你自便。

## 包里怎么核 / 怎么复现

> 解包后得到 `_phase1_2_pkg_v24/` 目录，主线代码在它下面的 `project/`，以下路径相对 `_phase1_2_pkg_v24/`。

- sizing cheap gate（本轮重点，v2 LSB，**包内可直接跑**）：`project/docs/research/p1_2_spike_sizing_gate_20260601/`（`sizing_gate.py` + `RESULTS.md`，含 MSB→LSB 对照表）
- spike 自我结论 + G 标准表 + Layer-2 defer + 第九审/v23 修正节：`project/docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- remap 审计（F5）：`project/data/cuts/spike/remap_audit.json`
- spike 实现代码镜像（review-only，**不是** master 合并目标）：`project/code_context/spike/`（含修复后的 `toy_translator.py` / `scale_ramp.py` / `spike_prod_scale_runner.py` + 12-case 自测 `test_toy_translator_f3_malformed.py`）
- 主线 soundness 守卫：`project/src/cuts/families/power_hitting_set.py` 和 `power_grid_reach.py` 的 `_validate_facility_cells_match_pose_registry`；真 bitset 编码：`project/src/cuts/oracles/region_capacity_oracle.py`
- 回归测试：`project/src/tests/cuts/`；跑：`cd project && python -m pytest src/tests/cuts/ -q`（实测 414 passed）

## 包 sha256（核对上传完整）

- `phase1_2_spike_review_v24.zip`：`b66e3318705e8f8a29bcf697a21bccaa3008dc0c15c61ed33412997e9febb9a0`

（依赖 wheel 分 3 块 `deps_linux_py313.zip.001/.002/.003` 与本包一起打在外层 zip 里；解包后 `cat` 三块合并成 `deps_linux_py313.zip` 再离线 `pip install --no-index --find-links` 装，详见包内 README "怎么跑"节。）
