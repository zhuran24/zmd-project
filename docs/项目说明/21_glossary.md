# 21 — 当前术语表

> 当前 authority 与状态以 `PROJECT_LOCK.md`、`06_current_status.md` 和机器 gate 为准。
> 历史研究术语可在 `docs/research/` 查阅，但不能覆盖下列发布语义。
> **术语状态日期：2026-08-02（AB16 返工代码已落，实验仍为 0/16）。**

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
- **OPEN-GATE / publish-open gate**：owner 控制的 P1.2 发布闸。当前实现已存在，且已于
  2026-07-07 owner-closed；“gate implemented”不等于“gate closed”，本次 closed 只认
  `owner_manual_decision`，不得从测试、receipt、seal 或 checker 绿灯自动推导。
- **P1.2 CLOSED**：技术 close、要求验证、包材边界和 owner gate 同时满足。当前已成立
  （2026-07-07 `owner_manual_decision`）。

## 求解层

- **master**：placement 与 ghost rectangle 主问题。
- **binding**：端口/slot 绑定子问题。
- **routing**：离散网格 routing 子问题，并含 selected-graph connectivity acceptance guard。
- **flow diagnostic**：`src/models/flow_subproblem.py` 的连续多商品流 LP。仅诊断，不门控
  certified verdict，不产生 proof-bearing Farkas/min-cut cut。
- **power / whole-layout checks**：候选与 terminal evidence 中的电力和全布局复验边界。
- **independent infeasibility reverify**：对 whole-layout proof-bearing elimination 的独立重算；
  generator 的失败声明本身不够。
- **ghost rectangle**：目标空矩形，objective 为 `max_lex(area, min_side)`；`min_side >= 6` 是
  default admissibility，不是替代 objective。
- **pose**：facility instance 的候选位置、朝向、port mode 与 occupied cells。

## 数据与状态

- **canonical rules**：`rules/canonical_rules.json` 的 owner-reviewed 语义真源。
- **preprocess plan**：`rules/preprocess_plan.json`，既参与 regeneration，也被当前 runtime/hash
  closure 消费。
- **candidate placements**：当前 54,467,709-byte / SHA256 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3` hash-bound pose artifact；45,774,305-byte / `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`、45,773,799-byte / `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`、53,594,995-byte / `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 与 53,595,501-byte / `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` 是 superseded、hash-incompatible 历史链。
- **generic-input provider contract**：成品必须从 producer output 路由到实际 provider instance 的 physical input；`box_sink` 为 3 进/3 出，mandatory core 为 14 进/6 出。当前需求 2 已由 mandatory core 覆盖，所以 provider-aware、instance-aware box lower bound 为 0；campaign 绑定完整 `generic_input_slots_by_operation` map。
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
- **PR1**：当前工作树已落的 producer/supervisor split、fixed-witness、independent reverify、
  publish gate 与 central publisher hardening。
- **PR2**：仍开放的更小 controlled-loader/read-once verifier TCB 工作。
- **P1.3**：面向人的当前实施阶段，涵盖 cut-family attach、Stage B/PIC 与最终 promotion。机器 JSON 中
  保留的 `p1_3b_*` 是兼容字段，不应继续扩散成人类状态名。

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
- **active cut families**：当前为 F1-F7+F9；F8 因游戏规则前提为假于 2026-07-08 退役。typed lowering（可写 master）仅 F1/F6/F7；F5 为 shadow-only（compiler=None，无 lowering）；F2/F3/F4/F9 为 LEGACY_DIAGNOSTIC（registry 边界拒绝）。总开关仍 unsafe/default-off，尚未成为默认 certified path。
- **validator trust boundary**：对 cut certificate 做 fail-closed 重算的边界。实现存在不自动
  意味着该 family 已进入 production theorem。
- **held / active / quarantined**：cut lifecycle 状态；应按实际 lifecycle 与 phase scope解读。
- **GHOST_AGNOSTIC / source digest / replay**：cut scope/currentness 机制，不能替代 campaign
  supervisor 或 public publisher 的 currentness contract。

## 研究账本与有界实验

- **research upper/lower ledger**：当前为 `U=(1188,18)`、`L=absent`。
  `U` 表示给定已准入必要引理后的 research upper bound；`L=absent` 表示尚无
  feasible witness 对应的下界。上下账未相遇，因此不建立 attainability 或
  optimality，也不是 production `CERTIFIED`。
- **Track B**：上界证明研究线，与 typed cut 平台的 **Stage B** 无关。
  R4 `a004` admission 只准入几何必要引理供 B1 encoder 使用；随后独立的
  proof-bearing PB/RoundingSat/VeriPB 链才建立 `U=(1188,22)`。
- **`FORMAL_AUTHORITY_INCOMPLETE`**：内部 solver/verifier 结果不足以补齐
  terminal resource、provenance 或 detached receipt authority 时的失败关闭终态。
  面向 `(1188,18)` 的 strict/SMM3 attempts 均属此状态，
  `upper_bound_update_authorized=false`，不构成账本更新 authority。
- **routing-aware witness / W2b**：HEAD/input-pinned 的研究构造、运行监督与独立
  六项复验基础设施。只有通过完整验收链的 content-addressed layout 才能形成具体
  feasible lower-bound 证据；当前没有被账本接受的 layout，故 `L=absent`。该基础设施
  不属于发布面，也不产生 production authority。
- **non-certified cuts A/B**：对 production attach 机制可达性与固定配置效果进行的
  有界研究实验，不是“已证明不 sound”的同义词。Gate 1 v4 的当前最强结论仅为
  `MECHANISM_CREDIBLE`：一个具体注入 inequality 排除了同一 frozen incumbent。
  Prospective AB16 当前指固定科学预注册加 append-only per-attempt retry 的 research-only
  16-arm 设计：scientific manifest 不含 attempt topology，首次可信 terminal 关闭 slot，
  失败 attempt 保持不可改写并允许同 slot 新 ordinal；campaign-global input digest 禁止
  16 臂之间共享输入漂移。baseline 由 tracked-clean checkout provenance 自举；
  fixed-assignment replay 只接受 v2。历史 A031–A038 是不可改写证据而非当前 frozen-root
  runtime。fresh campaign/arm 尚未运行（`0/16`）；控制器 flock 生命周期与 direct runner
  绕锁在修复前阻止真跑。Gate1 v4 仍是独立 trust line，AB16 只可经 package-pinned
  constructor 写 fresh continuation selection，不能铸造 Gate1 terminal/production/certified authority；
  没有 family-global soundness、proof-sidecar、PIC、B6、上下界、optimality 或
  production `CERTIFIED` 结论。
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
- **C1 / C6**（M6 修复候选编码）：C1=杆侧 pose 布尔+覆盖通道，现为 certified
  默认 master 表示；C6 判负。
- **批1（1A-1F）**：C1 certified 化六子批。
- **批A / 批B**（P1.3A attach spike 下的两批，07-10/11）：批A=PIC-3 预算 env
  化落地；批B=宿主形态+RFC-001 评估。**与"批C/D/E"同一序列**；与 Stage B 的
  B0-B6 无关。另 soundness_gap_roadmap 里 M2 语义前置的"批A/批B/批C-1"是
  第三套局部编号，只在该文档内有效。
- **Stage B（B0/B1/B1.5/B2/B3/B4/B5a/B5b/B6）**：typed 单一可信链工程序列；
  B6=owner promotion 手动门（唯一未执行项）。
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
- **PR1 / PR2**：P1.2 认证链的两轮硬化（PR1 已落，PR2 大部延期发布时点）。
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
