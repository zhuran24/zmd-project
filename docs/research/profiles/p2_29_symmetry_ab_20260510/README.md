# P2 #29 对称性级别 A/B 实验（2026-05-10）

测试 CP-SAT `symmetry_level` 参数从项目默认强化的 `=3` 改成 `=0`（关闭）的开销变化，看路线图 #29 提议是否成立。

## 背景

P1 #20 短跑 profile 显示 CP-SAT 对称性检测占 master 求解 ~3% CPU 时间。git blame 显示项目从 Codex 时代起就**主动强化** `symmetry_level=3`（CP-SAT 最高级），覆盖默认 `=2`。原因没在 commit 历史里，只 1 个 initial migrate commit。

项目已经做过手动对称性破坏（grouped encoding + signature monotonic，R2 round audit `a96266f5aed302928` 说 99% 已覆盖）。所以猜测：CP-SAT 内部 detection + orbital fixing 是冗余先验，关掉应该正向。

## 实验配置

A/B 都用 `scripts/profile_short_run.sh`，参数完全相同：
- py-spy: `record --native --subprocesses --rate 100 --duration 600`
- main.py: `--campaign-hours 0.2 --parallel-processes 1`
- 主机环境: 13900KS / CachyOS / cmdline 含 mitigations=off + isolcpus=0-7 + nohz_full=0-7 / PPD performance / HWP boost

A baseline:
- env 不设 → 项目默认强化 `symmetry_level=3`
- 复用 P1 #20 part 1 的 profile（`profile_20260510_041840/`）

B experiment:
- `EXACT_MASTER_SYMMETRY_LEVEL=0`
- profile: `profile_20260510_050748/`

## 实验结果

### 对称性相关函数 sample 数变化

| 函数 | A (`=3`) | B (`=0`) | 变化 |
|---|---|---|---|
| `FindCpModelSymmetries` | 1.23% | **0.00%** | -1.23% |
| `DetectAndExploitSymmetriesInPresolve` | 1.25% | **0.00%** | -1.25% |
| `GraphSymmetryFinder::FindSymmetries` | 0.78% | **0.00%** | -0.78% |
| `GraphSymmetryFinder::RecursivelyRefinePart...` | 0.75% | **0.00%** | -0.75% |
| `DetectAndAddSymmetryToProto` | 0.40% | **0.00%** | -0.40% |
| `GenerateGraphFor...` | 0.39% | **0.00%** | -0.39% |
| **小计** | **4.80%** | **0.00%** | **-4.80%** |

env override 真的关掉了所有对称性检测代码路径。省下的 ~4.8% CPU 时间被以下工作吃掉：

- `build_exact_core` (master_model.py:2358) +1.47%
- `IntegerEncoder::~IntegerEncoder` +1.42%（CP-SAT 整数编码销毁）
- `Model::Delete` +1.42%
- jemalloc 分配释放函数群 多个 +~1.3%
- `LinearProgrammingConstraint` +1.31%（线性松弛 / LP 求解）
- `UsedVariables` +1.25%

## Caveats（实验局限）

1. **A/B 两次 master iteration 1 都 status=UNKNOWN**（CP-SAT 600 秒内没解出 70x70 实例的 master）—— 没法比较 search 收敛速度差异。
2. **没有 cert hash 比较** —— 因为没出解。不知道关闭对称性检测后求解结果是否仍正确。
3. **单 worker 跑** —— 不反映生产 4-worker 配置下的真实分布。

## 判定与建议

### 已验证

- ✅ `EXACT_MASTER_SYMMETRY_LEVEL=0` 这个 env override 在项目当前代码里**真的生效**
- ✅ 关掉对称性检测真的省 ~4.8% master CPU 时间（比 audit 估的 3% 还多 60%）

### 待真长跑验证

- ⚠ 关掉对称性检测后 search 完备性是否受影响（项目手动 breaking 是否真覆盖了所有相关对称性）
- ⚠ 多迭代后 incumbent 质量差异
- ⚠ master 真正解出实例的 wall time 差异

### 建议

**保留默认强化 `symmetry_level=3` 不动**。短跑数据看到机会但不足以做生产决策。

168h 真长跑启动后做完整 A/B：
- 同时跑 2 个 worker process，一个 baseline 一个 `EXACT_MASTER_SYMMETRY_LEVEL=0`
- 比较第一个 incumbent 出现时间 + 多 iteration 后 best feasible 的差异
- 如果 `=0` 不退化，常驻设到 `~/.claude/CLAUDE.md` 的"168h campaign 启动 wrapper"里

或者更保守：试 `EXACT_MASTER_SYMMETRY_LEVEL=2`（CP-SAT 真默认），跟 `=3` 比较看 Codex 时代的强化决策是否真值得。

## 文件清单

- `B_symmetry0_flamegraph.svg` —— B 实验火焰图（symmetry_level=0）
- `B_symmetry0_main.log` —— B 实验 main.py 日志
- A baseline 数据复用 `../p1_20_short_profile_20260510/`
