# P1.2 supervisor 重做 — L0/L1 详细设计（设计评审会收敛版）

> 本文 = 2026-06-23 supervisor 设计评审 team（panelist：redteam[codex] / soundness[opus] / tcb-arch[opus] / feasibility[codex]，~6 轮对抗讨论、全部 file:line 源码坐实、多处跨模型独立同结论）的收敛产出。
> **它推翻了本目录早先的「单 supervisor」草案**：单 supervisor 调 `evaluate_certified_delivery_surface` 会 `certified_surface:26→exact_campaign:26→master_model` 把 CP-SAT 求解核拖进 TCB，"最小 TCB"与"调 evaluate"自相矛盾 → 必须 **L0/L1 两层切分**。
> 状态：待 owner 过 + 拍 (a)/(b) → Codex 实现 → Opus 审 → 我终审 --full preflight → 外审。

## 0. 诚实性总判据（全场灵魂，进 PROJECT_LOCK）

**一项东西能算「命名 TCB / 声明信任」,当且仅当它「架构上不可达伪造」;一旦实际可达伪造,它就不是 TCB,是个穿 TCB 外衣的 open LIVE 洞。**
（我这轮往 PROJECT_LOCK 加的"父进程只 relay=TCB""guard 非判决权威"两条正是反例：外审 PoC 证伪——用"架构上不产判决"的【声明】糊住了"producer 物理仍有发布路径"的【架构事实】。一期必须收回。）

## 1. 四类 TCB 诚实性框架（tcb-arch + soundness 统一）

每个 TRUSTED / verified-not-trusted 项必须落其一，否则不许写：
- **① 架构事实（机器可验）**：L1 无发布路径、L0 发布链不可达 guard。
- **② 承认的人审根**：L0 源字节（git-hash + 人审锚定，**不假装不可改**）。
- **③ 真信任非验证**：固定解释器、ortools `.so`（不可审，诚实标）。
- **④ verified-not-trusted（L0 运行时核 hash 才信）**：verifier / producer / 所有项目 `.py`。

**第④类的充要诚实前提（soundness 补、最关键）**：名义 verified-not-trusted 但 floor 漏列模块 X → X 从没被核 → 悄悄从"已验证"滑回"未验证却被信任" = 与那两条 false claim 同罪。→ 第④类成立 ⟺ **floor 覆盖完整是机器可验架构事实**。**这正是受控 loader 的价值**（见 §3）。

## 2. L0/L1 两层架构 + 两层 TCB

```
┌─ L0 micro-verifier-core  (~300-350 行, 真 TCB, 唯一发布者) ──────────┐
│ TCB = ① L0 源字节(人审+git钉) ③ 固定解释器+stdlib ① OS read-once    │
│ 【无 ortools;项目码仅 import strict_json 叶(边界见§4);无 domain码】 │
│ 职责 = 字节搬运 + 编排 + 二值裁决,不理解 campaign 语义:             │
│  1. 两段式自举(§3)  2. read-once 读 checkpoint 原始字节 + 自算 digest │
│  3. 自生成 nonce + 自起 replay-child + capsule-child(受控 loader 喂字节)│
│  4. 收二值 verdict + 验 digest 链  5. seal + 独占写三认证输出         │
└──────────────────────────────────────────────────────────────────┘
        ↑ L0 spawn(固定解释器 -I -S -B + 受控 loader)
┌─ child (verifier/replay)  semantic TCB ────────────────────────────┐
│ TCB = verifier+其 import 闭包字节(被 L0 核) + ortools .so + 解释器   │
│ 跑全套 domain 解析/shape 校验/binding·routing/replay —— 字节受控    │
└──────────────────────────────────────────────────────────────────┘
┌─ L1 orchestrator  (~150-200 行, verified-not-trusted) ─────────────┐
│ spawn producer 求解、读 gate 当建议;无发布路径(地址空间内无认证写) │
└──────────────────────────────────────────────────────────────────┘
        ↑ L1 spawn producer(现有 runner,jemalloc/taskset 原样生效)
   producer = 现有大求解进程,只写候选 checkpoint(CANDIDATE_PROPOSED 态)
```

求解器/ortools"算得对"的信任落 **child semantic TCB**、不污染 **L0 编排 TCB**——比单层 TCB 干净得多。

## 3. 受控 import loader（技术核心，一个机制同闭四洞 + 兜第④类诚实前提）

L0 spawn child 时喂一个 meta-path importer，**child 只从 L0 已核的内联表字节快照 import（经 fd 传字节）、根本不走 sys.path 文件系统**。同时闭：
- **BLOCK-6 source-exec-before-digest**：child 不读文件树,无"先 import→后 hash"窗口。
- **覆盖完整性（第④类前提）**：表外模块物理 ImportError → 漏列从 fail-open 变 **fail-closed**;消除"child 自报闭包被谎报"。"实际被核 .py ⊆ floor"是受控 loader 物理恒等、非事后实测。
- **package-shadow B5/B7**：表外模块物理 import 不了。
- **root-split**：child 源 = L0 喂的已核字节,**checked-bytes ≡ executed-bytes 恒等、无两端可 split**（FIX-5 思路延伸到 child 源加载）。

**两段式自举（堵 B7 在 L0 自身）**：阶段① 纯 stdlib（hashlib/pathlib/os/sys，零项目 import）算 sha256 核 floor 字节 → 阶段② 装受控 loader + 清文件系统 finder 后,才触发任何项目 import。装 loader 前那几行必须零项目 import。loader 白名单：项目模块走快照、stdlib + 固定 ortools 绝对路径 `.so` 放行、其余 ImportError（防伪装 stdlib 名夹带）。

## 4. L0 详细职责（CORE 一期）

- **B2 replay 接管（最高危,LIVE-1,三条件缺一不闭——soundness 第三轮升级）**：L0 接管整条 `build_sink_verified_terminal_frontier_evidence`（`certified_frontier:289` replay + `:302` capsule）,且：
  1. **read-once 锁 candidates 字节**（对第一层 stored-byte）;
  2. **L0 自 spawn replay child + 固定解释器**（对第二层应答认证,=B4）;
  3. **L0 独立持有"待验候选域"**——锚定 hash-pinned `canonical_rules.json → globals.empty_rectangle.min_side_admissibility`(+grid 上界)、由 L0 自跑 `certified_frontier.generate_candidate_sizes` 等价**纯 stdlib 枚举**(`certified_frontier.py:58-99`,只吃 admissibility 参数、**不读 candidate_placements.json**)独立产出;**绝不锚 candidate_placements.json**(它虽 frozen+hash-pinned 但只是设施位姿池=求解输入、非「该验哪些尺寸」的域定义)、**绝不从 producer 的 status / strong-key 标记决定验哪些**（`candidate_proof_replay.py:429-441/457 _strong_record_keys` 只复验 record 自报 strong 的子集 → producer 把真·更优候选标成非 strong/漏标,它连复验资格都没有 = 第三层最终扳机）+ **对每个声称 INFEASIBLE 的候选真跑求解判可行性（非仅验 proof 自洽）+ 任一失败 fail-closed 阻断整个 terminal certification**;不继承 producer 任何 per-candidate status。
  - **三条件为何缺一不闭(B1×B2 耦合,跨模型坐实)**:漏标本身**不直接丢候选**(它仍在域里待搜);真正破坏 = 漏标的更优候选被一个**伪造的 strong INFEASIBLE** 经单调放大器 cascade 剪掉(`certified_frontier.py:218` + **`outer_search.py:673/696` 同逻辑镜像**)→ 所以「L0 独立枚举完整候选域」与「对每个 INFEASIBLE 真跑求解」**必须同时成立**,只防一个堵不住耦合扳机。candidate_placements.json 仍由 L0 作求解输入 contract hash 校验(`certified_artifact_contract.py:35-45` solve-time 强 pin),但不作候选域真值锚。
  - **边界**：第 3 条不把 CP-SAT 求解核拖进 L0——L0 只**决定验哪些 + 编排 replay child 真验**（binding/routing 在 child/floor）,L0 持有的是候选域集合 + R* admissibility 组合判定（无 CP-SAT）;候选域真值锚 = 上述 hash-pinned canonical_rules admissibility 字段(已在 floor),**不引入新的「候选域 manifest」中间产物**(那会再造一个 producer 派生锚)。
  - 不修则 `exact_campaign:2115` 最优性比较 `if status!="CERTIFIED": continue` + `certified_frontier:218-220` 单调性放大器 → 一个伪造 INFEASIBLE 撬掉整片"尺寸⊇它"的更大候选域 → false-optimal CERTIFIED,污染 max_lex。
- **B4 解释器身份双向固定**：L0 自身 + L0 spawn child 都用启动时捕获认证的**绝对路径解释器**,不取可变 `sys.executable`;spawn 加 `-I -S -B`（`-S` 必须,堵 BLOCK-4 site/.pth hook 截 stdin）。
- **gate 闸（L0 自带,逐条等价移植,不简化）**：read-once 读 `phase_1_2_spike_close.json` 原始字节 + `object_pairs_hook` 拒 dup-key + **stdlib 逐条移植现有 `resolve_p1_2_publish_open_gate` 的 5 道 fail-closed 检查**（gate_id / status==CLOSED / `next_phase_entry.allowed is True` / owner_decision is Mapping / `p1_3b_entry_allowed is True` + try/except 全兜底）。**不 import certified_surface**。
- **JSON 严格性 + L0 import 精确边界**：① X/Y 决断走 **Y** —— 阶段② import 已验叶子 `src/io/strict_json.py`(实测纯 stdlib 闭包:仅 `decimal/json/math/pathlib/typing`、零项目 import,`strict_json.py:8-14`),不自补。② **「L0 零项目 import」是标语,精确事实 = `L0 项目 import ⊆ {src.io.strict_json}` 单个纯 stdlib 闭包叶**——§0 警告「用标语糊架构事实」,这里必须写精确版、PROJECT_LOCK 同步,否则又是一个标语洞。③ 配套硬约束:gate 5 道(§下条)必须 L0 **自己用 stdlib 实现**(含 `_path_has_symlink_component` 的 3 行 pathlib 重写)、**绝不 import `certified_surface`**(其模块顶层会拖进 `delivery_manifest`/`serializer`/`exact_campaign` 一整片项目依赖)。双 preflight 护栏:L0 项目 import ⊆ {strict_json} + strict_json 闭包仍纯 stdlib,漂移即红。
- **digest 链**：checkpoint_digest（L0 亲读亲算）+ candidate_set_digest + **replay_projection_digest（所有 INFEASIBLE 候选经 L0 自 spawn replay 重投影）** + capsule_verdict_digest + frontier 完备谓词 + supervisor_source_digest,缺一不可、全 L0 自算。
- **L0 拥有路径**：L0 自生成 per-run id + 拼 checkpoint 绝对路径**告诉 L1 往哪写**（不接受 L1 报路径）。配 `proposal_ready` marker（producer 写 run id/exit code/checkpoint sha256）,L0 读 checkpoint **自己独立重算 sha256** 比对、不信 marker 里的 sha256。

## 5. producer / L1 改动

- **`exact_campaign.supervisor_seal()`** = 唯一能写 terminal `final_status=CERTIFIED` 的入口（在 L0 内）。producer 只写 **`CANDIDATE_PROPOSED`** 非权威态;改 `:1920` resume 一致性语义（候选态允许 final_result 存在而 final_status≠CERTIFIED）= **campaign resume state schema 一期必扩**（不扩则 resume 把候选错判成 terminal CERTIFIED 绕过 L0）。
- **写闸删掉、靠架构隔离**：三认证输出写函数**只定义在 L0 文件**;`outer_search.py`/L1 路径删干净 import+调用 → L1 进程地址空间物理无这些写动作。**删 inspect.stack/env-token 软写闸**（同进程内可伪造=虚假保护）。
  - **OS 权限隔离只是 prod 的「+」、dev 下基本形同虚设**:目录无写权要 producer 与 certify 跑在不同账户才成立;本机 dev/test(同用户、UAC 关、(a) 模型下 certify 与 producer 同账户)它等于没有 → **dev 下真保护全压在「架构隔离(L1 物理无写 import/调用)+ AST 可达性闸」两条**,OS 那条不能当 dev 依靠。
- **AST 闸两级别**：① **AST 可达性闸 = soundness 级、且是 dev 下唯一发布安全主闸**(份量等同架构隔离、按 soundness 主闸对待)（证 L0 发布路径不可达 guard / 不调可绕 checker,把"B8 对 L0 dead"钉成架构事实）;② **AST import-hygiene 扫 = hygiene 级**（防开发回归早警,**注释明标非 soundness 论据**）。
  - **现状与诚实边界(跨模型坐实)**:已有控制流敏感可达性引擎 `_reachable_direct_call`(`check_p1_2_proof_obligations.py:694-890`,处理 return/raise 截断 + 常量 if 折叠),但**只用在 fixed-witness 一条线**;认证发布路径中心绑定仍是**存在性级** `_calls_function`/token(`:1698/:1824`,死分支里的调用也误判存在)。升到「控制流敏感可达直呼」(换 `_direct_calls_name`/`_imported_direct_call_errors`)= **中等难度、引擎现成**;但真·soundness 级「证**运行时** guard 不可达」需过程间 call-graph + 路径条件,**当前 codebase 无此基础设施**。→ **设计取向必须诚实**:本闸靠「把 L0 发布路径 guard 做成**常量可判定/调用层面可达直呼**」迎合现引擎(架构上让 guard 不可达),**不得宣称达到完整数据流级 soundness 闸**,否则又是标语糊架构事实。

## 6. 一期范围（必闭,不可推二期） vs 二期

**一期必闭**：B1（capsule 接管）、**B2（3 条件缺一不闭,见 §4）**、**B3/BLOCK-D（根因比文档更深:整条链根本没读过权威磁盘字节 = serialized_state_bytes 形同虚设;修 = L0 拥有路径 + L0 亲自 read-once 读原始字节 + 经 fd 传 child + child 受控 loader 下自解析 + 从 IPC 链整个删 candidate_records/final_result 参数,这套同闭 BLOCK-D + L0 拥有路径 + schema 禁字段）**、**B4（解释器双向固定）**、**单 supervisor→L0/L1 切分**、**BLOCK-6（受控 loader/两段式自举）**、gate 闸进 L0、campaign state schema 扩展、**收回 PROJECT_LOCK 两条 false claim**。
**二期可推（tamper-only,前提 gate 保持 next_allowed=false + PROJECT_LOCK 显式登记 open）**：B5(.pth)、B7(verifier child 侧 floor 覆盖)、**B8(带 2 绑定条件**：B2 按定方案闭 + `runtime_activation_allowed=False` 进 PROJECT_LOCK 硬不变量,缺一 guard 复活)、B9(phase-checker stub)、B10(STRUCTURAL_GATE 手列)、B11(sink 闭世界)、B12(root-split 残)、B13(scanner CONCERN)。
**降为 CONCERN**：producer stdout/exit code 反向污染（现无内容进裁决;设计须明写"裁决输入只来自 L0 read-once hash-bound 落盘字节"）。

## 7. 实现铁律（防伪等价 + 防回归）
- **L0 用 stdlib 重写替换项目码,必须逐项等价,禁止借"L0 要小"弱化**。实例：gate=移植 5 道（非"看 allowed"）;strict JSON=等价 strict_json 防的**三**类（dup-key + NaN 字面量 + parse_float 拒 1e400→inf）。少一项 = false-equivalence。
- **differential tests**：L0 strict JSON parser 配 5-8 property-based test，固定"L0 解析语义 ⊆ 生产 checkpoint writer 输出语义"。
- L0 自身完整性 = **带外 TCB**（git hash + release signing + CI + 人审）,L0 顶层入口无更外层 runtime 验证者 → **诚实写"鸡生蛋根不可消除、只缩小+显式命名",不写成 runtime 自证**。

## 8. 工作量 + 落地顺序（feasibility 终估）
约 **850-1060 行**有效改动、**55-75 个测试** 改/新增、**2-4 周**。拆 2 PR：
- **PR1（地基,不依赖 L0,独立可测）**：`exact_campaign.supervisor_seal()` + `CANDIDATE_PROPOSED` 态 + `:1920` resume 语义 + `outer_search` 剥发布权 + capsule:274-275 BLOCK-D 改 + proposal_ready marker + 同步红测。
- **⚠️ PR1 落完 ≠ 接近收敛、仍 REOPEN**:PR1 只剥 producer 发布权 + 落 BLOCK-D 的 producer 侧;**L0 亲读字节、B2 三条件、B4、受控 loader / 两段式自举全在 PR2**。发 CERTIFIED 资格要 **PR1+PR2 全过 + 再一轮外审** 才到「收敛候选」,gate 全程 `next_allowed=false`。**别让 PR1 绿了产生「快了」错觉**——那正是 round-5 推翻「收敛点」的同一个坑(窄洞闭合 ≠ 架构收敛)。
- **PR2（L0/L1 + 入口）**：L0 micro-verifier-core（受控 loader / 两段式自举 / B4 / 两路 spawn / digest 链 / gate 5 道 / 原子写）+ L1 orchestrator + certify 入口 + preflight AST 两闸 + `run_campaign_linux.sh`/`main.py` 入口。

## 9. PROJECT_LOCK 一期必配修订
- **L0 import 边界进清单**：L0 自身的「项目 import 边界」必须写精确版 `L0 项目 import ⊆ {strict_json}`、**严禁写「零项目 import」标语**(§0 反例:用标语糊「实际 import 了 strict_json」的架构事实);受控 loader「被核 ⊆ floor」机器闸是此条兑现机制。
- 每个 TRUSTED/verified-not-trusted 项落四类之一 + verified-not-trusted 指向受控 loader 机器闸 + "X 对 L0 不可达"指向 AST 可达性闸 + 逐条把旧 false claim（②父进程只 relay、③guard 非判决权威）标"已被第5轮外审推翻",并说清 supervisor 一期把它"变成架构不可达"还是"仍 open LIVE 待二期"。

## 10. 不回退（外审两份 + team 都确认真闭）
F3 own-body、FIX-5 read-once、verifier 内部 witness 一致性、`_fresh_run_marker` 入口 fail-close、四结构源同树 floor、五 anchor 不能 data-only 自升、FIX-4 I1、PYC-EXEC-DIGEST 窄洞。L0/L1 叠在这些之上。

## 11. 调用模型：(a) 分离 certify 命令（owner 2026-06-23 定）
owner 原选 (b),经 team 四方技术分析（一致倾向 (a)）后 **2026-06-23 改定一期落 (a) 分离 certify 命令**（= tcb-arch 触发选项 (c)）;(b) 顶层倒置留作后续加固（同一 L0 换 wiring）。理由：
- (a)：producer 跑完落候选退出 → certify 命令调起 L0 → L0 one-shot 验证发布。L0=跑完即退的纯函数式进程,无 IPC/无常驻=最小核理想形态;jemalloc/taskset 在 (a) 下 producer 仍由现有 runner 起、原样继承。
- (b)：L0 顶层 spawn producer——是**同一个 L0 换个 wiring**,可作后续加固后补;但 spawn 不保证继承 `LD_PRELOAD`(jemalloc)、重构 main 入口回归面大。
→ **已定:一期落 (a);(b) 后补。**

## 12. 外审 21a9dda 三审交叉核对(2026-06-23,3 独立 reviewer)
三份独立外审(审 commit `21a9dda` = 含全部 FIX+capsule+PYC 的 HEAD,各带 PoC/逐行证据,在 `C:\22957\download\新建文件夹\{1,2,3}`)去重后 **5 条 LIVE/tamper BLOCK**,逐条对本设计核对:

| # | BLOCK(三审去重) | 关键 file:line | 本设计纳入 |
|---|---|---|---|
| 1 | TOCTOU 执行源≠事后 digest(capsule import-before-hash L18<L73 / candidate replay hash-before-import / `-B` 不禁读 .pyc) | `terminal_fixed_witness_verifier.py:18/73`、capsule/replay launcher | ✅ 一期 §3 受控 loader(child 只从 L0 已核字节经 fd 编译执行) |
| 2 | `-I` 缺 `-S` → system-site `.pth`/`sitecustomize` 先于 verifier 执行 | 两处认证 launcher | ✅ 一期 §4 B4 已写「-I -S -B,-S 必须」 |
| 3 | v99 floor 非执行闭包:活语义依赖未封(改之 checker 仍绿) | `src/models/port_binding.py`(binding 10→0)、`src/preprocess/operation_profiles.py`(端口槽归零) | ⚠️ 机制一期(§3 受控 loader 物理 fail-closed 表外模块 + §1 机器推导 closure),但**下列具体文件 + contract 内容 digest 此前未显式点名 → 本节补登记**;完整 child 侧覆盖验证 = 二期 B7 |
| 4 | **`sys.argv[0]` 伪造 checker 身份跳过 close-kernel**(命中即不启 checker,配 gate 数据篡改放行 open-gate)= LIVE tamper-assisted | `certified_artifact_contract.py:112-119/:115` | ❌ **此前是 GAP**(L0 接管裁决原则上覆盖、但设计没显式列)→ 本节升为**一期必闭**显式项 |
| 5 | phase-gate AST guard 被最终同名重绑定骗过(`main = lambda: 0`,原定义仍满足 `_reachable_direct_call`,CLI 已换绑) | `check_phase_review_gate.py` `__main__` sink | ⚠️ §5 已述 AST 局限(证定义体非 CLI 最终对象),但「gate 脚本进 checker-owned 硬 digest + 真实负向 CLI 锚点」此前未显式列 → 本节补登记 |

**本节补登记的必闭项(此前设计没显式写、外审逮到):**
- **B-ARGV0(一期必闭)**:L0 自己做 artifact-contract 校验(read-once 读 artifact 字节、自算 sha256 比 LOCKED 常量),**绝不调用 producer 进程内任何用 `sys.argv[0]`/env/文件标志判「已在 checker 内」并短路的逻辑**;删除该身份豁免;公共校验路径无条件执行下层纯校验。L0 不信 producer 的任何「checker 已跑过」自证 —— 这本就是「L0 = 唯一发布者」范式的直接推论,**必须显式钉死、不靠「架构应该盖住了」**(正是 round-5 同款坑)。
- **B-CONTRACT-DIGEST(一期,补强 §3/§4)**:`certified_artifact_contract.py`(及其 `LOCKED_*` 常量)进 L0 floor 的 **checker-owned 内容 digest**(不止存在性);whole-tree digest 只证「树前后一致」≠「树等于获批树」,L0 必须对 contract 本体有内容锚。
- **port_binding.py / operation_profiles.py 显式进 L0 机器推导 floor 闭包**:二者是被认证 binding/routing 真实 import 的活语义依赖,受控 loader 下若不在已核闭包则 child 物理 ImportError fail-closed —— 但闭包推导必须实际覆盖到它们(作为机器推导 authority-transitive closure 的验收用例)。
- **B-PHASEGATE-REBIND(二期 B9 升格为显式必闭)**:`check_phase_review_gate.py` 进 checker-owned 硬编码内容 digest + preflight 跑**真实负向 CLI 锚点**(断言 false gate CLI 返回非零),不再仅靠 AST。

**非 LIVE(一并记):**
- 当前 HEAD(21a9dda)`check_p1_2_proof_obligations.py` 在未改包上**直接红**(缺 2 条 evidence path,指向 `docs/项目说明/soundness_gap_roadmap.md`)= 当前包 close-kernel 未全绿、需核实补(不铸假、非 LIVE,但不能当兜底)。
- `PROJECT_LOCK.md:126-150` 仍描述 FIX-1/OPEN-GATE 未落地、与源码漂移(CONCERN)→ 并入 §9 修订一并清。

**对 PR1 的影响**:无冲突。PR1 第一块(mint 收敛:把发布裁决移出 producer)正是 B-ARGV0 的根除方向;argv[0] 豁免删除 + contract 内容 digest + phase-gate 硬 digest 落 **PR2**(L0 接管 + floor 闭包)。三审确认真闭的(FIX-2/FIX-5/FIX-4 核心判定 + 父不信 in-process verdict + nonce + F3)进 §10 不回退。
