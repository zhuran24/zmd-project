# 21 — 术语表

> 当前 authority 按各自机器源管辖；统一查询入口是 [`../CURRENT.md`](../CURRENT.md)，本页只解释术语，不保存任何“当前取值”副本。
> 历史研究术语可在 `docs/research/` 查阅，但不能覆盖下列发布语义。
> 会变化的 gate、阶段、hash、上下界、cut lifecycle 与实验进度必须从 [`../CURRENT.md`](../CURRENT.md)、[`../CATALOG.md`](../CATALOG.md) 或对应机器源读取。

## 认证与发布

- **candidate verdict / `RUN_STATUS_CERTIFIED`**：单个候选在 benders 求解层通过当前声明检查的
  内部结果。不是 durable campaign `CERTIFIED`，也不是 public certification。
- **producer**：`outer_search`。记录候选并在 strict frontier exhaustion 后提交 proposal。
- **`CANDIDATE_PROPOSED`**：待 supervisor 审核的 terminal proposal 状态，明确不是认证终态。
- **supervisor seal**：`ExactCampaign.supervisor_seal()` 从 canonical disk authority 重读并复验
  proposal 后，唯一可以铸造 durable terminal `CERTIFIED` 的路径；独立 production CLI 为 `scripts/run_supervisor_seal.py`，普通 solver run 仍不自动调用。
- **fixed witness**：为 terminal result 固定、序列化并可独立复验的 witness material；防止
  producer/consumer 对“同一结果”使用不同对象或解释。
- **terminal frontier evidence**：strict candidate frontier 已穷尽且最终候选与记录绑定的证据。
- **public certified surface**：sealed campaign、`final_solution.json`、`optimal_blueprint.json`、
  manifest、当前 hashes 与 publish gate 共同组成的 fail-closed surface。
- **central verified publisher**：`publish_verified_certified_delivery_surface()`，唯一 canonical
  public writer；失败清理三件套。
- **OPEN-GATE / publish-open gate**：owner 控制的 P1.2 发布闸。“gate 已实现”、
  “gate 当前关闭”与“下一阶段获准进入”是三个不同命题；当前取值只读
  [`../CURRENT.md`](../CURRENT.md) 和 gate JSON，不得从测试、receipt、seal 或 checker
  绿灯自动推导。
- **P1.2 CLOSED**：技术 close、要求验证、包材边界与 owner gate 同时满足的治理状态。
  该术语描述成立条件，不自行证明当前已经 CLOSED。

## 求解层

- **master**：placement 与 ghost rectangle 主问题。
- **binding**：端口/slot 绑定子问题。
- **routing**：离散网格 routing 子问题，并含 selected-graph connectivity acceptance guard。
- **flow diagnostic**：`src/models/flow_subproblem.py` 的连续多商品流 LP。仅诊断，不门控
  certified verdict，不产生 proof-bearing Farkas/min-cut cut。
- **power / whole-layout checks**：候选与 terminal evidence 中的电力和全布局复验边界。
- **independent infeasibility reverify**：对 whole-layout proof-bearing elimination 的独立重算；
  generator 的失败声明本身不够。
- **ghost rectangle**：优化目标中的空矩形。精确 objective、admissibility 与 emptiness
  语义只读 `rules/canonical_rules.json` 及 [`../CURRENT.md`](../CURRENT.md)；启发式评分
  不能替代 exact 比较器。
- **pose**：facility instance 的候选位置、朝向、port mode 与 occupied cells。

## 数据与状态

- **canonical rules**：`rules/canonical_rules.json` 的 owner-reviewed 语义真源。
- **preprocess plan**：`rules/preprocess_plan.json`，既参与 regeneration，也被当前 runtime/hash
  closure 消费。
- **candidate placements**：由冻结规则和 preprocess 生成、并通过内容 hash 绑定到
  campaign 的 pose 候选工件。当前文件 identity 只读 proof obligations、manifest 与
  对应机器源；历史 hash 只能作为历史证据，不能被术语表重新提升为 current。
- **generic-input provider contract**：成品必须从 producer output 路由到实际 provider
  instance 的 physical input，campaign 必须绑定完整的
  `generic_input_slots_by_operation` map。具体实例计数、端口数与 lower bound 只读当前
  preprocess/canonical 输入，不在术语表复制。
- **campaign resume compatibility**：checkpoint 与当前规则、artifact 和 proof-bearing source
  closure 一致；不一致必须 reset/新建证据链。
- **compatibility export / viewer / adapter output**：派生消费面。即使文件名或字段看起来像
  canonical artifact，也没有自行认证 authority。

## Controls

- **proof obligation**：把声明、关键 source/sink、测试与 hash 绑定的结构契约。PASS 不等于
  full-project proof 或 owner close。
- **strong-status allowlist**：deny-by-default 的扫描登记与理由。allowlisted 只表示该写入点的
 角色被显式审计，不表示它可绕过 supervisor/publisher。
- **close-kernel**：P1.2 结构 gate、关键文件与解释器/OS 等命名 TCB 的集合。
- **PR1**：producer/supervisor split、fixed-witness、independent reverify、publish gate 与
  central publisher hardening 这一认证链工作包的历史名称。
- **PR2**：进一步缩小 controlled-loader/read-once verifier TCB 的后续工作包名称。
- **P1.3**：面向人的 production master integration 阶段名称，涵盖 cut-family attach、
  Stage B/PIC 与最终 promotion。机器 JSON 中保留的 `p1_3b_*` 是兼容字段，不应继续扩散
  成人类状态名；当前阶段准入只读 [`../CURRENT.md`](../CURRENT.md)。

## Cut framework

- **rule semantic shadow ledger / `RuleSemanticSpec`**：test-only 静态语义台账，
  登记版本、显式信息层序、owner、极性、前件、checker 可用性与失效条件；详见
  [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md)。它不被
  production runtime 消费，也不授予规则新的 authority。
- **family shadow specs / `FamilyTrustSpec` / `FamilyGenerationSpec`**：对既有
  family 硬编码的 test-only 镜像和一致性合同。unavailable 能力必须如实保留；
  规格通过不等于 family promotion 或 production admission。
- **`RejectionRecordV1`**：test/offline-only audit sidecar record，以既有 `cut_id`
  或 semantic fingerprint 为 subject；不含 `record_id`，不进入 authority digest，
  不改变控制流，也不能自动晋级为可信 cut。
- **shadow onboarding fixture**：复用既有 lowering operation 的未接入测试 family，
  用于执行通用负路径和差分语义链；不是 production plugin、manifest row 或 exact
  theorem。
- **active cut families**：在某个明确 registry、lifecycle 与 phase scope 内被接受的 cut
  family 集合。精确成员、lowering 能力、shadow/retired 状态和 attach 安全性只读
  [`../CURRENT.md`](../CURRENT.md)、[`../CATALOG.md`](../CATALOG.md)、
  [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md) 及其机器 registry；
  “active”本身不等于 production admission 或 certified theorem。
- **validator trust boundary**：对 cut certificate 做 fail-closed 重算的边界。实现存在不自动
  意味着该 family 已进入 production theorem。
- **held / active / quarantined**：cut lifecycle 状态；应按实际 lifecycle 与 phase scope解读。
- **GHOST_AGNOSTIC / source digest / replay**：cut scope/currentness 机制，不能替代 campaign
  supervisor 或 public publisher 的 currentness contract。

## 研究账本与有界实验

- **research upper/lower ledger**：`U` 是由已准入必要引理与对应 authority 支持的条件性
  research upper bound；`L` 是通过完整验收链的 feasible witness lower bound。
  当前取值与前提只读 [`../CURRENT.md`](../CURRENT.md)。上下账未相遇时不建立
  attainability 或 optimality，也不是 production `CERTIFIED`。
- **Track B**：上界证明研究线，与 typed cut 平台的 **Stage B** 无关。paper proof、
  proof-bearing 求解链、detached authority 与 research-ledger update 是不同层级；哪一层已获
  接受必须查稳定 claim/decision，而不能从文件名或一次 PASS 推断。
- **`FORMAL_AUTHORITY_INCOMPLETE`**：内部 solver/verifier 结果不足以补齐 terminal
  resource、provenance 或 detached receipt authority 时的失败关闭终态。处于该状态的
  attempt 不能自行更新 research ledger；具体 attempt 与裁决查 [`../CATALOG.md`](../CATALOG.md)。
- **routing-aware witness / W2b**：HEAD/input-pinned 的研究构造、运行监督与独立六项
  复验基础设施。只有通过完整验收链的 content-addressed layout 才能形成具体 feasible
  lower-bound 证据；基础设施本身不属于发布面，也不产生 production authority。
- **non-certified cuts A/B**：对 production attach 机制可达性与固定配置效果进行的
  有界 research-only 实验，不是“已证明 sound”或“已证明不 sound”的同义词。scientific
  manifest、attempt topology、retry 与 frozen-input provenance 必须分层记录；单个 arm、
  mechanism probe 或 campaign receipt 均不能自动铸造 family-global soundness、research
  ledger update、promotion 或 production `CERTIFIED`。当前实验状态与具体结论查对应 dossier
  和 [`../CATALOG.md`](../CATALOG.md)。
- **HEAD-pinned research authority**：receipt 只证明其记录的 originating HEAD、
  inputs、tools 与工件字节。后续 Git 合并保留该历史结果及其明确准入的账本结论，
  但不会在新 HEAD 上重新生成、重放或扩张原 receipt authority；要求 live HEAD
  身份一致的消费必须失败关闭。

## 测试词

- **collected**：pytest 发现了测试，不表示测试执行通过。
- **passed**：指定命令在指定工作树退出 0。必须附命令/日志，不能复用历史计数。
- **targeted suite**：只覆盖列明模块的局部测试，不可描述为 full suite。

## 工作线与批次名录（2026-07-17 全量命名普查后立册）

> 历史名不回溯改写（已被封印文书/锁面条款/提交信息引用）；本节做归位映射。
> 完整普查清单（含全部低频名）存 `.artifacts/doc_sweep_20260717/sweep_findings.json`。

### 工作线（P1.3 内的持续线，非一次性批）

- **cut 框架工程线**：typed cut 平台的工程化（Stage B 系全部批次归此线）。
- **求解与研究线**：让 certified master 真正解出/证明最优（M5/M6/C1、八人会议
  规约、RAB-SEP、front-clear 上收归此线）。
- **支线**：P3.0 形式化（轴 A/B）、P2.0 吞吐、TNS。

### 里程碑与批次（按线归位）

- **M1-M6**（求解线里程碑，07-08/09）：M1 attach sizing spike；M2 语义前置；
  M3 step_8 通电；M4 attach 链通电（F5 后转 shadow-only）；M5 prod 可行性
  实测与内存归因；M6 供电编码诊断。
- **C1 / C6**（M6 修复候选编码）：C1=杆侧 pose 布尔+覆盖通道，并在该历史工作包中
  转为 certified master 表示；C6 判负。当前实现仍应以代码和机器义务为准。
- **批1（1A-1F）**：C1 certified 化六子批。
- **批A / 批B**（P1.3A attach spike 下的两批，07-10/11）：批A=PIC-3 预算 env
  化落地；批B=宿主形态+RFC-001 评估。**与"批C/D/E"同一序列**；与 Stage B 的
  B0-B6 无关。另 soundness_gap_roadmap 里 M2 语义前置的"批A/批B/批C-1"是
  第三套局部编号，只在该文档内有效。
- **Stage B（B0/B1/B1.5/B2/B3/B4/B5a/B5b/B6）**：typed 单一可信链工程序列；
  B6 表示 owner promotion 手动门。各子阶段当前是否完成只读
  [`../CURRENT.md`](../CURRENT.md) 与对应 decision，不在术语表保存进度副本。
- **批C**：PIC-4/PIC-5 生产层实测批（含 RFC-003 门 6 prod A/B）。
- **批D**：RFC-002 F5 独立 verifier 批。
- **批E**：RFC-003（semantic dedup+审计 ledger+family 开关）批。
- **修复批 α/α2/β**：promotion 前信任根/写入面/文档层三连修。
- **prod 形态适配批**（07-14）：int-orientation 形态 gap 修复。
- **RAB-SEP 三段批 / ①′**（07-14→16）：soundness 审查→env 收编→prod 演习；
  "①′"源自 Fable 对照组文档的路线编号，正式名用"RAB-SEP 三段批"。
- **front-clear 上收批**（07-16）：front-clear 必要条件上收 master 编码，
  含六级验证阶梯与探针 2/3/4。
- **round 1-5**（研究线 go/no-go 轮次，07-14→15）：上界证书两死一翻案
  （doc12-16）；**与 PROJECT_LOCK §3A 的 Gemini round 序列是两条互不相关的
  编号轨道**。
- **PIC-0~7**：production integration checklist 检查项；PIC-4=多 rect/epoch
  下 cut 池演化实测、PIC-5=Step 5→8 完整编排生产级验证。
- **RFC-001/002/003**：宿主形态评估 / F5 独立 verifier / dedup+ledger+开关。
- **PR1 / PR2**：P1.2 认证链两轮硬化工作包的历史名称；完成度与延期记录查对应
  dossier，不从本表读取。
- **TCB**：Trusted Computing Base，认证链信任计算基。
- **TNS**：全域无解证书链（Total No-Solution）设计稿。
- **V99**：close-kernel source-hash floor 字典的代号。
- **S4**：C1 转正批的防御断言（certified 路径非 C1 即拒）。

### 已知命名碰撞（读文档时注意消歧）

- **B0/B1**：① Track B 的上界证明研究阶段；② Stage B typed-cut 工程序列的批次；
  此外 **B1** 还可指五月 pose-bool master 范式史料。新文档必须写全
  `Track B/B0`、`Track B/B1` 或 `Stage B/B0`、`Stage B/B1`，不得裸写。
- **F1-F9**：①cut family（本表上文）②15 号文档的 red fixture 编号（无关）。
- **F-6**：批C 发现编号（binding↔routing 枚举循环），**不是** cut family F6。
- **round-N**：①Gemini 设计外审轮（PROJECT_LOCK §3A）②研究线 go/no-go 轮
  （doc12-16），互不相关。
- **命题 N / 命题 UBC**：同一族 front-clear 必要条件的两个抽象层级（N=逐端口
  原始陈述，UBC=聚合计数+逆否的证书形态）；计数等价定理是两者之间的桥。
- **M1/m1**：大写=P1.3 里程碑；小写 m1/m5/m9=03 号史料的 metric 代号。

### 前向命名规范（2026-07-17 起）

1. 耐久事物（线/批/里程碑/条款）命名必须**自解释或自定位**：带功能描述词
   （"front-clear 上收批"合格；裸字母/裸序号如"批F"不合格）。
2. 新名先查本表避免碰撞，落名后同步登记进本表。
3. 沿用系统化序列（PROJECT_LOCK 条款 `F-*`、RFC-N、PIC-N）时按既有 scheme
   顺延，不发明并行序列。
4. 研究文书内部的临时代号（探针 N/阶梯 N/V1-V5 席位号）可用，但首次出现处
   必须自定义，且不得跨文书裸引用。
