# Batch 4 corrected-front 阶段性复验结果（2026-07-18）

> **状态：部分完成，不是 Batch 4 收官。** 本轮在基线 revision
> `9c0f7242a43bf9a17a31c4c22a01a4375f82a1a3` 上重建可复验 harness，完成
> 独立 front oracle、历史 RAB front-only 对照、两个新 witness 的当前 binding
> 检验、PB v2 翻译审计，以及一组有界生产 RAB A/B。FCL 生产臂和 Round 1–5
> 未运行；PB 没有形成可验证证明；不得据本文恢复任何旧 certificate 或全称判词。

原始运行输出位于未跟踪目录 `.artifacts/batch4_20260718/`。它们是诊断证据，按
仓库规则不提交；下文钉住路径、SHA-256 和诚实边界。可复跑 harness 与回归测试随
本批提交。

## 1. 基线与独立臂

| 项目 | 钉值 |
| --- | --- |
| 当前候选池 | `data/preprocessed/candidate_placements.json`; 7 个 facility pool、共 81,797 poses; `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` |
| 历史候选池 | 66,405 poses; `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b` |
| mandatory / generic I/O | `545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6` / `ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e` |
| canonical rules | `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05` |
| 独立 front oracle | `independent_front_audit.py`; `4c9bd6c0923f661740e15b2a236075034a0ef9ade77f2467e48f30a8cfee0671` |
| 历史 RAB oracle | `rab_front_only_historical_rejudgment.py`; `c84336768ff7a6e66378bf13b0a5c95fda66d3fe4eaab6cfda90571dbfa582bd` |

独立 front oracle 只使用已存 `(x, y)` 口坐标和字面方向 canary，不导入生产
`_DIR_DELTA`/front helper。历史 B0 复审工件
`rounds/b0_4r_historical_reaudit/independent_front_audit.json`
（`77e08379f747eee6eee705a31e334efb8e1de72d34d24975bde9190835d00f1c`）覆盖
293 poses / 1,804 ports：1,569 个口前格被其他本体占据、235 个空闲，越界、
自占和布局重叠均为 0。历史 comb 复审工件
`witness/historical_comb_reaudit/independent_front_audit.json`
（`7d5d40930074031d6b689118f363c9947f12b4cac2fb4c3af7a27db16582062b`）覆盖
241 poses / 1,554 ports：160 blocked、1,394 free，同样无越界、自占或重叠。
历史 B0 的 293 poses 统计跳过了 `ghost_pick` 非设施标记；这两项只重审旧布局的
front/body 几何，不是完整模型 replay。

## 2. 新 witness 与当前 binding

`run_reconstructed_witness.py`（`bc29d57efeedd29bdf998469eb978a3dc5937a732fb6b146580688eced86ed32`）
生成的是当前 revision 下的新重建基线，不能称作恢复历史 witness。
constructor 运行时 `binding_enabled=false` 且强制关闭 overload separation；下表
binding 是事后 identity-front hard-binding validation，不是 binding-aware 构造。

| 构造 | placement / 独立 front | 当前 binding | 边界 |
| --- | --- | --- | --- |
| greedy default | 266/266；1,804 ports = 1,582 free + 222 blocked；无越界、自占或重叠。`result.json` `04ab7172…094a`；独立审计 `bfcc763e…192e` | `FEASIBLE`（内部 CP-SAT `OPTIMAL`）；219/219 exact choices 非 unused；generic inputs 使用 2/14，outputs 使用 52/52；0 empty domains。`binding_validation.json` `601fdcf6…0f32` | 不含 power optional、routing 或 certification |
| comb default | 266/266；1,804 ports = 1,754 free + 50 blocked；无越界、自占或重叠。`result.json` `06d3dd3a…dc20`；独立审计 `41b7813a…21d8` | `FEASIBLE`（内部 `OPTIMAL`）；219/219 exact choices 非 unused；generic inputs 使用 2/14，outputs 使用 52/52；0 empty domains。`binding_validation.json` `7a6f3409…35ce` | 不含 power optional、routing 或 certification |
| skyline seed 0 | 256/266，10 个实例未放置；1,704 ports = 1,600 free + 104 blocked。`result.json` `029466df…5bc6` | 未跑完整 binding validation | 仅部分诊断基线 |

run record 中的三个 constructor source hash 只是随工件携带的来源记录；当前 validator
未验证生产依赖闭包或这些源码的现时字节，不能把它们称作已验证源码闭包。

## 3. RAB 历史对照与有界生产 A/B

六个冻结布局的 front-only 对照工件
`rab_front_only/front_only_historical_rejudgment_v3_comparison.json`
（`876c365ee38c7514dbf506d55c80830c5454581c0da93f510d63feddfa65f681`）完成
1,757 次 pose identity 核对和 1,314 个 eligible owner 检查。corrected 生产实现与
独立 stored-xy oracle 完全一致（1,214 empty / 100 nonempty，0 mismatch）；历史
`+delta` 比较臂为 1,294 / 20，其中 80 个 owner 从 old-empty 转为
corrected-nonempty。该结论只说明 front-only 分类变化，不等于旧 binding、routing
或 certificate 已重放。

生产 A/B 使用相同的 fixed-ghost inner-LBBD 配置：6×6、seed 1、1 worker、fixed
search、最多 6 轮；master/binding/routing/flow 时限分别为 900/600/600/60 秒，
alternative cap 200；systemd cgroup 为 `MemoryHigh=20G`、`MemoryMax=24G`、
`MemorySwapMax=12G`。它不是 `main.py` 外层 campaign，且没有持久化 cut replay。
现有两臂由旧 runner `aecaa1e9a36da7793b99d0f17becb305ae0c6a19b256977fd8a949b206e488ae`
生成；该版本把 venv 入口 `resolve()` 成 uv 基础解释器。run record 已记录实际路径，且
两环境的 OR-Tools/protobuf 版本同为 9.15.6755/6.33.6，但解释器 provenance 不同。
提交后的 runner（`b65c02ad3c0c4572c8f7e113fbd3b34a9cf9d4820ca7f30916f4908e20cf6ed0`）
保留被调用的 venv 路径；现有两臂仍只作为旧 runner 下的诊断快照，
无需为此重跑 8+49 分钟。其七个 source pin 也不是传递依赖闭包。

- **RAB off（clean）**：`result.json` `7517d608…546f`，`run_record.json`
  `6c683a60…5397`；worker exit 0。LBBD `UNKNOWN`、无 solution；1 轮，master
  `OPTIMAL`，枚举 200 个 binding，199 个 routing precheck reject，0 routing
  attempt、0 cut。总墙钟 8m53.161s，峰值 20G RAM / 1.4G swap。
- **RAB on（非 clean）**：`result.json` `81c01a1f…ddff` 在崩溃前写出
  `COMPLETED` 诊断快照：LBBD `UNKNOWN`、6 轮、1,208 个
  empty-domain/exact-safe cut、0 binding enumeration、0 routing attempt、无
  solution。但 `run_record.json` `e056f985…6162` 记录 `WORKER_FAILED`、exit
  `-11`；所以不能称作 clean run。coredump 的崩溃点位于 Python `_Py_Finalize`
  清理 OR-Tools `CpModelProto`/constraint protobuf 的析构路径；这只能定位发生点，
  不能单凭栈断言根因。总墙钟 49m28.776s，峰值 20G RAM / 2.1G swap，未发生
  cgroup OOM。

两臂都没有求得 solution，也没有进入 routing solve（RAB-off 仅执行到 precheck），
因此不能形成 RAB 性能优劣、可行性或 certified soundness 结论。

## 4. PB v2 翻译审计

历史 PB v1 同时含有 front 二次偏移和 RHS 代数错误。目标约束
`|F| - sum(occ) >= d*x` 的正确 OPB 形式是
`-d*x - sum(occ) >= -|F|`；v1 使用 `d-|F|`，会连未选 pose 一并过约束。

v2 encoder、独立 gate 和 toolchain runner 当前源码 SHA-256 分别为
`035667385a61a070eadbabf965ef84ab113ff9b5fddced9c4d67abf7cfc7f6a4`、
`821a5b4bbac3450f2b14a6117e230e45e9cef35c154dec5487ba2bcbec1db966`、
`6ad659f6d034189621416b18788cb0448d4681d68b7508c8e67c254dcbd9a9e2`。
单元 truth table（含 `d=3`）和共享中间格 canary 已覆盖正确代数。已有大工件生成于
最终 provenance 加固之前，只能作为翻译诊断：

- 60×60 gate `PASS`（544,000 constraints、64,104 vars），工件
  `pb/fc_60x60/translation_gate.json` `d28f9d1b…b21b`。raw solver stdout 在
  120 秒为 `TIMELIMIT`、exit 4；当时 runner 将其记为 `NO_RESULT`。proof 以
  `conclusion NONE` 收尾，VeriPB 未运行，`claim: none`。
- 6×6 gate `PASS`（260,500 constraints、68,208 vars），工件
  `pb/fc_6x6/translation_gate.json` `4ab18533…5c81`。566,190,080-byte proof
  (`a57c2104…c095`) 截断于半个 token，且没有 toolchain record/stdout/stderr；
  它不可验证，也没有 solver 或 UNSAT 结论。

因此 PB-03 仍为“需重验”；没有恢复任何 business UNSAT 或 proof claim。

## 5. FCL、测试与剩余工作

FCL 全池 golden 已改成独立字面 `(x, y)` 方向臂，覆盖 17 groups / 295,700 个
group-pose case；这不是 295,700 个唯一 pose。生产 FCL off/on 均未启动，
`.artifacts/batch4_20260718/prod_ab/` 下没有 FCL 产物。

本批可复跑检查：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-uvbolt-backup/bin/python3.13 -m pytest \
  -p no:cacheprovider -p no:randomly --basetemp=/tmp/zmd-b4-targeted \
  src/tests/test_batch4_*.py src/tests/test_front_clear_lift_full_pool_golden.py -q
.venv-uvbolt-backup/bin/python3.13 -m ruff check \
  docs/research/front_offset_incident_20260718/batch4_harness src/tests/test_batch4_*.py \
  src/tests/test_front_clear_lift_full_pool_golden.py
```

提交前定向结果为 59 passed（53.48s），Ruff 全绿。已暂存 32 文件后，受控并发
（4 xdist workers，BLAS/OMP 各 1 thread）的 `preflight_gate.py --full` 为 19/19：
4,561 passed / 74 skipped（467.87s）；串行 `--slow-tests` 为 31 passed（289.96s）。
默认 24-worker 的两次尝试分别在两个无关测试子进程中触发 Python 3.13 `SIGSEGV`；
两项孤例均串行通过，coredump 同时显示每进程 OpenBLAS 线程过度订阅，因此不把失败尝试
称作 clean gate，也不把它归因于本批代码。以上通过数字只采用无崩溃的受控并发终态。

Batch 4 剩余项为：生产 FCL A/B、Round 1–5 corrected-front 重跑、PB 当前
provenance 工件的完整 solver+verifier 闭环，以及 RAB-on cleanup SIGSEGV 的独立
复现/根因调查。未来 FCL 验收还必须要求 `corpus_errors` 为空且布局 corpus 完整，不能
只看 run `COMPLETED` 或 raw-scope `PASS`。除非这些各自完成对应门禁，否则历史 addendum 的“作废/需重验”状态
不因本轮数字相似而自动恢复。
