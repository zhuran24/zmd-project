# 06 — 当前状态

**状态日期：2026-08-03。**
**发布结论：P1.2 CLOSED（owner 2026-07-07 显式 owner_manual_decision）；P1.3 已开放。**

## 当前结论摘要

- **研究上下界账本：** `U=(1188,18)`，`L=absent`。SMM4 最终 detached receipt
  与 immutable closeout 均为 `VERIFIED`，且只有这两项明确给出
  `upper_bound_update_authorized=true`。该结果只更新 research upper ledger；
  不建立 `(1188,18)` attainability、global optimality、whole-instance
  infeasibility、任何 lower bound 或 production `CERTIFIED`。证据与边界见
  [SMM4 fresh-authority recovery](../research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md)。
- **SMM4 formal 终态：** `smm4-formal-a004` 已消费且永久不得重试。内部
  `VERIFIED`/UNSAT receipt 仍为 `upper_bound_update_authorized=false`，不是账本
  授权源；`production_certified=false`。下述 W0 D6 单轴局部阶段已经完成。
- **W0 power-cycle domino / D6：** G3 最小公共研究合同与 W0 专用的
  hash-pinned intake、exact front-aware joint completion gate、独立 replay 已作为
  research/developer infrastructure 落地。closed-root v2 的 `seed_narrow` 与
  `all_legal_d6_slots` 已分别得到 replay-accepted `INFEASIBLE`，只关闭各自 exact local
  antecedent。保持 28 slots、geometry、pairing、tile split 与全局 class ledger 不变的
  `d6_6b_d9_6g_swap_v1` 单轴 class transfer 也已通过 full preflight、前后两次相同资源
  门禁与两份异构 replay，得到 replay-accepted `INFEASIBLE`。它只关闭 exact local D6 swap
  antecedent，不写入 tracked 状态，不产生 cut、拒绝、下界或全局结论。
- **Routing-aware witness / W2b：** 已有研究构造、运行监督与独立复验基础设施；
  当前没有通过其 HEAD/input-pinned 验收链的 content-addressed layout，故
  `L=absent` 不变。该基础设施不属于发布面，也不产生 production authority。
- **规则与 cut 演化：** 静态规格、一致性门、onboarding fixture 与 rejection audit
  sidecar 均为 test/offline-only shadow，`authority_effect=non_authorizing`；不改变
  production runtime、trusted apply 闭集、authority digest、P1.2 seal 或 family promotion 状态。
- **Noncert cuts A/B：** Gate 1 v4 只建立一条具体 inequality 对一个固定 incumbent 的
  局部 mechanism reachability 与 exclusion power。AB16 减法批与 R11–R20 已落地；
  `run-20260802T221714Z-r6` 的 16/16 预注册臂已可信关闭并按 owner 停止令收官。
  历史 A031–A038 以及旧 frozen-root、retained-FD、pathname replacement 与 disposable
  drill 记录按原字节保留为研究史料，不被重解释，也不再约束当前控制流。终态细节只以
  [roadmap 08-03 行](00_master_roadmap.md) 和
  [最终 EVAL](../../.artifacts/ab16_arms_20260802/EVAL.md)为索引；EVAL SHA-256 为
  `0320a9ace162651eb1e4618641f31c6e5bb33695b97b2458ae45d01a44911784`，terminal
  classification v2 SHA-256 为
  `8745361b540d99ceaa97218f3297c2049ba26bbc37d254abaeafa3aeb0bd5769`。全部 claim-bearing
  authority 仍为 false，`U=(1188,18)`、`L=absent` 不变；不建立 family-global
  soundness、production `CERTIFIED`、witness、attainability 或 optimality。

## 2026-07-29 W0 D6 closed-root negatives 与单轴 class transfer

当前候选只以 research input 收编：strict instance SHA-256 为
`e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`，
framework SHA-256 为
`db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89`，
实际 geometry seed SHA-256 为
`18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1`。
seed 内 producer 自报的
`295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5`
没有绑定实际 seed bytes，明确拒绝作为验收 identity；外部 validation 与冻结 geometry
front probe 也只保留为背景材料。

实现分成两个可独立验收的层次。`devtools/research_run_contract.py` 只提供严格稳定
bytes snapshot、实际 SHA-256、exclusive/no-overwrite run root、canonical
config/receipt、逐组件 descriptor-relative no-follow root 打开、保留全树目录
FD/signature 至终检、排除固定 `receipt.json` 自身的完整 path/type manifest、`-I -B`
进程合同与 byte-identity replay，不解释 W0 数学。D6 专用目录
[`w0_power_cycle_domino_d6_20260728`](../research/w0_power_cycle_domino_d6_20260728/README.md)
联合决定 body、operation class、mode、active physical ports/fronts、合法 transport
incidence，以及 cycle output-injection/input-tap 的双极可达性；seed anchors 只作 hint，
不能恢复“先冻结 body、再补 fronts”。W0 replayer 另行钉死每个 D6 artifact label 的唯一
root-relative path；该实验语义不进入 G3 公共层。

`FEASIBLE` 只证明 receipt 绑定的局部 D6 实例；`INFEASIBLE` 只关闭完全一致的
antecedent、源码与 solver config；`UNKNOWN`、中断、intake 失败或异常均没有拒绝语义。
历史 seed-narrow receipt-payload-v1 root 的命名字节图绑定 antecedent
`7dd634386b4c27a695a7115bd0dddf1c67556ab58923e9dfe526e5f7ee54e59f`
并重放为局部 `INFEASIBLE`，但 root 内两个未登记 `.pyc` 使完整目录闭包不成立；历史 root
保持原样且不得充当 v2 root-closure 证据。

两个已接受 v2 roots 使用完整
`antecedent_v1 + config_v2 + receipt_payload_v2 + replay_v2` cohort：
seed-narrow antecedent `7dd634386b4c27a695a7115bd0dddf1c67556ab58923e9dfe526e5f7ee54e59f`
与 28-slot antecedent
`a5fc8a3a3814970f2401d4c27800e422f8cb46cd358b6d07451f9935f76ddef3`
均为 replay-accepted `INFEASIBLE`。前者没有排除其他 attachment slots；后者排除了仅移动
attachment slot 的修复，但两者都没有排除 class transfer、safe pole anchors、tile 内 size
分配或 domino pairing。

第三个已接受的局部 negative 使用
`antecedent_v2 + config_v3 + receipt_payload_v3 + replay_v3` 的
`d6_6b_d9_6g_swap_v1`：D6 用 `1×6G` 替换 `1×6B`，D9 做反向算术补偿，故 D6 active inputs
由 25 降为 23、D9 由 30 升为 32，全局九类 ledger 不变。D9 不建模、不求解；任何
`INFEASIBLE` 仍只关闭 exact local D6 swap antecedent。`PROJECT_LOCK.md` 仅新增 W0
research-only v2/v3 合法矩阵、兼容与 authority 边界，并未把这些源码或 receipt 加入
certified exact-source TCB。

实现提交 `db00416d3c687dfca28695fa972b768a3f31ee4e` 后，执行链持有三把既有
heavy/production-solver locks，在 full preflight 前后分别检查 RAM、swap、disk、PSI、
竞争进程、项目锁、clean HEAD 与三份 pinned inputs。full preflight 为 `19 passed`，其中
non-slow pytest 为 `6463 passed, 153 skipped`。正式 producer root
`w0-d6-6b-d9-6g-swap-v3-20260728T202427Z-db00416d3c68` 返回
`INFEASIBLE`；exact antecedent SHA-256 为
`dab2a3282b4d4c632d4e0260cc364f397b567f108dbf6480db5d1553a41a9221`，
producer receipt SHA-256 为
`1f5236c39d6f9b827c6244da49fb16f81d97faf0822062042de5dff1e57e620c`。
coherent CPython 3.13.13 与 `/usr/bin/python3` 3.14.6 的两份 root-pinned replay 均为
`PASS` 且逐字节一致，replay receipt SHA-256 为
`568b58bb5e72580dead23936242faa69a7ccbda9e2ec4e3b7476a9bc66cc6f24`。

该 receipt 只关闭上述 exact local D6 swap antecedent；D9 仍只作未求解的 ledger 算术
补偿。按三态合同，本轮在 replay-accepted `INFEASIBLE` 处停止，不自动进入另一轴、D7 或
多轴放宽。H20 row-power oracle、G4、D7、全图 solve 与多轴联合放宽继续后置。
solver/cut production 控制流、checkpoint identity、冻结或密封 bytes、
`U=(1188,18)`、`L=absent` 与 `production_certified=false` 均不变。

## 2026-07-27 SMM4 research upper recovery 终态

成功 fresh root 为
`.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b/`，
external authority package ID 为
`bed3a65a788655b95b445c944292b28fdf6a9f6fce74b27c4f0f8a2617a0622b`。
formal `smm4-formal-a004` 已唯一选择、唯一启动并消费，后续不得重试或改号续跑。

内部 formal receipt 为 `VERIFIED`/UNSAT，但明确保持
`upper_bound_update_authorized=false`。unit 清理后的独立 verifier 执行第二轮
VeriPB，并关闭 resource、terminal/cleanup、unit/cgroup 与 PID absence 证据。
最终 detached receipt SHA-256 为
`9a590d3e0ba6805dc2c1d6abebe60274e4cc5ced868126ab962b0b1a627ddafe`，
immutable closeout SHA-256 为
`e839073a0f20942141147045db541050cc7aad58be91a1459d58835e081d863f`；
两者均为 `VERIFIED` 且明确 `upper_bound_update_authorized=true`。

该 closeout 把 research upper ledger 更新为 `U=(1188,18)`，同时保持
`L=absent`、`production_certified=false`。其证明范围只连接旧
`U=(1188,22)` 的完整 band、SMM-209 geometry admission、2-selector delta
公式/变量映射与 `(22,54)`、`(54,22)` 两个方向；不外推为 attainability、
global optimality、whole-instance infeasibility、lower bound 或 production
`CERTIFIED`。旧 SMM2/SMM3 与前两个 SMM4 root 的失败事实继续保留。

## 2026-07-24 规则与 cut 演化 shadow 协议终态

rule_cut_evolution_status: full_preflight_passed

- **范围：test/offline-only。** 本批增加规则与 family 静态规格、一致性门、
  合同矩阵、onboarding fixture 和 rejection audit sidecar；详见
  [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md)。
- **验收：** `full_preflight_passed` 是绑定
  `fd015a9ac49a182b242895433a2ff2d2e5ee57de` 的批次级 receipt；详细记录见
  [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md)。该 receipt
  不外推为其他 HEAD 的 full-suite 结果或任何 production authority。
- **Authority：non-authorizing。** `PROJECT_LOCK.md`、P1.2 seal/hash、public wire
  与 digest、production 控制流及 trusted apply 闭集不变；`PROJECT_LOCK.md` SHA-256
  仍为 `33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410`。
  full 通过只验收 test/offline shadow 维护面，不授权 production 接线、family 晋级、
  P1.2 reseal、owner flip、持久化 schema 变更或新的数学结论。
- **延期：** production manifest 接线、registry/resolver/Benders/replay/lifecycle
  迁移、持久化 rejection schema，以及 binding/routing/power seam 接入均留待独立
  owner-authorized 批次。

## 2026-07-13 → 07-17 实现状态增量

- **批C 收口（07-13）**：cap=1500 七点矩阵 + 3 组 A/B 完成（全部 0 cut 生成——只证"无触发时无害"）；owner 当晚四项口径全拍（注入式触发对照、alias 一跳为界、B6 先于 F5 转正、矩阵零头清账）——详见 00 号台账 #7。
- **prod 形态适配批（07-14）**：批C 注入演习揭 prod frozen int-orientation 形态 gap（F1/F6 snapshot 投影比 live master 更严 → family 过滤前整条 attach fail-closed）；3 调用点改 `master_scalar_coercions=True` 忠实镜像 live master，双对抗审查 0 BLOCK，reseal 双文件——详见 00 号台账 #8。cut 框架工程线至此**只待 B6 owner flip**（PIC-4/5 生产层 APPLIED>0 证据口径待 owner 表态，00 号台账 #9）。
- **RAB-SEP 三段批（07-14→16，`815a73e`）**：front-free 必要性（命题 N）11 席对抗审查存活；`EXACT_B1_ROUTING_AWARE_BINDING` 收编 certified operational allowlist（默认 OFF）；EMPTY_DOMAIN 证书结构 fail-closed（PROJECT_LOCK 新条款 `F-BL-R11-01`）；单发演习证实 binding↔routing 枚举踏车被结构性绕开（binding 0 轮枚举），但迭代 cut 通道六轮无收敛迹象。
- **front-clear 上收批（07-16，`7b9cbae`/`0873cd1`/`7b88ab8`）**：front-clear 必要条件（计数等价定理）上收 certified master 编码（PROJECT_LOCK 新条款 `F-GM-FCL-01`，默认 OFF）；三集合双 NoOverlap 拓扑 + demand SSOT 进 sealed `port_binding.py`；close-kernel reseal 三轮；语义正确性三面实证（哨兵 45/全池黄金 286,636 pose/corpus 1,314 双向核对零 mismatch），OFF 路径零回归。ON 可用性：presolve 展开病灶确诊并由 `EXACT_MASTER_CP_MODEL_PRESOLVE=0` 解除（lift-ON 必要操作配方），但 6×6 锚点 30min×单 worker 下 fixed/automatic 双双无果；长预算单发判读与默认值翻转待 owner（00 号台账 #10/#11）。判读全档=`docs/research/rab_sep_promotion_20260716/06`。
- **当前机器口径（07-16 上收批后）**：sinks 67 / obligations 15（口径不变）；strong-status 65 AST nodes / 83 allowlist；--full 19 gates / 4470 tests；slow 32 实例。

## 2026-07-11 → 07-12 实现状态增量

- **Stage B 工程面全部完成（B0-B5b，07-11 当夜到深夜连落）**：typed 链首次通电进 benders 编排（B5a wiring cut-over：三路 match + `typed_apply` plan interpreter + resolver/`ModelScopeBinding` 唯一构造 + F5 apply 物理删除 + replay 双表）+ AST lockdown 收尾（B5b：`add_*`→`_lower_*` 私有化 + AST caller 钉 + getattr 旁路拒绝 + precheck 前移原子化）。当前唯一写 master 通路 = registry→resolver→step_8→typed_apply；F2/F3/F4/F9 在 registry 边界拒绝（旧 step_8 `NotImplementedError` fallback 机制已退役）。
- **批D（07-12 凌晨）**：RFC-002 F5 独立 verifier 落地（零依赖 Kuhn 匹配 + differential 357 组合 + 六红测）。**拆两层读**：verifier 本体 sound 且测试贯通仅证明「兼容测试 oracle 可走完 typed 编排」；真实 adapter 因 frozen tuple/list 形态差异在 verifier 前 fail-closed（可达性哨兵钉死），故 F5 仍 shadow-only、转正另需 adapter 修复+真 adapter e2e。
- **修复批 α/α2（07-12）**：pre-promotion 信任根七道 fail-closed 门（state/bundle 内容绑定、exact-type 容器门、cache 一致性、apply 边界 fresh 重算、深冻结 memo/cycle、u_var 身份、master weakref）+ master 写入面锁定收尾（F7 lazy cache 原子性、AST owner-scope lambda/comprehension 封堵、use-context digest、私有构造 reference 反搬运、assert→RuntimeError）。各双 opus 双审（设计 AGREE_WITH_AMENDMENTS + 攻击 PASS）。
- **批E RFC-003（07-12 晚，`7875902`/`dd1a182`/`c10d317`）**：①semantic dedup——编排层严格相等去重（applied-only pool，per master build，step_8 成功后才 insert；I-8 的「同语义 cut 30 轮重复吃预算」就地消灭）；②JSONL 审计 ledger（`src/cuts/ledger.py`，per-writer segment+O_EXCL+GENESIS 血缘+seq/hash 链+reader 三态 fail-closed；**严格非消费**：restart 重取资格=重生成，owner 2026-07-12 显式批准对 02 采纳判定「envelope replay」字面的 waiver）；③enabled_cut_families 参数级 family 开关（默认全开零变更，门 7 rollback 演练用）+编排层 receipt v1+POISONED fail-closed 记账。规格 08 双审：opus 设计位 AWA（4M+6L 全采纳）+codex BLOCK→复核 AGREE_WITH_AMENDMENTS（2M+3L 全采纳，rev3）。七门测试 12 个（门 5 含双进程 kill/resume）；RFC 门 6 保持 **OPEN→批C**。宿主 harness（attach_host_runner.py）解开「批C 宿主环」，批C 三卡点已登记（组织性触发未验/算力窗口/生产编排层=守卫层）。
- **当前机器口径（HEAD `07d04b3`）**：sinks 67 / obligations 15；strong-status 65 AST nodes / 83 allowlist；测试 455 文件 / 4424 收集；slow 24 登记→31 实例；cuts 833。
- **剩余到 promotion**：PIC-4/PIC-5 生产规模实测（批C；集成 harness 层已由定向测试覆盖，生产 campaign 层未做，RFC-003 门 6 prod A/B 并入）、B6 owner 手动门。RFC-003 工程面已于 07-12 批E 落地。α2 新增两项清单已于 07-12 B6 前置工程批双双闭合（①sink 注册 owner 改判 won't-do+理由、②F-05 alias 一跳追踪落地）；session-bundle 所有权同批兑现（`ef5e124`）。**F5 真 adapter 修复只挂 F5 转正批（lock:492 口径），不是 flip 前置。**

## 2026-07-08 → 07-11 实现状态增量（细节见 roadmap §0 与各规格书）

- **C1 已是 certified 默认 master 表示**（批 1D，`a1ae1ed`+`fecb495`）：coordinate delegate 的 C1 pose-bool cov-channel 编码转正，S4 blocker 保证 certified 路径非 C1 即拒。批 1 全六子批（1A-1F）落地：cov 通道+witness cell（1B）、解级 power-pole dominance 剪杆进 sealed（1C，`3cc3cf4`）、第 15 条 proof obligation 入册（1E，`4d98314`）。
- **生产内存条款**（1F+M5 修订）：wrapper `systemd-run --scope` 42G 硬帽+`CAMPAIGN_SWAP_MAX` 默认 20G（C1 出解时刻有 ~60G 级固有尖峰，禁 swap 必死——M5 归因判决 `1148067`/`b25ba1d`）;readiness gate RSS 三档分层。「产品默认 solve 参数病态」经 07-11 A/B 四刀证伪（参数仅 wall 差异,`bd96549`）。
- **cut framework 通电前修复批**（`68b4557`）：F1 BState ghost 轴反置修复（soundness 级）+F2 scope 全 map 严格相等+F3 step_8 入口完整性纵深。**attach 通电 spike 判决 GO**（`e719e5d`：10K cut attach 16.6s+solve +4.1%,效度边界四条）;production integration checklist 立册（PIC-0~7,`4fceb9f`）,PIC-3 预算 env 化已落（`b9fcca9`,BUDGET fail-closed resolver+双注册）,PIC-7 已归因关闭。批 B（宿主形态+RFC-001 评估）已于 2026-07-11 完成；Stage B 规格定稿并已全部执行完（B0-B5b，见顶部 07-12 增量段）——本行早期「待 B2-B5」的表述是 07-11 凌晨快照。
- **exploratory 模式在 prod-scale 上不可用**的坑已钉死（port clearance 启发式 build 爆炸+legacy master+all_facility 实例集,py-spy 实锤,memory 卡+spike 规格书）。

本页顶部摘要描述当前已提交状态与 authority 边界；各带日期的增量段保留当时事实，
其中 receipt 只绑定其明确标注的 HEAD，不外推为其他 HEAD 的 authority。

## 已落地的边界

### 1. producer 只提案

`src/search/outer_search.py:855-954` 的 terminal path 只构造并持久化
`CANDIDATE_PROPOSED`，同时提交 terminal frontier evidence、sink replay request、fixed-witness
material 和 proposal marker。它不再直接铸造 durable terminal `CERTIFIED`。

### 2. supervisor 是唯一 durable terminal mint

`src/search/exact_campaign.py:3497` 的 `ExactCampaign.supervisor_seal()`：

- 从磁盘读取已提交 proposal，而不是信调用者的内存对象；
- 复核 project/source/artifact/campaign/candidate bindings；
- 执行 candidate sink replay 与 fixed-witness capsule；
- 校验 terminal evidence 与发布 witness；
- 写前、写后重新验证 disk authority；
- 只有全部通过才写 terminal `CERTIFIED` seal。

其它路径调用 `mark_campaign_stopped(..., "CERTIFIED")` 会被拒绝。

**生产入口（2026-07-04 已接入）：**`scripts/run_supervisor_seal.py`（`349c56c`）是 `supervisor_seal()`
的独立生产命令，从 proposal-ready marker 驱动；`main.py` 和 runtime wrappers 仍不调用
`supervisor_seal()`，普通 solve 的实际终点仍是 `CANDIDATE_PROPOSED`。入口存在只满足一条机器条件，
不等于 P1.2 closed。

### 3. fixed-witness 与 connector/body 复验

`terminal_fixed_witness_capsule.py` 在隔离 Python 子进程中对提案的确切 `π*` 复跑验证，并用
nonce-bound response 返回裁决。`terminal_fixed_witness_verifier.py` 还独立拒绝 connector cell 被
facility body 占用，包括 own-body 和 other-body。自由重解出的“同尺寸另一个可行布局”不能替代发布
witness。

### 4. P1.2 publish gate 已机器化且 owner-closed

`src/search/certified_surface.py:508` 从权威 review gate 解析 P1.2 发布状态。缺失、畸形、仍 open
或非显式 owner-closed 的 gate 一律使 public surface `publishable=false`。

### 5. public publisher 单入口

`src/search/certified_surface.py:800` 的
`publish_verified_certified_delivery_surface()` 是公开 solution、blueprint 和 delivery manifest 的
唯一 certified publisher。它要求 disk-current supervisor seal，三件输出同源，并在失败时清理部分写入。
外围 serializer、viewer、report、adapter 和 compatibility exporter 已被收拢为非权威派生面。

### 6. whole-layout false-INFEASIBLE 防线

`src/search/benders_loop.py::_reverify_whole_layout_infeasibility_before_cut`（当前调用点约 `:8279`） 在 whole-layout nogood 落 cut 前调用
`independent_infeasibility_reverifier.py`。独立 verifier 不确认、发现可行分歧、超时或异常时，路径返回
UNKNOWN 并拒绝落 proof-bearing cut。

### 7. close-kernel 结构闸

`data/proof_obligations/p1_2_proof_obligations.json` 当前含 15 个 active obligation；
`scripts/check_p1_2_proof_obligations.py` 绑定 proof-bearing sink inventory、source hashes、guard tokens、
allowlist 和关键 gate 文件。它是结构边界检查，不是“P1.2 已 sound/已发布”的证明。

## 已关闭后的剩余边界

1. 普通 solver run 不会从 proposal 自动晋升（生产 supervisor seal 命令已存在：`scripts/run_supervisor_seal.py`；但尚无真实生产 campaign→seal 实跑记录）。
2. `data/review_gates/phase_1_2_spike_close.json` 已为 `closed_manual_owner_decision`，兼容字段
   `p1_3b_entry_allowed=true`。这是 2026-07-07 owner 真实输入的 `owner_manual_decision`；
   内部 supervisor seal 不能自动翻转 owner gate，clean 计数仍保存在仓库外。
3. PR2 的较小 verification TCB、controlled loader、read-once/one-snapshot 设计仍未实现完整（其中「仅防能执行 reseal 仪式的蓄意内鬼」的硬化 owner 2026-07-06 已暂缓到发布时点、明确非 P1.2 闭合前提，见 PROJECT_LOCK §C5 close-scope 修改）。
4. `scripts/package_review_snapshot.py` 的 resolve-once 已把 treeish 一次解析为不可变 commit 并同时用于
   provenance 与物化（ref-move TOCTOU 已闭，回归 `test_package_review_snapshot_ref_move_after_resolve_keeps_packaged_commit`）；
   归档排除策略主缺口已堵（协作记忆 `cc_memory/`+`cc_memory_vnext/` 已排除，`28d9d2c`），残余仅策略细化（`paths/`/`.githooks` 去留、secret-scan 纵深、manifest 是否列出被排除路径名）。
5. roadmap 中标为 OPEN/PARTIAL 的 canonical→geometry、boundary-placement 等项目仍需按各自验收条件处理。
6. flow/throughput 仍明确在命题 P 之外。不能把 diagnostic flow PASS 写成 certified throughput guarantee。

## 测试状态

2026-07-12 collect-only（HEAD `07d04b3`）为 **455 个 `test*.py` 文件、4424 tests**；`src/tests/cuts` 单独为 **833 tests**；`-m slow` 收集 **31 个实例**（`_SLOW_TEST_NODEIDS` 字面登记 24 条）。
这些都是收集数量，不是通过数量；任何 pass 数仍须附命令、工作树与退出码。批次提交信息里的 cuts N 是各 commit 时点快照，不是当前树数字。

## 输入状态

当前冻结 pin：`rules/canonical_rules.json` 59,989 字节 / SHA256
`c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0`；
`rules/preprocess_plan.json` 1,383 字节 / SHA256
`5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`；
`data/preprocessed/candidate_placements.json` 54,467,709 字节 / SHA256
`f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`。轻量分发可外置 candidate，
但当前工作树并不缺该文件。superseded 历史链为 45,774,305-byte
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`、45,773,799-byte
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`、53,594,995-byte
`d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 与 53,595,501-byte
`78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` 只属 superseded、
hash-incompatible 历史链。

当前 generic-input 合同：`box_sink` 3 个物理输入/3 个物理输出，mandatory core 14 个物理输入/
6 个物理输出，成品从 producer output 路由到 provider physical input。provider-aware、
instance-aware box lower bound 为 0，因为当前需求 2 已由真实 mandatory core 容量覆盖；campaign
绑定并原子比较完整 `generic_input_slots_by_operation` map。

## 阶段命名

- P1.2：当前认证发布链 soundness 与 release gate 收口已于 2026-07-07 owner-closed。
- P1.3：已开放（2026-07-08 起实质推进）。cut family 当前态：**通电（typed
  lowering 可写 master）仅 F1 region_capacity、F6 shape_packing_hall、F7
  power_hitting_set 三族**；F5 pattern_nogood 为 shadow-only（B5a 起无
  apply/lowering、只产 ShadowValidated，真 adapter 修复挂 F5 转正批）；
  F2/F3/F9/F4 保持 fail-closed（终态理由：F2 吞吐锁+桥语义、F3 缺
  active_port_witness、F9 tight-K 绞死、F4 缺 route registry——均非遗漏）；
  F8 power_grid_reach 已整族退役删除（owner 游戏规则拍板：电杆不需连网）。
  cut 总量预算 2000 满即停发。总开关 `EXACT_CUT_FRAMEWORK_ATTACH` 仍在
  unsafe map（certified 下开启即 fail-closed）。剩余到 promotion 的是
  PIC-4/PIC-5 生产层证据口径（含 RFC-003 门 6 prod A/B，随批C；证据充分性
  待 owner 表态，00 号台账 #9）与 B6 owner 门。close-kernel 现 67 sinks。
  （史料注：07-08 M4 时期曾按「四族通电」记账，F5 于 07-11 B5a 转
  shadow-only；详见 current 记忆卡 `cut-framework-stage-b-current-20260712`。）
- `p1_3b_*`：只作为既有 JSON/CLI 兼容字段保留，不代表人类路线图仍分 A/B。
