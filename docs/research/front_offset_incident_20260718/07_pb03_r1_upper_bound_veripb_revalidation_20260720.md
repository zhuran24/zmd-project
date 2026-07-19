# PB-03：R1 `(1326,34)` 上界的 VeriPB 重验闭环（2026-07-20）

> 本页记录纯研究路径上的 `encode -> translation gate -> RoundingSat proof logging -> VeriPB` 重验。它不接触 sealed 面、不修改 frozen 工件、不 reseal，也不把研究结论写成 production `CERTIFIED`。

## 0. 结论与两段式论证

PB-03 本次重验已经闭环：独立 translation gate 14/14 PASS，RoundingSat 以 exit 0 产出完整 UNSAT proof，VeriPB 3.0.2 以 exit 0 验证为 `s VERIFIED UNSATISFIABLE`。这是项目第一条从严格研究输入到 VeriPB 的完整 PB 证明链。

完整的 R1 严格版 `(1326,34)` 上界引理由两段互补论证组成，必须分开阅读：

1. **带外初等排除，不在 OPB 内。** 对所有 lexicographically better 且面积 `>1348` 的有向尺寸，严格输入给出的必要 body area 为 3,544；219 个受电实体在单 pole 最多覆盖 144 个 body cell 的条件下至少需要 2 根 pole，每根 pole body area 为 4。因此自由格上限为

   `4900 - 3544 - 4 * 2 = 1348`。

   面积大于 1,348 的矩形由此直接不可能；独立枚举中这一段含 1,763 个有向尺寸。它是自由格上限引理的初等推论，**不由本 OPB / VeriPB 证书承担**。

2. **带内 PB 排除，由本证书承担。** 在面积 `<=1348` 的 lexicographically better 尺寸中，独立枚举恰剩 22 个有向尺寸。本 OPB 枚举 47 个边界模式及这些尺寸的全部合法锚点，并由 translation gate 独立重建后，交给 RoundingSat 产出 proof log，再由 VeriPB 核验。证书的精确覆盖面只有这 22 个带内有向尺寸。

两段合并，才覆盖全部 `1,763 + 22 = 1,785` 个 lexicographically better 有向尺寸，从而得到完整 `(1326,34)` 上界引理；任一段单独都不等价于完整引理。

## 1. 基线、输入与模型

本轮锁定 Git 基线为 `07d2e3fd2c0de52605a8191b43872bafaba3f3d1`。其后 roadmap/历程叙事提交不属于 PB 语义基线，未追随。正式记录同时钉住当时 tracked diff SHA-256 `f0d5d5f8e1513b07bad366056ef51de5e5460f4ef3665d13f997a018bb0bd115` 与 `git status --porcelain=v1 -z --untracked-files=normal` SHA-256 `d6a0aa34e438e05ce09c0bc49ed53e4215a231d1c7e8f23758b0c243b3b5a015`；estimate、metadata、gate、runner 三处完全一致。

编码器只读取 `cleanroom_rederivation_20260718/strict/external` 的四文件闭包，以及 04、05 号研究记录与 `verify_r1_strict_bounds.py`。没有读取 sealed candidate pool，没有修改 frozen 工件。关键输入钉值如下：

| 输入 | SHA-256 |
| --- | --- |
| `problem_instance.json` | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` |
| `problem_instance.schema.json` | `5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23` |
| `problem.md` | `c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f` |
| `SHA256SUMS` | `8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70` |

### 1.1 residual-band OPB

22 个有向尺寸为：

`(20,67), (21,64), (22,61), (23,58), (24,56), (28,48), (29,46), (31,43), (32,42), (35,38), (36,37), (37,36), (38,35), (42,32), (43,31), (46,29), (48,28), (56,24), (58,23), (61,22), (64,21), (67,20)`。

编码变量由 47 个边界模式选择量与 16,702 个矩形放置选择量组成，共 16,749 variables。OPB 有两条 exactly-one 等式；对每个放置 `R`，加入

`sum_delta |R intersect Q_delta| * p_delta - 46 * r_R >= |R| - 1348`。

当 `r_R=1` 且某个 `p_delta=1` 时，它恰好要求 `|R union Q_delta| <= 1348`。因此该式只编码自由格上限下矩形与 46 个被迫 connector cell 共存的必要条件。模型规模为 16,704 constraints（其中 2 equality、16,702 placement constraints），非零 overlap 项 62,792；OPB 为 936,597 bytes，header 是 `#variable=16749 / #constraint=16704 / #equal=2 / intsize=64`。

## 2. proof-size 预估与资源合同

scratch 侦察只在仓外临时目录进行，正式工件前已经清理；它观测到 proof 约 25.5 MB。正式 estimate 没有把观测值直接当硬保证，而是向上取整为 512 MiB（536,870,912 bytes）保守 planning envelope。它低于 5,000,000,000-byte 放弃阈值，故 decision=`GO`；OPB 在此之后才编码。estimate SHA-256 为 `52316a7441be550079a92a6e12e5d59ae633b76d308a382a85a9686739596c99`。

正式 solve 只启动一次，systemd unit 为 `pb03-r1-1326-34-20260719t203012z.service`，合同为：

- `MemoryHigh=34G`，cgroup 实值 36,507,222,016 bytes；
- `MemoryMax=38G`，cgroup 实值 40,802,189,312 bytes；
- `MemorySwapMax=16G`，cgroup 实值 17,179,869,184 bytes；
- `OOMPolicy=continue`；
- proof runtime cap 5,000,000,000 bytes，磁盘低水位 10,737,418,240 bytes；
- solver internal time limit 300s、solver wall timeout 330s、verifier wall timeout 300s。

runner 在子进程运行中与退出瞬间都复查 proof size 与可用空间。11 个采样点的最低可用空间为 28,606,607,360 bytes；proof 从 0 增长到 25,496,266 bytes。cgroup `memory.peak=111,013,888` bytes，start/end 的 `high/max/oom/oom_kill/oom_group_kill` 全为 0；没有 cgroup high/max/OOM 事件混淆终态。runner 本版没有采集 `memory.swap.current`，因此不对实际 swap 用量另作断言。

## 3. translation gate

`verify_r1_upper_bound_pb_translation_v1.py` 不导入编码器或历史 PB harness。它从严格 JSON 独立重算 47 个边界模式、22 个带内尺寸、16,702 个放置、dense variable map 与完整 constraint multiset，再解析实际 OPB 比对。正式 gate 结果：

- status=`PASS`，14 个必需 checks 全为 `true`；
- `constraint_diff.missing_total=0`、`unexpected_total=0`；
- expected/actual constraint-multiset SHA-256 同为 `37c020d2fbe3ff0ea383b99870e01e9ea36f7adaa79dae7473eff09f37661f50`；
- 穷举 `47 * 16,702 = 784,994` 个 pattern-placement 对，`corpus_errors=[]`；
- 最小 `|R union Q_delta|` 下界为 1,351，见 witness `[pattern=0, w=35, h=38, x=1, y=1, overlap=25]`，仍严格大于 1,348；
- d=3、共享中间格/set 语义、转置对称与 single-offset/double-offset canary 全通过。

gate SHA-256 为 `24b3fc52e06ef0edfc4122397bc6f301bc82988306dce60728d73821fb9cd7ba`。它只断言翻译和语义语料门通过，不自行冒充 solver proof。

## 4. RoundingSat 与 VeriPB

正式链由 `run_r1_upper_bound_pb_toolchain_v1.py` 在上述 systemd cgroup 内串行执行；solver 与 verifier 的完整 argv 都写入 `toolchain_record.json`。

| 阶段 | 结果 |
| --- | --- |
| RoundingSat | exit 0；唯一状态行 `s UNSATISFIABLE`；runner elapsed 0.401s |
| proof | 25,496,266 bytes；SHA-256 `1f709364af0c5d74802eaa7b2939b8d3b15c1fbfb7238f2c1757043d9a5b7dac` |
| proof tail | `conclusion UNSAT : 77527`，随后 `end pseudo-Boolean proof`；完整性门 PASS |
| VeriPB 3.0.2 | exit 0；唯一状态行 `s VERIFIED UNSATISFIABLE`；error markers 为空；runner elapsed 0.200s |
| hash stability | OPB 与 proof 在 VeriPB 前后哈希逐字一致 |

工具身份在运行前读取、写入 started record，并在运行后重算；只有完全稳定才允许 claim：

| 工具 | 身份 |
| --- | --- |
| RoundingSat binary | SHA-256 `08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf`；2,305,360 bytes |
| RoundingSat source | revision `d4edbf7908a9bb951fd181940919e0f3ac7ab1ee`；clean detached tree |
| VeriPB | version 3.0.2；SHA-256 `a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971`；3,317,320 bytes |

最终 `solver_declared_unsat=true`、`proof_tail_complete=true`、`veripb_verified=true`、`tools_stable=true`，runner claim 为 `machine_verified_residual_band_unsat_for_translation_gated_r1_upper_bound`。

## 5. provenance 与工件索引

no-overwrite 正式工件根：

`.artifacts/batch4_20260718/pb/r1_upper_bound_1326_34_v1/run-20260719T203012Z-07d2e3f/`

| 工件 | bytes | SHA-256 |
| --- | ---: | --- |
| `estimate.json` | 6,188 | `52316a7441be550079a92a6e12e5d59ae633b76d308a382a85a9686739596c99` |
| `r1_upper_bound.opb` | 936,597 | `1da46c8cfdbe81d1d5ca4b8e4dd21624288d3ab4da0e8b5eaaa8f43d1be3bde4` |
| `r1_upper_bound.meta.json` | 8,167 | `4765daa9adf6bb30d19e27e2bc89e07ec805110a06f80f4d9a92d80730546a30` |
| `r1_upper_bound.var_map.json` | 4,564,353 | `7341d2668116ecb8d84f8a46f98526f3be4b04a7d437fa7565083eb764929d8c` |
| `translation_gate.json` | 12,091 | `24b3fc52e06ef0edfc4122397bc6f301bc82988306dce60728d73821fb9cd7ba` |
| `toolchain-a01/roundingsat.proof.pbp` | 25,496,266 | `1f709364af0c5d74802eaa7b2939b8d3b15c1fbfb7238f2c1757043d9a5b7dac` |
| `toolchain-a01/resource_monitor.json` | 4,714 | `f3b71a606d3f345fb7338edf37fd52b80413a6513da7254f32b4125f43f77c34` |
| `toolchain-a01/toolchain_started.json` | 7,358 | `698d6163492172293bed2c9a38e178b29a0971be5ead2f03ccdd218f6c2ad533` |
| `toolchain-a01/toolchain_record.json` | 13,096 | `c0ac77cfd09b37513de19089f6ead5765c18e93017ebbb1537b85df495a702fc` |

`toolchain_record.json` 闭合记录 runner/solver/verifier argv，strict inputs、estimate、OPB、metadata、variable map、translation-gate JSON、三份 harness source、Git snapshots、工具 binary/repository 的运行前后身份、stdout/stderr、proof、resource monitor 的路径/bytes/SHA-256，以及 VeriPB 退出码和 claim boundary。三个 harness source SHA-256 分别为：encoder `8a6b06ba31361650d820da66766e8023e17840dd2f6927782b0c653da2c1204d`、gate `46724cb7b93e6c4dcdfcd7d932bf89087d652bee29754bbf8d304b1e1db89edf`、runner `115bbe67cba6a515f85bd570333b7dde03f534fb4f33a48d42de886f624a0880`。

## 6. 验收与 claim 边界

代码面验收：

- 新旧 PB 定向 pytest：`17 passed in 12.27s`；
- encoder / gate / runner / 新测试定向 Ruff：通过；
- R1 独立复算脚本：通过（47 patterns、1,182 unordered pairs、最优上界 `(1326,34)`）；
- 历史 `pb_encoder_v2.py`、`verify_pb_translation_v2.py`、`run_pb_toolchain_v2.py` 无改动；
- 未修改 `PROJECT_LOCK.md`、`rules/`、`data/` 或 sealed/frozen certificate 工件。

认识论边界必须保持如下措辞：

- `VeriPB verified` 表示上述哈希闭合 residual-band OPB 有一份**研究级机器可验证 UNSAT 证明**；
- 它不是 sealed `CERTIFIED`，不触发 freeze/reseal，也不进入 production authority；
- 它只恢复 PB-03 本次所承担的带内证明义务，不自动恢复任何其他历史 PB、RND 或 solver 判决；
- 完整 `(1326,34)` 引理仍明确依赖第 0 节的两段合取：带外 `area>1348` 靠自由格上限初等排除，带内 22 个有向尺寸才由本 VeriPB 证书排除。
