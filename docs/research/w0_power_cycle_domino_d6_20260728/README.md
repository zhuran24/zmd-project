# W0 power-cycle domino：D6 局部联合 completion gate

**状态：** RESEARCH_ONLY / LOCAL_D6_ONLY
**日期：** 2026-07-28
**账本影响：** 无；`U=(1188,18)`、`L=absent`、`production_certified=false` 保持不变。

本目录实现 power-cycle domino framework 的首个 exact、front-aware 局部联合 gate。它只回答
完整 D6 antecedent 在给定运行配置下的局部 completion 问题，不产生 whole-layout witness、
全图 cut、下界、全局 infeasibility 或 production authority。实际运行结果只存在于
`.artifacts/research_runs/` 下的 no-overwrite run root；tracked 源码不预写某个 verdict。

## 输入与信任边界

| 输入 | SHA-256 | 角色 |
|---|---|---|
| `docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json` | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` | strict instance |
| `W0_power_cycle_domino_framework_v1.json` | `db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89` | 外部 research framework |
| `W0_geometry_only_seed_v1.json` | `18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1` | 外部 geometry warm-start seed |

runner 通过 G3 公共研究合同读取一次实际 bytes、复核期望哈希、复制到独占 run root，再只消费
这次快照的内存 bytes。seed 内部 `validation_summary.source_sha256=295bfef9…` 与实际 seed
bytes 没有可验证的绑定关系，只登记为被拒绝的 producer claim；外部 validation 与
frozen-geometry front probe 也不参与 gate 验收。构造器自报不能替代独立 replay。

## 完整 D6 antecedent

- domino 为 power cells `(1,2)` 与 `(2,2)`，局部范围 `x=14..41, y=28..41`；
- 两个固定 2×2 pole body 的 anchors 为 `(20,34)` 与 `(35,35)`；
- body-only protected rectangle 为 anchor `(29,28)`、size `6×7`；
- directed cycle 为 `y=29, x=14..41`、方向 east；
- seed-narrow attachment slots 为 `x=23..25` 与 `x=30..37`，cycle cell `(x,29)`、
  branch cell `(x,30)`；
- tile type counts 分别为 `(5×3x3, 3×5x5, 1×6)` 与
  `(5×3x3, 1×5x5, 2×6)`；
- anonymous class vector 为
  `{3L:7, 3O3:3, 5L:2, 5O2:2, 6G:2, 6B:1}`，共 17 bodies、
  25 active inputs、25 active outputs。

class 的 template 与 I/O 数量从 strict `operation_groups` 推导，mode 与 physical port catalog
从 strict `facility_templates` 推导。seed body anchors 只按 tile/type 稳定匹配后进入 `AddHint`，
不成为等式或冻结 geometry。

## 联合语义

gate 同时决定 operation class、body anchor、mode、exact active physical ports/fronts、
transport incidence、cycle attachment roles 与两个方向的可达性流。每个 body 必须留在所属
14×14 power cell，彼此不重叠，避开 cycle、pole bodies 与 protected body rectangle，并至少有
一个 body cell 被固定 pole 覆盖。active front 严格按
`anchor + port.body_cell + direction_delta` 复算，必须在 domino 内且不被任何 body 占用。

ground transport 使用 strict routing 语义的 44 个 directed patterns：12 个 straight/turn、
16 个 splitter、16 个 merger；elevated channel 只有 4 个 directed straight patterns。
同一 cell 的双层同时使用只允许两个互相垂直的 straight channel，且 cross 不切换通道。
相邻 cell 之间按权威 routing incidence 聚合前驱/后继，因此可在该邻接边上 ground↔elevated
换层；这不等于允许在同一 crossing cell 内换线。
普通 cycle cell 固定为 `W→E`；output injection 为 `{W,N}→E`；input tap 为
`W→{E,N}`，两类 role 不共用 cell。

`OUT` 极性要求每个 active output 注入 1 单位，最终由 output-injection slots 吸收总计 25；
`IN` 极性由 input-tap slots 发出总计 25，每个 active input 消耗 1。整数流必须落在所选
directed channel arcs 上；certificate 同时携带离散配置和可独立复算的流/可达性证据。

## 结果语义

- `FEASIBLE`：只证明该 run receipt 精确绑定的 D6 局部 antecedent；交付
  `configuration.json` 与最小 `certificate.json`。
- `INFEASIBLE`：只关闭完全一致的 antecedent、源码与 solver config。
- `UNKNOWN`、超时、中断或异常：不产生拒绝、cut、下界或全局结论。
- intake、哈希、工作树 clean 或 antecedent 构造失败：不是 D6 verdict。

seed-narrow 的 `INFEASIBLE` 下一项最小变体只把 attachment slots 放宽到全部合法 D6 slots；
`UNKNOWN` 的下一项最小变体只把时间预算从 3600 秒提高到 7200 秒。两种情况都不启动全图
solve。H20 row-power oracle 不在本目录实现。

## 隔离运行与 replay

从已提交且 clean 的源码 HEAD 运行：

```bash
python docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py \
  --strict docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json \
  --framework /home/zhuran24/下载/w0回复/1/W0_power_cycle_domino_framework_v1.json \
  --seed /home/zhuran24/下载/w0回复/1/W0_geometry_only_seed_v1.json \
  --run-root .artifacts/research_runs/w0-d6-<run-id> \
  --workers 2 \
  --random-seed 0 \
  --max-time-seconds 3600
```

producer run root 内含快照 inputs、源码副本、canonical `config.json`、完整
`antecedent.json`、`result.json` 和最终 `receipt.json`；只有 `FEASIBLE` 才有
`configuration.json` 与 `certificate.json`。

独立 replayer 是 stdlib-only、solver-free 的自包含实现，不导入 gate、runner、G3、`src/`
或 OR-Tools。replay receipt 应写入新的 sibling root，不能改写 producer root：

```bash
mkdir .artifacts/research_runs/w0-d6-<run-id>-replay
python -I .artifacts/research_runs/w0-d6-<run-id>/sources/replay_d6_certificate.py \
  --run-root .artifacts/research_runs/w0-d6-<run-id> \
  --output .artifacts/research_runs/w0-d6-<run-id>-replay/replay_receipt.json
```

所有 status 都复核完整 byte graph；只有 `FEASIBLE` 进入 body/front/incidence/crossing、
cycle role、flow 与 graph reachability 的语义复算。replay 成功仍只确认 receipt 声明的局部
范围，不提升其 authority。
