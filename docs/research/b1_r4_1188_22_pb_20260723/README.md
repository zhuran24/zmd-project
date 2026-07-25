# Track B/B1：R4 `(1188,22)` 候选的 proof-bearing 回归

| 文档属性 | 当前值 |
|---|---|
| 文档性质 | 当前终态研究报告 |
| 证据截止 | `2026-07-23` |
| 状态 | **VERIFIED** — 完整 lex-better band 已由 RoundingSat proof 与 VeriPB 3.0.2 验证为 UNSAT |
| 上界账本 | `U: (1190,34) -> (1188,22)` |
| 下界账本 | `L: absent` |
| build authority | `.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/` |
| formal authority | `.artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/` |
| detached receipt | `authority_receipt.json`，2,613 B，SHA-256 `0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2` |
| claim 层级 | research-only；不是 production `CERTIFIED` |

## 终态结论

本轮把 R4 response review 已准入的 `(1188,22)` 从
`encoder-design candidate` 升级为研究上界：

```text
U old -> new: (1190,34) -> (1188,22)
L: absent
```

唯一 formal attempt `a001` 的原始结果为：

- RoundingSat exit 0，stdout 唯一状态行 `s UNSATISFIABLE`，stderr 为空；
- proof 尾部为 `conclusion UNSAT : 4278` 与
  `end pseudo-Boolean proof`；
- VeriPB 3.0.2 exit 0，stdout 唯一状态行
  `s VERIFIED UNSATISFIABLE`，stderr 为空；
- formula 与 proof 在 verifier 前后哈希不变；
- detached receipt 在 systemd unit 退出后完成全语义只读重放，状态仍为
  `VERIFIED`，`upper_bound_update_authorized=true`；
- raw `toolchain_record.json` 自身保持 `claim=none`。研究 claim 只由绑定其精确
  字节的 detached receipt 发布。

这项结果的精确含义是：**给定固定 R4 `a004` admission 已准入的几何必要引理，
全部 oriented `6<=w,h<=70` 且
`lex(w*h,min(w,h)) > (1188,22)` 的尺寸选择不可满足。**

## 上游 authority 与信任分层

本轮唯一上游是：

```text
.artifacts/track_b_r4_external_brain_handoff_20260722/
  run-20260722T084343Z-R4hP1A/
  responses/run-20260723T023657Z-R4resp-357f260d/
    admission/a004/admission.json
```

`admission/a004/admission.json` 为 10,273 B，SHA-256
`2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff`。
encoder、translation gate 与 formal runner 均调用固定 admission closer 做完整
只读重放；它们不把外部回复代码当作验证实现。

信任边界分成两层：

1. `a004` 准入 ordinary membrane、conditional marked membrane、access-cell、
   power-halo 与 boundary full-span 几何必要引理；
2. 本目录的独立 translation gate、OPB、RoundingSat proof 与 VeriPB 只验证这些
   给定引理之后的有限尺寸算术。

strict instance 的核心 SHA-256 为
`e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`。
translation gate 不导入 encoder、旧 B0 encoder 或 R3 certificate 脚本；它从
strict bundle 与固定 `a004` authority 独立重推数量、几何算术、band 与完整 OPB
constraint multiset。

## 给定引理后的完整 band

对 `S=w+h`，每个候选矩形必须满足：

```text
w*h + max(
    ceil((580-S)/4),
    ceil((678-2*S)/4)
) <= 1320.
```

其中 `580` 来自 ordinary membrane 与 628 个 active terminal 的外部 incidence
账；`678` 来自 110 个 marked terminal、8 个 directed endpoints 与 12 的
inside offset；分母 4 来自逐 access-cell 的
`t(z)+m(z)<=4`。右端 `1320` 由
`4900 - 3544 - 9*4` 得到。fixed `a004` 还准入边界 23+23 / 69-of-70 packing，
因此任何 `w=70` 或 `h=70` 的 full-span selector 都被禁止。

独立枚举的终态为：

| 项目 | 结果 |
|---|---:|
| oriented lex-better 尺寸 | 2,084 |
| area `1188` 且通过 tie-break 的 oriented 尺寸 | `(27,44)`, `(33,36)`, `(36,33)`, `(44,27)` |
| full-span 尺寸 | 107 |
| 仅通过算术不等式的尺寸 | `(17,70)`, `(70,17)` |
| full-span closure 后幸存尺寸 | 0 |
| 非 full-span 最小左端 | 1,322，于 `(27,44)` / `(44,27)` |

## 透明 OPB 与 translation gate

每个 band 尺寸对应一个 Boolean selector。OPB 包含：

- 1 条 exactly-one selector 等式；
- 2,084 条固定系数的算术蕴含；
- 107 条 full-span selector forbid；
- 合计 2,084 variables、2,192 constraints、1 equality、`intsize=64`。

`w`、`h`、`w*h` 与两个 ceiling 值都在生成期化为整数；公式没有
`W*H` 非线性、优化目标或隐藏 big-M。独立 gate 的 20 个 closed checks 全真，
`corpus_errors=[]`、OPB parse errors 为空，constraint multiset 的 missing 与
unexpected 均为 0。formal worker 在 solver 前重新生成 gate，所得报告与 build
中的 `translation_gate.json` 逐字节相同。

## Authority 工件

### Build-only authority

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `estimate.json` | 13,231 B | `0a8bdfd6a3b38e9aa4085942788240087a7db335d05583447a7d02004521786b` |
| `formula.opb` | 56,881 B | `9ce8f110757ecf87af888ed7fd2fbc334eecaf2e1a9be784a8a1b5dc8f3435d8` |
| `encoder.meta.json` | 15,390 B | `f304342bd6b1ac51b8be5dc0c4c6d439dfde06b667fec3c8fd7928f714d73c3d` |
| `variable_map.json` | 967,694 B | `877fe9ee63e96bb616761b8c1719fde40d5fe14a9eaf852adce747275830c028` |
| `translation_gate.json` | 10,332 B | `0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602` |
| `SHA256SUMS` | 942 B | `652a7bdf5bab1488e40fa1bce6eab18e59437f038acef0d7b3f39b197c74771a` |
| `build_record.json` | 11,982 B | `4f8124c582d0c4134538abd2574f2f2ebb3fb5eeb56f0aba7fb1d760fc72f886` |

Build manifest 精确覆盖 11 个 immutable payload 文件；manifest 与
`build_record.json` 为避免哈希环而在单向闭包中分层。正式 runner 独立解析
manifest、重放 build record 的完整 argv、source/Python identity、三次 child
结果与全部输出 identity。

### Formal authority

| 工件 | 大小 | SHA-256 |
|---|---:|---|
| `formula.opb` | 56,881 B | `9ce8f110757ecf87af888ed7fd2fbc334eecaf2e1a9be784a8a1b5dc8f3435d8` |
| `roundingsat.proof.pbp` | 39,446 B | `54c4b9c61f7a4505808e8cad895c863ca8579400e3df83e7e7c8d269d0504531` |
| `resource_monitor.jsonl` | 6,773 B | `cb241cffe7b79d57b9d2d6f3f89e1e5b632f5e459d224986d8280c48e8c4e2c5` |
| raw `SHA256SUMS` | 1,795 B | `8049f487106735c5d133d8c5998bd669eedca46e28dd4bef46714aac88d2c8ca` |
| `toolchain_record.json` | 154,545 B | `b99c9dd62b9be3c06de93d125bd2feaadc761f9eb541eb3d39a72070f33314f3` |
| `authority_receipt.json` | 2,613 B | `0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2` |

Raw manifest 精确覆盖 20 个 solver 前后原始工件，并固定排除自身、最终 record 与
detached receipt。Receipt 绑定 raw manifest、record、persistent reservation、
reservation copy、build record/manifest、formula 与 proof 的 path/size/SHA。
Receipt 自身的 detached path/size/SHA 由下游重放参数携带，避免自哈希环。

## 工具与资源合同

正式工具 identity 为：

| 工具 | 固定 identity |
|---|---|
| Python 3.13 | SHA-256 `74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb` |
| RoundingSat | SHA-256 `08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf`；clean revision `d4edbf7908a9bb951fd181940919e0f3ac7ab1ee` |
| VeriPB | version `3.0.2`；SHA-256 `a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971` |

唯一 worker 在同一 cgroup 中满足：

```text
MemoryHigh=35 GiB
MemoryMax=39 GiB
MemorySwapMax=16 GiB
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
```

11 个 telemetry 样本记录的最低可用磁盘为 33,990,295,552 B，最大 proof 为
39,446 B；cgroup memory peak 为 44,093,440 B，swap 为 0。
`high/max/oom/oom_kill/oom_group_kill` 增量均为 0。所有 child 均在指定 unit
cgroup 内，结束后仅余 runner，进程组清理门全真。

## 验收与复现

定向测试为 29 passed；相关 authority/preflight 回归为 189 passed；最终 full
preflight 为 `19 passed`，其中 pytest 为 4,864 passed、74 skipped。Ruff
check/format、direct external-artifact check、direct secret scan、build authority
replay、translation gate replay、同配置 cgroup preflight 与 detached receipt
replay均通过。

完整 build/formal 顶层 argv、可执行 detached receipt replay、主要验收命令及
原始结果摘要见
[`03_execution_record.md`](03_execution_record.md)。所有 authority 目录均为
no-overwrite；`a001` reservation 已持久消费，不得重跑。

## Claim 边界

本轮建立的是 research upper ledger `U=(1188,22)`。它不建立：

- witness 或任何 feasible lower bound；`L` 仍为 absent；
- `(1188,22)` 的 attainability；
- global optimality；
- whole-instance infeasibility；
- production `CERTIFIED` 语义；
- `a004` 几何必要引理在 PB proof 内部的再次证明。

本轮到此停止，不自动延伸到下一个 upper candidate、Track W 或其他 solver/search
路线。
