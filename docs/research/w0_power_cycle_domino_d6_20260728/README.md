# W0 power-cycle domino：D6 局部联合 completion gate

**状态：** RESEARCH_ONLY / LOCAL_D6_ONLY / ROOT_CLOSURE_V2_READY / SEED_NARROW_RERUN_PENDING_ENDFIELD
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
directed channel arcs 上。`configuration.json` 携带离散配置和可独立复算的流/可达性证据；
最小 `certificate.json` 只绑定 antecedent/config 哈希、status 与 claim boundary。

## 结果语义

- `FEASIBLE`：只证明该 run receipt 精确绑定的 D6 局部 antecedent；交付
  `configuration.json` 与最小 `certificate.json`。
- `INFEASIBLE`：只关闭完全一致的 antecedent、源码与 solver config。
- `UNKNOWN`、超时、中断或异常：不产生拒绝、cut、下界或全局结论。
- intake、哈希、工作树 clean 或 antecedent 构造失败：不是 D6 verdict。

历史已执行的 v1 research producer root
`.artifacts/research_runs/w0-d6-seed-narrow-20260728T132308Z-27b4ae9/`
的 v1 receipt 命名字节图可独立重放，绑定 antecedent
`7dd634386b4c27a695a7115bd0dddf1c67556ab58923e9dfe526e5f7ee54e59f`
并得到局部 `INFEASIBLE`。该 root 同时含两个未登记的 `sources/__pycache__/*.pyc`，
所以只能声明“receipt 登记的 byte graph 通过”，不能声明完整 root 已闭包或封存。
该历史 producer/replay root 保持原样，禁止删除、补写或就地修复；v2 replayer 对它稳定返回
`ROOT_CLOSURE_CONTRACT_MISSING`。

## 隔离运行与 replay

从已提交且 clean 的源码 HEAD 运行：

```bash
D6_PYTHON=.venv-uvbolt-backup/bin/python3.13
"$D6_PYTHON" -I -B docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py \
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
`configuration.json` 与 `certificate.json`。producer 在创建 run root 前验证当前解释器确由
`-I -B` 约束，gate import 与后续 replay 均不得在 producer root 写入 bytecode/cache。

v2 `receipt.json` 内嵌 `research_artifact_root_manifest_v1`。manifest 按 path 排序，精确登记
除固定终端 `receipt.json` 外的全部后代 path/type；`receipt.json` 是协议唯一允许的额外普通文件。
W0 D6 还要求 manifest 的目录集合恰好等于全部命名 artifact 路径的祖先目录闭包；即使空目录
已被 manifest 登记，只要不承载任何命名 artifact 也必须拒绝。
producer 在写回执前验证 manifest 等于完整 root，写回执后再验证
`manifest + receipt.json` 等于完整 root，并重新读取命名 byte graph 与 receipt identity。回执不登记也不保存自身内容哈希；producer 只在
stdout summary 中报告写后观察到的 receipt identity。该合同是验证时的精确集合观察，不是
文件系统级不可变封存。

独立 replayer 是 stdlib-only、solver-free 的自包含实现，不导入 gate、runner、G3、`src/`
或 OR-Tools。第一次 replay 使用 producer 的 coherent CPython 3.13 环境；第二次使用
`/usr/bin/python3`、fresh `/tmp` cwd 与独立输出位置，构成异构 replay。两份 replay receipt
必须逐字节相同，且都写在 producer root 外：

```bash
D6_RUN_ROOT="$(realpath .artifacts/research_runs/w0-d6-<run-id>)"
D6_REPLAY_SIBLING="$(realpath -m .artifacts/research_runs/w0-d6-<run-id>-replay)"
mkdir "$D6_REPLAY_SIBLING"
"$D6_PYTHON" -I -B "$D6_RUN_ROOT/sources/replay_d6_certificate.py" \
  --run-root "$D6_RUN_ROOT" \
  --output "$D6_REPLAY_SIBLING/replay_receipt.json"

D6_TMP_REPLAY="$(mktemp -d /tmp/w0-d6-replay.XXXXXX)"
(
  cd "$D6_TMP_REPLAY"
  /usr/bin/python3 -I -B "$D6_RUN_ROOT/sources/replay_d6_certificate.py" \
    --run-root "$D6_RUN_ROOT" \
    --output "$D6_TMP_REPLAY/replay_receipt.json"
)
cmp "$D6_REPLAY_SIBLING/replay_receipt.json" "$D6_TMP_REPLAY/replay_receipt.json"
```

replayer 只接受 run-copy source，并在解释 status 前、命名字节/语义复算后再次验证完整 root。
未登记普通文件、目录、symlink、特殊节点、缺失/非普通 `receipt.json`、manifest 路径逃逸或
历史 v1 合同都 fail closed。所有 status 都复核完整 byte graph；只有 `FEASIBLE` 进入
body/front/incidence/crossing、cycle role、flow 与 graph reachability 的语义复算。replay
结束前还会按最初绑定的 root identity 重读所有命名 bytes 与 receipt。replay receipt v2
可保存其从外部观察到的 producer receipt identity；这不是 producer receipt 自哈希。
replay 成功仍只确认 receipt 声明的局部范围，不提升其 authority。

## 可信执行顺序

root-closure 修复提交及静态验收完成后，solver 执行继续等待 Endfield 完全退出。Endfield 不在场，
且资源、竞争 solver、项目锁与 clean committed HEAD 检查全部通过时，按常驻路线授权自动执行，
无需再次等待 owner 批准：

1. 用新 no-overwrite producer/replay roots、原三份 pinned 输入和原 solver config
   `workers=2, random_seed=0, max_time_seconds=3600` 强制重跑 `seed_narrow`；
2. 用 producer 的 coherent CPython 3.13 环境执行 root 内 pinned replayer，再从 fresh `/tmp`
   cwd 用 `/usr/bin/python3 -I -B` 做第二次异构 replay；两份 canonical replay bytes 必须一致；
3. `FEASIBLE`：交付局部 certificate 与异构 replay，停止，不运行 28-slot；
4. `UNKNOWN`、中断、运行失败、root closure/replay 失败或 status 分歧：停止并修复同一
   seed-narrow 链，不放宽 attachment scope；
5. 只有 replay-accepted `INFEASIBLE` 才自动运行 `all_legal_d6_slots`；保持同一 clean HEAD、
   输入和 solver config，唯一放宽项是 attachment scope。该变体的预期 antecedent SHA-256 为
   `a5fc8a3a3814970f2401d4c27800e422f8cb46cd358b6d07451f9935f76ddef3`。

H20 row-power oracle、G4 巨型核心拆分和全图 solve 均不在该序列内，继续后置。
