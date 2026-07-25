# Cuts credibility 与真实 A/B 强制排期

| 项目 | 合同值 |
|---|---|
| 合同日期 | `2026-07-24` |
| 文档性质 | SMM3 后续强制排期，不是 cuts 执行结果 |
| 触发点 | SMM3 terminal acceptance 完成 |
| 下一项强制任务 | `CUTS_GATE1_V4_AUTHORITY_COMPLETION` |
| 独立 worktree | `/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723` |

## 1. 排期地位

cuts线不是“不应该做”，也没有被放弃。Gate 1 v3的停止只表示：缺少可信
authority root时，不得继续追加实验代次。它不构成cuts无效证据。

SMM3先完成，因为它是一次有界的上界更新尝试，而且其supervisor/keeper
两阶段采证能提供复用设计经验。SMM3不吸收cuts工作，不共享cuts实验结果。

SMM3 terminal acceptance有且只有两个触发分支：

- SMM3成功：先记录`U=(1188,18)`、`L=absent`，立即进入cuts；
- SMM3 incomplete：先记录`U=(1188,22)`、`L=absent`，同样立即进入cuts。

两个分支都设置：

```text
NEXT_REQUIRED_TASK=CUTS_GATE1_V4_AUTHORITY_COMPLETION
```

在本文件的三个里程碑完成前，不得启动：

- 新B1/B2武器；
- witness重启；
- PIC；
- B6；
- 其他候选或实验线。

严格顺序：

```text
SMM3 terminal acceptance
→ Gate 1 v4 authority completion
→ 三族单变量重复 A/B
→ 三族 bundle 重复 A/B
→ 效果分类与 promotion 判读
```

## 2. Cuts 独立 authority

cuts必须在独立worktree中建立新的no-overwrite run。v1、v2、v3工具、
history manifest、既有closeout和Gate 1工件保持不可变。

cuts不得读取或引用SMM3 package、selection、receipt或manager epoch作为授权。
它只复用两阶段协议的设计经验。

每个cuts suite在任何arm目录出现前，必须独立固定自己的manager/boot epoch：

```text
boot_id
+ DBus unique owner
+ manager PID/starttime
+ manager executable path/size/mode/SHA-256
+ manager Version/Features
```

manager executable identity采用cuts自己固定的privileged attestor，经
`sudo -n`只读取证；除该attestation外，全部cuts工具和arm以普通用户身份运行。
privileged边界与[01_authority_contract.md](01_authority_contract.md)相同，但
receipt、nonce和epoch属于cuts run，不能复用SMM3字节。

cuts epoch必须贯穿：

- synthetic success；
- synthetic post-SEAL failure；
- forced APPLIED positive-control的control与treatment；
- 全部16个organic arm；
- 每个selection前后与launch；
- 每个pre-terminal、terminal和cleanup；
- 每个pair gate；
- detached replay。

每个arm的`InvocationID`只锚该unit，不能替代cuts manager epoch。

漂移规则：

- arm selection前漂移：不得创建selection，不得启动该arm；
- selection后漂移：该arm已消费，对应pair为
  `CREDIBILITY_INCOMPLETE`；
- 不得把漂移前后的arm组成pair；
- 不得跨epoch、跨run或跨SMM3 authority拼接arm。

manager restart或boot change导致suite无法继续时，只能保留旧run为immutable
incomplete history。在新的no-overwrite run中重新发布完整authority root与
experiment manifest，并从synthetic、positive-control到全部16个organic arms
重新执行。禁止挑选或复制旧run中的已完成arm。

## 3. 里程碑 1：Gate 1 v4 authority completion

### 3.1 Authority root

任何arm出现前，以`O_EXCL`建立包外launch-selection root，固定：

- package ID、purpose、run/arm identity；
- 完整输入与初态；
- solver、cut工具、observer、resource verifier和terminal closer；
- cuts自己的manager/boot epoch；
- resource/time合同；
- selection、SEAL、ledger、terminal与cleanup schema。

v4必须关闭v3的两个已知缺口：

1. terminal envelope必须具备完整raw字段、payload状态、pre-terminal cgroup
   snapshot、release、systemd terminal metadata和cleanup；
2. selection从pre-run到所有阶段都绑定同一detached byte identity，消除跨阶段
   path re-read TOCTOU。

### 3.2 三个真实强制门

#### Synthetic success

完整supervisor/keeper、pre-terminal、terminal、cleanup和detached replay
全部PASS。

#### Post-SEAL failure

payload在SEAL后失败；keeper和terminal必须保留该failure，不能分类为success。

#### Forced APPLIED positive-control

```text
control:   APPLIED=0
treatment: GENERATED>0, COMPILED>0, APPLIED>0
```

checker必须从冻结模型、真实selector mapping、完整solver response和incumbent
独立重建active literal、LHS和RHS。至少一条实际APPLIED inequality必须在同一
冻结incumbent上满足`lhs>rhs`，并与compiled cut、assignment和APPLIED ledger
event一一join。

resource、terminal、cleanup和cuts manager epoch authority必须同时PASS。

该门只建立：

```text
MECHANISM_CREDIBLE
```

其含义是机制可达且至少一条cut具有排除力。它不建立organic runtime
usefulness、family-global soundness、SAT、UNSAT或正式证明价值。

### 3.3 完成门

里程碑1仅在三个真实门及其detached replay全部PASS后完成。失败run固定为
`GATE1_V4_AUTHORITY_INCOMPLETE`；排期仍停留在本里程碑，不得绕行其他项目线。

## 4. 里程碑 2：Prospective order-balanced A/B

Gate 1 v4通过后，在任何organic arm selection前发布immutable experiment
manifest。

### 4.1 Manifest

manifest必须预注册：

- strict input、候选集、初始incumbent/prestate；
- solver与cut工具字节；
- 固定seed、单worker、solver参数和排序；
- 内部固定预算、arm hard guard、cgroup合同和ledger cap；
- primary/secondary指标；
- 指标方向与阈值；
- budget censoring规则；
- no-effect、regression、nonactivation和inconsistent-repeat分类；
- 两个matched pairs的AB/BA顺序；
- pair delta、聚合和一致性判据；
- 与Gate 1 v4 root相同的cuts manager/boot epoch。

指标不得在观察结果后增加、删除或改变阈值。

### 4.2 四组配置与十六个arms

每个配置使用两个order-balanced matched pairs：

```text
pair 1: control A → treatment B
pair 2: treatment B → control A
```

每个arm是fresh process；不共享solver学习状态；全部串行、单worker。两个pair
使用同一预注册固定seed。

四组配置：

1. `region_capacity`
   - control：三族全关；
   - treatment：只开`region_capacity`。
2. `shape_packing_hall`
   - control：三族全关；
   - treatment：只开`shape_packing_hall`。
3. `power_hitting_set`
   - control：三族全关；
   - treatment：只开`power_hitting_set`。
4. bundle
   - control：三族全关；
   - treatment：三族全开。

总数：

```text
4 configurations × 2 matched pairs × 2 arms = 16 organic arms
```

单族trial只归因于该单族开关。bundle trial只归因于三族整体；bundle内
per-family计数不能代替单族消融。

### 4.3 Credibility 与 outcome 双轴

每个arm、pair和configuration分别记录：

```text
credibility_status
outcome_class
```

`credibility_status=PASS`只由以下事实决定：

- authority和cuts manager epoch完整；
- pair输入、初态、seed、工具、预算和环境可比；
- generated/compiled/applied ledger完整；
- resource、terminal、cleanup和detached replay完整。

它不取决于cut是否激活，也不取决于solver是否在预注册内部预算内返回
UNKNOWN。

可信且可完成pair的结果包括：

- `ORGANIC_NONACTIVATION`
  - `GENERATED=0`；
  - 零事件ledger独立replay PASS。
- `NO_ORGANIC_APPLIED_CUT`
  - `GENERATED>0, COMPILED=0`；或
  - `COMPILED>0, APPLIED=0`。
- `BUDGET_CENSORED_UNKNOWN`
  - solver正常到达预注册内部固定预算；
  - runner正常返回UNKNOWN。
- `ORGANIC_APPLIED`
  - 存在独立replay的organic APPLIED cut。

可信零激活与预算内UNKNOWN都是实验结果，不是credibility缺口。它们允许pair
正常完成，禁止为了追逐非零结果而重跑。

`CREDIBILITY_INCOMPLETE`只用于：

- manager/boot epoch漂移；
- 非预注册外层timeout或`RuntimeMaxSec`终止；
- OOM、kill、crash、limit drift；
- authority、ledger、resource、terminal、cleanup或replay缺失；
- 两臂不可比；
- 跨epoch、跨run或跨SMM3 authority拼接；
- 结果产生后修改指标、阈值、censoring或聚合规则。

### 4.4 预注册指标

Primary：

- 有目标模型：固定预算终点的规范化incumbent/objective-bound gap，更小为优；
- 纯可行性模型：cut-free checker验证的incumbent是否出现；
- 无incumbent时不得从cut-on `INFEASIBLE`推导数学进展。

Secondary：

- 达到预注册共同milestone的solver `deterministic_time`；
- 固定预算终点的branches、conflicts、binary/integer propagations；
- generated、compiled、applied计数及首次事件的deterministic time；
- wall time只作资源诊断。

默认阈值：

- 离散objective/bound：至少一个模型最小计量单位；
- incumbent presence：布尔状态变化；
- deterministic time：同时超过绝对`1e-6`和control的1%；
- branches/conflicts/propagations不单独升级runtime-effect claim。

内部预算UNKNOWN是有效右删失终态。它允许比较固定预算终点的预注册指标，但
不建立SAT、UNSAT或其他数学claim。

### 4.5 Pair 与重复聚合

单个matched pair最多报告：

```text
SINGLE_PAIR_OBSERVED_DELTA
```

每个pair按预注册有利方向计算treatment-minus-control delta。两个重复同时报告：

- 两个原始pair delta；
- 算术平均，仅作摘要；
- conservative worst-pair delta，作为claim gate。

只有以下条件全部满足，才允许升级为`SINGLE_FAMILY_RUNTIME_EFFECT`或
`BUNDLE_RUNTIME_EFFECT`：

- 两个matched pairs均`credibility_status=PASS`；
- 全部arms与manifest具有同一cuts manager epoch；
- 两个treatment均存在independently replayed organic APPLIED cut；
- 两个delta方向一致；
- 两个delta均跨过同一预注册阈值；
- 没有primary regression；
- worst-pair delta仍满足效果阈值。

两个重复均落在no-effect band时，分类为
`FIXED_CONFIGURATION_NO_EFFECT`。两个重复均跨过反向阈值时，分类为
`FIXED_CONFIGURATION_REGRESSION`。重复方向不一致、一个激活一个未激活或
只有一个跨阈值时，只报告`INCONSISTENT_FIXED_RUN_OBSERVATIONS`。

### 4.6 完成门

里程碑2在以下条件成立时完成：

```text
4 configurations
8 matched pairs
16 organic arms
```

全部取得`credibility_status=PASS`并具有预注册outcome分类。可信零激活和
预算内UNKNOWN计入完成；只有credibility缺口阻止推进。

## 5. 里程碑 3：判读与 promotion 边界

最终报告必须分离：

- `MECHANISM_CREDIBLE`
- `ORGANIC_NONACTIVATION`
- `NO_ORGANIC_APPLIED_CUT`
- `BUDGET_CENSORED_UNKNOWN`
- `SINGLE_PAIR_OBSERVED_DELTA`
- `SINGLE_FAMILY_RUNTIME_EFFECT`
- `BUNDLE_RUNTIME_EFFECT`
- `BUNDLE_NONADDITIVITY_DIAGNOSTIC`
- `FIXED_CONFIGURATION_NO_EFFECT`
- `FIXED_CONFIGURATION_REGRESSION`
- `INCONSISTENT_FIXED_RUN_OBSERVATIONS`
- `CREDIBILITY_INCOMPLETE`

bundle与三个单族delta可以形成预注册的
`BUNDLE_NONADDITIVITY_DIAGNOSTIC`。没有完整factorial contrast时，不得宣称
已经识别具体pairwise或三阶交互。

可信零激活、no-effect、regression或预算内UNKNOWN只适用于冻结配置。它们：

- 不能证明inequality的运行效果；
- 不能外推cut family全局无效；
- 不能删除这条必做工作；
- 不能建立SAT、UNSAT、soundness或proof claim。

## 6. Stage B promotion

可信化和真实A/B是强制阶段。完成三个里程碑后，是否进入正式Stage B
promotion由独立任务决定。

promotion仍需另过：

- family-global soundness；
- proof-sidecar；
- PIC-4/PIC-5；
- proof-ledger。

本排期不预先承诺production接入，不授权B6，也不把runtime观察升级为数学证明。
