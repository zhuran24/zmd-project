# 26 — pricing-bound 实验交付包回件（2026-08-04）来源与性质

| 项目 | 值 |
|---|---|
| 收件时间 | 2026-08-04 |
| 通道 | owner 于 2026-08-04 把 GPT Pro 会话产出的交付包（zip）喂入主线线程 |
| 存档内容 | `26_pricing_bound_exp_delivery_20260804/`（18 个文件，逐字复制，未做任何改动） |
| 回件 zip | `~/下载/w0_pricing_bound_exp_20260804_pricing_bound_deliverable.zip`，51,370 B，SHA256 `07b0d3dbf6e5a1e00c88a78ccfd3553a21bb30eab37c7bcca222e228d9a5596c` |
| 送出的提问包 | `w0_pricing_bound_exp_20260804.7z`，82,123 B，SHA256 `8493d9c4bd389ab5bd570cf1b33e654ab1b7b2e2693700eff0c52a5a2145fdff` |
| 提问包源目录 | `.artifacts/w0_consult_packs_20260804/pricing_exp/`（`00_ASK.md`、`01_problem_spec.md`、`02_proposal_excerpt_column_generation.md`、`03_our_assessment_of_the_machine.md`、`04_pricing_bound_evidence.md`、`05_raw_result_CLEAN.json`、`06_raw_result_CORNER_hole.json`、`07_raw_result_LEFT_J3_strict.json`、`08_area_probe.py`、`09_class_supply_pre_gate.json`、`10_implementation_state.md`、`11_runnable/`、`12_raw_results/`、`MANIFEST.sha256`） |
| 包内自带清单 | `MANIFEST.sha256`（17 条），存档后逐条校验通过（`sha256sum -c`，17/17 OK） |

存档时把 zip 内唯一顶层目录 `pricing_bound_deliverable/` 的内容平铺进本目录（文件字节一字未改，
`MANIFEST.sha256` 的相对路径因此仍然可直接校验）。

## owner 转述的交付摘要要点

- 修正后的 Lagrangian 需要一层 **bucket 运输层**：桶权重取 `w_b(μ)=max_{c∈S_b}(A_c−μ_c)`，
  分支目标从纯面积换成 `max Σ_b w_b n_b − λh`。对方称该消元是精确的（取最小合法 `w_b` 只放松
  pattern 对偶约束、不增加 dual 目标）。
- 最直接的施工门槛：若 `CLEAN` 无孔 pricing 的合法局部上界从 146 降到 **142 或更低**，并保留包内
  现有 `CLEAN+hole≤129`、边界孔算术界与 `CORNER+hole≤85`，三类互斥孔分支的统一上界就从 **3388
  降到 3324**，过证书线（四格 local drop 经 16 倍乘数变成 64 格，正好补齐差距）。
- **cap-3 scope 纪律**：上面用到的 129/85 来自随附 `MAX_POLES_PER_REGION=3` 模型，因此 3324 这张
  证书明确属于 cap-3 scope；no-cap 主实验的上界可以安全用于该较小 scope，但**不能反过来**把
  129/85 外推成 no-cap 上界。若正式目标改成不限杆数的过覆盖模型，必须重新取得对应的 no-cap
  hole 上界。
- **NO-GO 数字条件**是可证伪的合取门（见报告 §2.4）：包含 D0 cap-3 exactly-one-hole 界相对 3388
  的 reduction `<16` 等若干项，且必须先通过校准项 `D0_AREA+CORNER+hole+loose+max_poles=3` 在
  240 秒内把 bound 压到 `≤90`——校准失败只能判 `INVALID_CALIBRATION_FAILED`，不得判 NO-GO。
  任一关键任务出现一格 bound drop、任一 closure 达 0.10、或校准失败，都推翻 NO-GO。
- **对方本地 pilot 不构成 GO/NO-GO**：`pilot_summary.json` 自带 `not_target_machine_evidence: true`、
  `research_only: true`，环境是 5 逻辑核 / 约 5.9 GiB 内存，只用来验 harness 能跑通。

## 性质与边界

**research-only 外脑产出，未经我方核实。** 本目录只做逐字存档，不构成复核结论：

- 包内所有【已证明】标注、阈值算术、GO/NO-GO 门限、pilot 数字均是对方自述；本文书写就时尚未做
  独立复算或对抗审查，引用任何一条前必须先自己算。
- 不携带任何 authority：不改变 `U=(1188,18)`、`L=absent`，不登记任何界，不触碰 cut / production /
  certified 状态，也不触碰 `PROJECT_LOCK.md` 的任何 `F-*`/`PCR-*`/`CUT-*` 条款。
- 包内脚本（`pricing_probe.py`、`run_protocol.py`、`analyze_protocol.py`、`lagrangian_accounting.py`、
  `make_tables.py`、`test_deliverable.py`）**未被执行**，其产物也未被应用到仓库内任何文书或工件。
- 先例纪律（19 号、147.4 两次）：外脑推理文书入库不等于采信，承重引用前要过 refute 席，数字前提
  要标证据等级。
