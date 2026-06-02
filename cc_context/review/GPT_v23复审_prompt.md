# 终末地 exact solver — Phase 1.2 spike close gate 复审 (v23)

我有一个项目想请你独立审一个具体的 gate。先把背景和我真正想知道的讲清楚，你别被我带偏，也别因为客气就给我盖章。

## 项目是什么

70×70 网格上 266 个固定设施的 certified-exact 最大空矩形求解器（游戏《明日方舟：终末地》的工业规划器）。目标 `max_lex(area, min_side)`，用 OR-Tools 9.15 CP-SAT + LBBD（Benders）分解。附件 zip 是项目快照（`project/` 是主线代码+数据，`code_context/` 是 review-only 的旁支代码镜像）。

## 我要你审的 gate

项目里有一道工序叫 "prod-scale spike"，目的是在真正动手做下一阶段（P1.3A，真 master 集成 + 多轮 LBBD 收敛）之前，先验证 cut 在生产规模下的 **sizing**（build/translate/solve 耗时、proto 大小、RSS）扛不扛得住。这个 spike 自己的结论是 **GO_WITH_MINOR**，明确只认 sizing 这一层，把收敛性和对抗鲁棒性 defer 到下一阶段。

这道 gate 此前已过 9 轮独立审查。**最近一轮（第九审）判了 B（未 clean close）**，catch 了几条 soundness / 完整性 / scoping finding。我已逐条复核确认属实并修复，这个附件包（**v23**）就是修复后的状态。包里 README 的「v22 → v23 状态变化」节 + `verdict.md` 的「第九审修正」节，记录了第九审 catch 了什么、我改了什么。

**你不用、也别假设你看过前面任何一轮——就当第一次看，独立判断现在 v23 的状态。** 前几轮的 finding 和修复都在 git 历史和 README 里，是给你 source-check 的事实素材，不是要你接谁的话往下说。

我想知道的就一件事：**以 v23 现在的状态，这道 spike close gate 还有没有未闭的 soundness / 完整性 / scoping finding？** 两个具体角度都欢迎挑战：

- (a) 第九审那几条 finding（下面列了）是不是**真的修对了、修到位了**，还是表面改了、实际仍有绕过 / 仍能蒙混？
- (b) 修复里对 scope 的**收窄**——尤其是把 "真 cut body 分布 sizing" 从"已覆盖"降级为 **PARTIAL**、并把 F1/F9 大池子容量 cut 的 sizing 风险量化成 P1.3A 的硬约束——是 sound 的，还是又一次把本该 block 这道 gate 的东西藏进了 "下一阶段"？

有就指出来、给可复现的反例；没有就直说没有。**别因为我已经修了就觉得这轮必须给 GO**，也别因为前面 9 轮都在收尾就客气。

### 第九审 catch 了什么 / v23 改了什么（给你核，不是要你认）

旁支 `toy_translator` + A3 fixture 4 个 soundness 修 + 1 个 sizing 口径收窄：

1. `_decode_cert_b64` 旧码 `base64.b64decode` 不带 `validate=True` → 合法 b64 里混入非 alphabet 垃圾字符会被静默丢弃、仍解码成功 → F3 不 fail-closed。v23 改 `validate=True`，micro-probe 从 9 case 加到 12（含 garbage prefix/suffix/middle）。
2. fallback / unknown-pose-remap 用内置 `hash()`（PYTHONHASHSEED 随机，跨进程不可复现）→ 改 `_stable_hash`（blake2b）。
3. unknown `(facility_type, pose_id)` 不在真 registry 时被静默 hash-remap 到任意真 var、仍计入 `applied` → 加 `n_pairs_remapped` / `per_family_remapped` telemetry，让 "100K applied=100%" 不再静默掩盖 "literal 没绑真 registry"（第九审实测 50 cert 中 36 个 pair unknown）。
4. A3 G10 pass 判定旧码只查 `total≥45 and unsound==0`，放行 `schema_err` → 加 `schema_err_count == 0`。
5. **sizing 口径收窄**：第九审指出 B2 的 100K proto/RSS 数字是"合成/remap 吞吐量"，不是"真 cut body 绑真 registry"。我做了个 cheap gate（`project/docs/research/p1_2_spike_sizing_gate_20260601/`，对真 fixture + 真 registry 直算），结论：cut body 的 master 约束大小不是固定可测的事实，而是 **~1000x 的 lowering 设计变量**；100K sizing 有界便宜（~1–40 MB），**唯一** blow-up 路径 = F1 region_capacity / F9 density_envelope 的**大池子**（manufacturing ~17952 pose）容量/面积 cut 按展开式 lower（每条 ~2000–3200 term → 100K ~1.9 GB）；其余 7 族任意 lower 都是几项到几十项。verdict 的 Finding 5 #2 已 YES→PARTIAL，并把 F1/F9 这条作为 P1.3A lowering 设计的带数字硬约束（二选一：witness 紧凑 no-good / 大池子展开设上界）。

## 真正的瓶颈（免得你往错方向使劲）

项目的根本难点不是这个 spike，是：master CP-SAT 在 prod 规模 single-solve 解不动——这是 latency-bound 工作负载（~280K pose registry，two-watched-literal 随机指针追逐，working set 溢出 L3）。项目试过 27 条求解 paradigm，绝大多数 NOT_GO，死因分类在 `project/docs/项目说明/03_paradigm_death_baseline.md` 和 `project/docs/research/` 下。当前主线是 cut-family LBBD 重设计：9 个 cut family（F1–F9）当 Benders cut 喂回 master 收紧搜索。这个 spike 就是在验这些 cut 的工程可行性。

## 已经死掉的方向（别重新推荐）

这些都实测/推理穷尽过，verdict 死。除非你能指出之前的 NOT_GO 论证里有**具体技术漏洞**（见最后一节的形式化要求），否则别 resurrect：

- 单机扩 RAM 路径：augmented master / GOC / PGW 全在 25–32 GB 上界，机器 48 GB，撑不住。
- 重写求解器：HiGHS 等 LP-MIP 对这种 dense linear constraint 不适合（实测 42 GB > 现 OR-Tools 30 GB）。
- 让 pose-bool master 自己持有 port direction / pole selection / belt routing 的决策：6 条 paradigm 撞同一面墙（master 表达力 fundamental 不够），全死。

## 重点看这几层（不限于此）

1. **假证据 / soundness（最高价值）**：spike 的 sizing 数字能不能被伪造或误导？具体说——`toy_translator` 在 cert malformed（坏 base64 / 非 dict root / 缺字段）时是不是真的 fail-closed。第九审 catch 了 base64 不带 validate 的洞，v23 已加 `validate=True` + 3 个 garbage case（现 12/12 PASS）。请验证：**这个修复是否真堵住了**？还有没有别的 malformed 路径（别的 family、别的字段、别的编码）能绕过 fail-closed，把合成 literal 蒙混成 sizing 数字？A3 oracle-emit fixture 报的 "0 unsound" 立不立得住？
2. **主线 src 的 soundness 守卫**：F7/F8 这两个 cut family 的 validator，是不是真的把 cert 里的 `facility_cells` 绑回了真实 pose registry？（不绑的话，可以伪造一个坐标骗过 validator → 生成 false-positive cut → 把本该可行的 pose 剪掉，破坏 FP=0。这是更早几轮的 BLOCKER 修复点，我想确认它真补上了、且锁住了——这块第九审没动，但你独立判。）
3. **完整性 + sizing 口径收窄是否 sound**：第九审指出 spike 原称覆盖"真 cut body 分布"是 overclaim（translator 把多数 cert lower 成合成/remap 小约束，36/50 pair 引用不在真 registry 的 pose 被静默 remap）。v23 的应对是 #5 描述的收窄 + 那个 sizing cheap gate。请审：**这个收窄诚实吗、量化对吗**？`sizing_gate.py` 的方法（按设施类型限定的 cell→pose overlap 计 term 数，区分紧凑 no-good vs 大池子展开）站不站得住？"唯一 blow-up 是 F1/F9 大池子展开"这个 claim 有没有漏掉别的 family / 别的 lowering 也会爆？还有没有同类被偷偷豁免的 sizing？另外 spike 仍声称覆盖的其余几项（真 prod registry 建 master var / build·proto·RSS·solve 实测 / active-cut filter / 一个 feasible case 避免 INFEASIBLE 早停掩盖成本）真覆盖了吗？
4. **scoping 诚实度**：GO_WITH_MINOR 把收敛性和对抗鲁棒性 defer 到下一阶段，第九审之后又把 cut-body sizing 这条收窄成 PARTIAL+P1.3A 硬约束——这些 defer / 收窄是诚实的，还是把本该 block 这道 gate 的东西藏进了 "下一阶段"？（前几轮最大的争议就是 "某个 gap 能不能用 'convergence later' 豁免"，结论是不能。我想知道还有没有同类被偷偷豁免的。）

## 我面前的选择

spike close 之后下一步是 P1.3A 主体。我卡在：能不能拿现在 v23 的状态当进入 P1.3A 的依据。

- A：第九审 finding 真闭 + 收窄后的 scope sound，spike close 成立，进 P1.3A。
- B：finding 没修对 / 修得不到位 / 还有新的未闭 finding（请指出 + 反例），修完再进。
- C：收窄之后的 scope 本身仍划错——比如把 F1/F9 sizing 当 P1.3A 约束这个 framing 不对，或 Finding 5 #2 标 PARTIAL 还不够诚实（其实该 NOT 覆盖）/ 过度诚实（其实没问题）。

我不预设你选哪个。

## 唯一的硬性输出约束：不可达断言要形式化

如果你的结论里出现任何 "X 不可达 / 必然失败 / 这道 gate 该 NOT_GO 因为 P1.3A 根本走不通" 这类断言，请把它**形式化**：给 complexity reduction、proof-system lower bound、resource inequality，或者 cite 文献。不接受 "我觉得 / 直觉 / 大概率"。

除此之外，finding 怎么报、报几条、什么格式，你自便——我不规定 verdict label，也不规定字数。

## 包里怎么核 / 怎么复现

> 解包后得到 `_phase1_2_pkg_v23/` 目录，主线代码在它下面的 `project/`，以下路径都相对 `_phase1_2_pkg_v23/`（即 `cd _phase1_2_pkg_v23` 后用）。

- spike 自我结论 + G 标准表 + Layer-2 defer + **第九审修正节**：`project/docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- 第九审 sizing cheap gate（v23 新增，对真 fixture+真 registry 直算）：`project/docs/research/p1_2_spike_sizing_gate_20260601/`（`RESULTS.md` + 可复现的 `sizing_gate.py`）
- spike 实现代码镜像（review-only，**不是** master 合并目标）：`project/code_context/spike/`（含修复后的 `toy_translator.py` 和它的 12-case fail-closed 自测 `test_toy_translator_f3_malformed.py`、runner、各 lib；说明在 `project/code_context/README.md`）
- 主线 soundness 守卫：`project/src/cuts/families/power_hitting_set.py` 和 `power_grid_reach.py` 里的 `_validate_facility_cells_match_pose_registry`
- 对应回归测试：`project/src/tests/cuts/`（含两个 `test_validator_unsound_when_facility_cells_do_not_match_pose_registry` 和 `test_oracle_scope_digest.py`）
- 原始 telemetry：`project/data/cuts/spike/*.jsonl`
- 每个 cut family 的 per-commit 数学 cross-check 存档：`project/docs/research/` 下各 `*_gemini_round*` / `cross_check/`
- 跑测试：`cd project && python -m pytest src/tests/cuts/ -q`（实测数见包内 README）；spike 自测跑法见 `project/code_context/README.md`

## 包 sha256（核对上传完整）

- `phase1_2_spike_review_v23.zip`：`131609a399f6afa00b2b58eb94afb1503efa3d500372cb930a84ca702d782b73`

（依赖 wheel 分 3 块 `deps_linux_py313.zip.001/.002/.003` 单独上传，`cat` 合并后 `pip install --no-index --find-links` 离线装，详见包内 README 的"怎么跑"节。）
