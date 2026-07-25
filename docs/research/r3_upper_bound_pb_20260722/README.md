# Track B/B0：R3 `(1190,34)` 算术层的 PB/VeriPB 链

> 本目录是纯研究路径。它只机器验证“给定 R3 几何引理后，全部
> `lex(area,min_side) > (1190,34)` 的尺寸均违反导出的必要不等式”。它不证明
> R3 几何引理、不提供 witness、不证明 `(1190,34)` 可达，也不建立全局最优性；
> 不接触 sealed/frozen/reseal 或 production authority。

## 1. 信任分层与账本

本件将上界链严格分成两层：膜与供电光环的离散几何论证由
`cleanroom_rederivation_20260718/11_r3_adversarial_verdict_20260720.md`
的对抗复核及 `verify_r3_certificates.py` 的独立复算背书；本目录的 OPB、
RoundingSat proof 与 VeriPB 只承担其后的有限整数算术。

上下界账本保持隔离：

- `U: (1190,34) -> (1190,34)`；数值不变，只增加算术层机器验证证据；
- `L: absent`；Track W 的 W2d 失败报告没有产出布局或下界；
- B1 未开始。

正式输入固定为 strict external 四文件闭包。核心 instance SHA-256 为
`e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`。
encoder 与 translation gate 分别重算，而不是信任 strict 内附的 sentinel：266 个
required、219 个 manufacturing、required body area 3,544、powered body area
3,325、628 个 active terminal（316 output + 312 input）、17 个 operation group、
19 种商品、1,804 个 required-instance physical port，以及 pole body area 4。

## 2. 给定引理后的算术

膜类表按 `(接触侧长度, 单机最多活跃制造端口)` 为：

```text
(3,1):155  (3,2):12  (3,3):11  (5,1):32
(5,2):17   (6,3):32  (6,4):3   (6,5):3
```

它给出 excess 63；四边端点修正为 24，因此制造/边界仓端口膜计数
`K <= w+h+43`。协议核心与两个 final input 再给宽松的 `+5`，得到
`U <= w+h+48`。628 个 active terminal 中，矩形外的 terminal incidence 至少为
`580-w-h`；同一 body-free access cell 最多承载四个正交 incidence，所以矩形与
外部接驳格共同要求

```text
wh + ceil((580-w-h)/4) <= 1320.
```

右端来自独立供电光环证书：14 个 doubled-weight orbit 项的单杆 stencil 总权为
396，840 个可能的制造机相对 placement 全部满足局部不等式，从
`3325 <= 396P` 得 `P>=9`，故可供空矩形和 body-free access cell 使用的格数至多
`70^2 - 3544 - 9*4 = 1320`。

encoder 与独立 gate 都枚举全部 oriented `6<=w,h<=70`。lex-better band 是
`wh>1190`，或 `wh=1190 and min(w,h)>34`。枚举结果必须为：

- 2,074 个 oriented 尺寸；
- 面积 1,190 的全部 oriented 因子对只有 `(17,70)`、`(34,35)`、
  `(35,34)`、`(70,17)`，均不通过 tie-break；
- 没有尺寸满足上述必要不等式；
- 左端最小值为 1,322，只在 `(19,63)` 与 `(63,19)` 取得。

## 3. 透明 OPB 与独立翻译门

每个 band 尺寸有一个 Boolean selector。OPB 只有一条 exactly-one 等式和每个
selector 一条线性蕴含：

```text
sum(x_w_h) = 1
(1320 - (wh + ceil((580-w-h)/4))) x_w_h >= 0
```

`w`、`h` 与 `wh` 都在生成期变成固定整数；模型不含 `W*H` 非线性、隐藏
big-M 或优化目标。预期规模为 2,074 variables、2,075 constraints、1 equality、
`intsize=64`。

`verify_r3_upper_bound_pb_translation_v1.py` 不导入 encoder 或
`verify_r3_certificates.py`。它独立重建 strict 账、膜/光环证书、band、dense
variable map 和完整 OPB constraint multiset；只有所有 checks 为真、missing 与
unexpected 均为 0 且 `corpus_errors=[]` 才输出 `PASS`。边界、tie-break、ceil、
类表、端点、incidence cap、halo 与 OPB reseal 均有 mutation canary。

## 4. 漏斗、资源与复现入口

固定解释器为：

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
```

执行顺序不可跳级：`estimate -> encode/build-only -> independent gate -> formal
gate byte-exact replay -> one RoundingSat run -> VeriPB 3.0.2`。estimate 的 proof planning bound 为
`max(512 MiB, 1024 * projected OPB bytes)`；5,000,000,000-byte proof cap 或
10,737,418,240-byte 磁盘低水位任一不满足即停止。

正式 worker 必须独占运行，并在同一 cgroup 中精确满足：

```text
MemoryHigh=35G
MemoryMax=39G
MemorySwapMax=16G
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
```

runner 还会钉住真实 RoundingSat/VeriPB 的绝对路径、binary hash、RoundingSat
source revision/cleanliness、固定 Python 解释器与 VeriPB 3.0.2 版本，持续采集
proof size、df、cgroup memory/swap/events，并在每个 child 运行中复核其 cgroup，
在 solver/verifier 前后复核 formula、proof、输入、源码和工具哈希。RoundingSat
成功必须同时具备唯一 `s UNSATISFIABLE`、本次新生成且尾部完整的 proof；VeriPB
成功必须具备唯一 `s VERIFIED UNSATISFIABLE`，二者的退出码与原始 stdout/stderr
照实归档，不能单凭退出码认定。信号、timeout、proof cap、磁盘低水位、cgroup
迁移、OOM event、残留进程组或任一哈希漂移均关闭 claim。每次结束另写
`SHA256SUMS`，覆盖 record/manifest 自身之外的全部原始工件；record 内钉住该
manifest。fake tool 只能用于单元测试内部控制流，不能通过正式 preflight。

## 5. 正式工件与结果

唯一正式 attempt `a001` 已于 2026-07-21 22:11 UTC 在以下 no-overwrite 目录成功
完成，reservation 已持久消费，不重跑：

```text
.artifacts/track_b_b0_1190_34/
  preflight-20260721T220937Z-398f8725/
  formal-a001-20260721T221107Z-398f8725/
```

独立 gate 为 16/16 PASS，`corpus_count=2074`、`corpus_errors=[]`、constraint
multiset missing/unexpected 均为 0；正式 worker 在 solver 前重跑 gate，结果与初次
报告逐字节相同，SHA-256 均为
`8ed3b07a8eedd208960c49abec7b3f0bd5ed3c8cacde3305d29d221153476417`。

正式工具链的原始结果为：

- formula：54,876 bytes，SHA-256
  `cd578dd972dd1bf7609e5190aff2649c3ffdce0d123b7815c81ac63f6e5346e3`；
- RoundingSat：exit 0，stdout 唯一状态 `s UNSATISFIABLE`，stderr 为空；
- proof：39,271 bytes，SHA-256
  `a6a7df1cedaabeee7271fa624f8627e5f666c9c77859df4d697577eec305fe4f`，
  尾部为 `conclusion UNSAT : 4152` / `end pseudo-Boolean proof`；
- VeriPB 3.0.2：exit 0，stdout 唯一状态 `s VERIFIED UNSATISFIABLE`，stderr
  为空；formula/proof 在 verifier 前后哈希不变；
- `SHA256SUMS` 覆盖 17 个原始工件并经 `sha256sum -c` 全部通过，manifest
  SHA-256 为
  `9901f793201391eb7473c5035034b94847292c35fb367cab32a2c09cb557620c`；
  为避免哈希环，它不含自身和最终 record。`toolchain_record.json` 的独立 SHA-256
  为 `0d18e112ca4b55ba2a01ba36139f86a5bc163cd3001e189002aa2623c0c77b06`。

资源合同从 start 到 end 均为 35/39/16 GiB，全部 systemd/cgroup 与祖先门为真；
9 个 telemetry 样本的最低可用磁盘为 22,968,557,568 bytes，最大 proof 为
39,271 bytes，cgroup memory peak 为 35,717,120 bytes，swap 为 0，
`high/max/oom/oom_kill/oom_group_kill` 增量全为 0。所有 child 均留在同一精确
unit cgroup，结束后仅余 runner，进程组清理门全真。

验收时定向 pytest 为 18 passed；Ruff、`verify_r3_certificates.py` 与
`scripts/preflight_gate.py --full` 均通过。最终 record 的 claim 是
`machine_verified_lex_better_arithmetic_band_unsat_given_r3_geometric_lemmas`。
其含义严格限于：**给定 R3 几何引理，lex-better band 的算术层已经由
RoundingSat proof 和 VeriPB 3.0.2 机器验证为 UNSAT**。账本仍为
`U: (1190,34)`、`L: absent`；本件不证明 witness、可达性或全局最优性，B1
未开始，也不是 production CERTIFIED 材料。
