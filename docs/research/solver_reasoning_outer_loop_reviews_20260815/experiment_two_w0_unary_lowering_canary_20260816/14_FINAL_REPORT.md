# W0 一元 lowering 金丝雀最终报告

> **运行日期：** 2026-08-16
> **冻结判词：** `INCONCLUSIVE`
> **协议冻结提交：** `0339c745b6c7f498fc989398de380a78578fc785`
> **实现提交：** `c2b240eb2e64014c3dabfb87ef5f68263063380f`
> **运行 ID：** `w0-unary-canary-r1-20260816`
> **性质：** `research_only / non_authorizing`

## 1. 判词

本实验没有证明 W0 theorem 已在真实系统中成功消灭一号 family，也没有证明 lowering 无效。

精确结论是：

1. theorem 到 CpModel 的一元 lowering **结构上 sound**，独立 checker 证明其拒绝集合与 `Active_041` trigger 精确等值；
2. endpoint evaluator 的 11 个正控、负控和 stale 控制全部 PASS；
3. observer-noop 不改变 baseline 的 selection 序列、死因谱或资源量级；
4. treatment 在模型构建后把目标 slot 的有效可选值从 3 收到 1，但第一次 binding solve 在冻结 20 秒内返回 timeout，未产生任何 binding proposal；
5. 因为 treatment 没有达到 baseline 的 1007-proposal 里程碑，也没有获得 FEASIBLE／INFEASIBLE 终态，所以不存在可比较的系统效果观测。

因此，treatment 中 `J-trigger=0` 是**零份 proposal 上的零**，不是“1007 循环已被真实系统成功塌缩”的证据。协议据此给出 `INCONCLUSIVE`。

## 2. 三臂结果

| arm | terminal | censor | proposals | J-trigger | routing solves | wall |
|---|---|---|---:|---:|---:|---:|
| `A_BASELINE` | `UNKNOWN` | `EVENT_CAP_REACHED` | 1007 | 1007 | NOT_REACHED | 342.699 s |
| `B_OBSERVER_NOOP` | `UNKNOWN` | `EVENT_CAP_REACHED` | 1007 | 1007 | NOT_REACHED | 341.098 s |
| `C_UNARY_LOWERING` | `UNKNOWN` | `SOLVER_TIMEOUT_BINDING` | 0 | 0 | NOT_REACHED | 21.209 s |

A/B 的 ordered selection digest 均为：

```text
33851502e1c74cfab135beb4551c61367048558612c17696ecdbe6ea1b54b6b9
```

两臂完全复现冻结谱：

```text
front_blocked = 1007
signature 4e4e... = 1001
signature b7a8... = 3
signature 0d81... = 3
point nogood = 1007 × 285 literals = 286,995 literals
routing solve = 0
```

B 相对 A 的墙钟差为 `-0.467%`，在冻结 15% observer 容差内；trigger evaluator 对 1007 个 selection 的累计成本为约 `0.000204 s`。因此 observer 本身没有可见扰动。

C 只调用了一次 binding solve，耗时约 `20.079 s` 后被单次 solve cap 截断。它没有进入 routing precheck，也没有生成 event 或 feedback。

## 3. lowering 合同

独立 proto checker 从 baseline 与 treatment snapshots 重算：

| 项 | baseline | treatment |
|---|---:|---:|
| variables | 17,190 | 17,190 |
| constraints | 289 | 290 |
| target slot model labels | 3 | 3 |
| target slot effective allowed values | 3 | 1 |

唯一新增约束：

```text
name = w0_j041_force_unused
variable = slot_boundary_port_041:out:0___unused__
coefficient = 1
domain = [1,1]
```

pre-existing target `ExactlyOne` 的 constraint index 为 273。原变量、原约束顺序、search strategy、objective、assumptions、hint 与 symmetry 全部不变。

独立判词：

```text
PASS
RejectSet(lowering) = Active_041 trigger set
```

所以当前删失不能归因于 lowering 越权或编译错位。

## 4. 四格账

| 层级 | 语义／搜索状态 | 资源／执行轨迹 |
|---|---|---|
| 切面 | target 的 `BOX_DOMAIN` 有效值 3→1；A/B 证明原 1007 proposals 全部属于 theorem trigger；C 没有 proposal，不能观测运行时 family coverage | A/B 各约 341–343 s，98.6% 左右 measured stage cost 在 binding solve；C 把全部 measured solve cost集中到第一次 binding solve 并在 20 s 被截断 |
| 终点 | `ΔL=ZERO_BY_SCOPE`；`ΔU=ZERO_BY_SCOPE`；`L=ABSENT`，故 `M_t=N_A_NOT_READY`；`ΔM=ZERO_BY_SCOPE` | C 与 A/B 没有共同 terminal／proposal milestone，21.209 s 不能与 341 s 解释成 93.8% 加速；endpoint resource 判词为 `INCONCLUSIVE` |

运行前后的 durable exact status、stable claim ledger、research upper-ledger evidence、`PROJECT_LOCK.md`、supervisor seal 源码、certified publisher 源码和 public runtime paths 身份完全一致。终点中性是 scope non-interference，不是本轮测得的 bounds 零收益。

## 5. 这次真正看见了什么

### 已看见

- 一条已证 Judgment 可以被编译成一个不越权的一元 CpModel 约束；
- 新增约束在表示层确实把 target slot 的有效取值缩到 `__unused__`；
- 现有 observer 可以在不扰动 selection 轨迹的情况下记录 theorem trigger；
- endpoint evaluator 已完成接线自测；
- baseline 的 1007 点状循环及其成本递增被再次精确复现。

### 没看见

- treatment 的第一份非 J binding selection；
- treatment 的 binding FEASIBLE 或 INFEASIBLE 终态；
- routing 热点是否接替 binding；
- 1007 点状循环在真实执行轨迹上被一条 family constraint 因果替代；
- endpoint compute gain；
- 跨布局普遍性、通用 compiler 或 certified-exact 上下界进展。

这次最重要的现象不是“定理没用”，而是：

> 原路径能快速连续找到大量 doomed assignments；加上一条 sound unary constraint 后，求解器在残余域中的第一次存在性／不可行性判断变成了 20 秒内无终态。

这正是“删掉 cheap-to-refute family 后，证明成本可能迁移到残余域”的实测形态。因为 treatment 被删失，当前不能判定残余域是可行但难找、不可行但难证，还是仅由现有 fixed search 表示造成的困难。

## 6. 决策边界

按冻结协议，`INCONCLUSIVE` 只允许：

- 修正实验装置中阻止形成共同里程碑的部分；或
- 新建 v2 协议，预注册更小的可比里程碑、有限域 slice 或 solve-cap ladder。

它不购买：

- 第二条 theorem 的真实 lowering；
- 跨布局 family holdout；
- 通用 D3/D4 解冻；
- production default；
- theorem registry 常态化；
- certified 或 release surface 变化。

若后续另获 owner 信号，最有判决力的下一问不是重复 1007-loop A/B，而是：

> 在 `boundary_port_041=__unused__` 的残余 binding 域中，能否用独立、有限且预注册的办法判定“存在可行 binding”还是“该残余域不可行”，并测量其证明成本？

该问题必须另冻 v2，不得回改本次 `INCONCLUSIVE`。

## 7. 证据身份

Local-optional evidence root：

```text
.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/
```

顶层 evidence manifest：

```text
SHA-256 = 4cc99e4a505d6ea72f41c963c984b03f21d403c1b285730d7be0a3a113bd206a
files checked = 36
run EXIT_CODE = 0
run .DONE = present
```

独立 post-run checker：[`12_check_canary_run.py`](12_check_canary_run.py)。

Tracked compact receipt：[`13_RUN_RECEIPT.json`](13_RUN_RECEIPT.json)。该 receipt 由纯标准库 checker 从 artifact journals、snapshots、endpoint receipts 和 manifest hashes 重新推导，最终结果为：

```text
checker status = PASS
scientific verdict = INCONCLUSIVE
```

checker PASS 只说明证据包自洽和冻结判词被正确重算，不把科学判词升级为 PASS。
