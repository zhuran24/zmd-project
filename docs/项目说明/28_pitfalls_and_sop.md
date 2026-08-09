# 28 — 坑册与操作规程（SOP）

> **本页为无时态文档，就地更新。** 全篇现在时、条件写成显式前提，不写日期。历史考古走 `git log` / `git blame` 与台账 `docs/项目说明/00_master_roadmap.md`；改动了本页所述机制或规程的批，必须同步更新本页。
>
> **本页零权威。** 它只做三件事：把散落的机制性陷阱按场景收拢、给出正确形态、指到真正的权威处。凡承重条款以被指向的那一处为准——release 边界看 `PROJECT_LOCK.md`，谓词外延看 `docs/项目说明/01_overview.md` §1.1 / §1.2，游戏规则看 `rules/canonical_rules.json`（导读 `docs/项目说明/26_rules_handbook.md`），实现状态看 `docs/项目说明/06_current_status.md`（坐标速查 `docs/项目说明/27_status_dashboard.md`），排期与 owner 拍板看 `docs/项目说明/00_master_roadmap.md`。
>
> **引用约定：给「文件 + 符号名」，不给行号**（行号会漂，符号名不漂）。数值型事实（sha、字节数、条数、计数）一律不抄进本页——它们各有唯一真相源且被 reseal 连锁维护，抄一份就是造第二真相源。
>
> **记忆卡不是权威。** 本页的「详情」指针大多指向记忆卡，卡是「为什么是这样」的推导史与转述；转述天然丢失败分支（卡 `sibling-line-receipt-paraphrase-not-evidence`）。承重结论要落地时回源码 / 冻结件 / `PROJECT_LOCK.md` 复核。
>
> 指针里的「卡 `x`（文件层）」= `~/.claude/projects/-home-zhuran24-zmd-pj/memory/x.md`；「卡 `x`（vnext）」= `cc_memory_vnext/cards/x.md`。

---

## 一、坑册（按场景）

### A. 跑测试 / 过门禁时

**A1 preflight 退出码只有 0/1**
机制：`GateResult.exit_code`（`scripts/preflight_gate.py`）只有「有 blocker → 1 / 否则 → 0」两个分支，没有返回 2 的路径。
正确形态：判 BLOCK 看 blockers 是否非空、或输出里的 `BLOCK` 行；别写 `if code == 2` 分支，也别把 exit 2 当成「有警告」。
详情：`CLAUDE.md` 命令坑节；源码 `scripts/preflight_gate.py` 的 `GateResult`。

**A2 `--full` 不是全部测试**
机制：`--full` lane 的 pytest 命令固定追加 `-m "not slow"`（`scripts/preflight_gate.py`），慢 soundness 测试整类不在其中。
正确形态：改认证核心（producer / seal / publish / checker / 被 V99 钉死的源文件）后必须另跑 `python scripts/preflight_gate.py --slow-tests`（串行长超时慢 lane），否则慢 soundness 是盲区。
详情：`CLAUDE.md` 命令坑节；`pytest.ini` 的 `slow` marker 说明。

**A3 `@slow` 是集中登记，不是散落装饰器**
机制：慢测试名单是 `src/tests/conftest.py` 的 `_SLOW_TEST_NODEIDS`（frozenset 字面 nodeid），运行期按它给测试打 slow 标记。新写的慢测试不去登记，就会被快 lane 意外跑到、把秒级门拖成分钟级。
正确形态：新写 ≥8s 的测试去 `_SLOW_TEST_NODEIDS` 登记；retune 时用**无并发、串行**的 `-m slow --durations` 全量扫描测时长（有并发 pytest 时测时长会被挤出假红和虚高）。注意「登记条数」与「`-m slow` 收集到的实例数」是两个口径（参数化会放大），别混着用；**本页不写条数，以 `conftest.py` 实测为准**——`CLAUDE.md` 命令坑节里带日期的那个数字是快照，会漂。
详情：`src/tests/conftest.py` 的 `_SLOW_TEST_NODEIDS`；卡 `pytest-slowness-root-cause-map`（文件层）。

**A4 并发跑 pytest 会互删临时目录**
机制：`pytest.ini` 里 `addopts = --basetemp=.pytest_tmp` 是全局的，两个 pytest 进程会共用并清理同一个 basetemp。
正确形态：多窗口 / 并发时每个进程显式覆盖 `--basetemp=.pytest_tmp/<独立子目录>`。单跑一个测试的标准形态是 `python -m pytest -p no:randomly --basetemp=.pytest_tmp/one <nodeid> -q`。
详情：`pytest.ini`；`CLAUDE.md` 命令坑节。

**A5 测试顺序不稳定**
机制：`requirements.txt` 声明了 `pytest-randomly`，但环境未必装了它——装了就随机排序、没装就自然序，同一条命令在两台机器上顺序不同。
正确形态：要可复现就永远显式带 `-p no:randomly`。
详情：`CLAUDE.md` 命令坑节。

**A6 缺 `candidate_placements.json` 是硬失败不是优雅 skip**
机制：部分测试（如 `src/tests/test_binding.py`、`src/tests/test_routing.py` 的若干用例）在 fixture 阶段直接读该外部大工件，缺失时抛 `FileNotFoundError` 变成一批 error。
正确形态：看到「一批测试莫名 error」先跑 `python scripts/check_external_artifacts.py --require candidate_placements`；缺了用 `python scripts/restore_external_artifacts.py candidate_placements --source <file> --force` 恢复。
详情：`CLAUDE.md` 命令坑节；`scripts/check_external_artifacts.py`。

**A7 静默 skip 比红更危险**
机制：skip 在 `-q` 汇总里只是一个数字，它同时藏两件事——①这条链根本没被验证过；②它若真跑会立刻暴露的别的缺陷。两层欠账互相掩护，能存活任意久。
正确形态：①验收看 skip 数字，不只看 passed，新增或长期 skip 都要问「它为什么不跑、跑起来会怎样」；②测试依赖仓库外路径（`~/下载/`、用户级二进制）时，先查仓库内有没有 tracked 副本，有就指过去；③外部依赖不可避免时用 `pytest.fail` 而不是 `skip`（诚实的红好过静默）；④判据不是「skip 多不多」而是「它在别处有没有被验证」——CI 专门跑的本地缺件 skip 不必补，全世界没人跑过的必修。
详情：卡 `silent-skip-hides-two-layer-debt`（文件层）。

**A8 认证链测试在跑时，整棵树必须冻结**
机制：认证链校验是字节级的、且在生产 runtime 路径上（不只在 checker 脚本里）。慢 lane / preflight 的 pytest 段运行期间，工作树里任何 `src/`、`scripts/` 文件的改动——包括纯新增函数、包括只改 docstring、包括非 sealed 文件、包括一次 `git commit`——都会让 source digest 中途变化，把跑成假红。认证链的 source digest 范围**大于** sealed 名单。
正确形态：①先把要提交的改动全部做完提交完，再挂认证链测试；测试期间只做树外工作（scratchpad / 记忆 / 纯分析）。②测试专用逻辑放 `src/tests/` helper 里 import 生产私有函数，生产文件零改动。③看到认证链测试莫名红，先 `git status` 查树是否脏，再怀疑基线。④别的会话（含 codex 席）在同一工作树跑批时，树冻结对本会话同样生效——连 docs 提交都要等。
本侧状态：Windows 侧的 `concurrent_test_run_guard` hook **未接线**（`~/.claude/hooks/` 下有源码，但 `.claude/settings.local.json` 的 hook 链里没有它），本侧靠纪律文本生效。
详情：卡 `sealed-file-edit-poisons-live-test-runs`（文件层）。

**A9 绿灯资格三问（验收装置忠实性）**
机制：门全绿不等于链被验过。三种独立的假绿：①**输入不是被验链自产**——fixture 手造 exact 值，把真数据里的类型形态差异整段掩盖；②**装置描述了一个不可能存在的世界**——自产字节、走真链、约束全真，但几何上机身占格 / 口位 / 朝向根本立不住；③**投影比它镜像的权威层更严**——单测全绿，真数据上潜伏 fail-closed。
正确形态：报**正结果**（FEASIBLE / 红利 / 解锁）之前逐条问：这些字节是被验链自己产的吗？这个装置在真实几何里存在得下去吗？这层校验是不是比 live 那层更严？负结果（INFEASIBLE / UNSAT）不需要这么严——不忠实的装置只会让它更容易假红、不会假绿。能把「装置忠实性」编成被测代码里的一条 fail-closed 判据就编进去，别只留在文档里当叮嘱；探针目录里同时留忠实变体作对照，两个数一起报。
详情：卡 `projection-must-mirror-live-master-not-stricter`、`probe-fixture-must-be-physically-realizable`（均文件层）。

**A10 `--exploratory` 会覆盖 `--mode`；`--skip-readiness-gate` 只跳启动门**
机制：`main.py` 的 `--exploratory` 覆盖 `--mode` 取值；`--skip-readiness-gate` 只跳启动门，不跳 freeze monitor。
正确形态：想跑 certified 就别同时给 `--exploratory`；想绕 freeze monitor 得另找门，跳启动门没用。另外 exploratory 在 prod-scale 上不可用（port clearance 启发式 build 爆炸 + legacy master 不可比），测 attach 类东西走 certified 直建 harness。
详情：`CLAUDE.md` 命令坑节；卡 `exploratory-mode-prod-scale-unusable`（文件层）。

**A11 `production_readiness_gate.py` 不是纯只读、且是 Linux 导向**
机制：它面向 CachyOS/pacman 环境写，Windows 上直接跑会 BLOCK；且它会 `mkdir .artifacts`。
正确形态：当它是「会落地的门」对待，别在只读勘察流程里顺手跑。
详情：`CLAUDE.md` 命令坑节；`scripts/production_readiness_gate.py`。

---

### B. 提交时

**B1 共享 `.git/index`：pathspec 既别多扫、也别漏**
机制：本仓常有并发会话共用同一工作区和同一个 `.git/index`。裸 `git commit -m` 会把别人 staged 的文件一起提交；反过来，reseal / close-kernel 类改动如果 pathspec 漏了 pin 引用的文件，就会出现「提交树里 pin 期望新 sha、文件还是旧版」——本地 `--full` 读磁盘工作树能过，CI 读已提交树才炸。
正确形态：提交前重看 `git status --short` 和 `git diff --cached --name-only`；只用带明确 pathspec 的提交命令；pathspec 要**精确等于这次逻辑改动的完整一致集**；push 前用 `git show HEAD:<file>` 核对钉死表期望值。
详情：卡 `concurrent-session-shared-index-hazard`（vnext）；hook `cc_memory_vnext/hooks/pre_tool_risk_gate.py`（多会话时拦并发形状；单会话下还有一道 staged 购物车检查）。

**B2 `--amend` 会改到别的会话刚落的提交**
机制：amend 改的是 **HEAD**，而 HEAD 随时可能已被别的会话推进过。仓库守卫问的是「staged 里是不是只有你的改动」——提问和真风险点错位，照着守卫答完仍会中招：你的改动被折进对方那条提交，对方的提交从此内容与 message 不符。
正确形态：amend 前先 `git log --oneline -1` 比对 **hash**（不是比对 message）确认 HEAD 是自己那条；不是就别 amend，改成追加一条新提交。已经误 amend 的无损修法：`git reset <对方原提交hash>` 走 mixed 模式（**别用 `--hard`**），对方提交原样还原、自己的改动留在工作区，再用精确 pathspec 单独提交。一般化：任何**以 HEAD 为隐式参数**的操作（amend / reset / rebase / cherry-pick）都要先验 HEAD 归属。
详情：卡 `amend-can-hit-another-sessions-commit`（文件层）。

**B3 共享工作区里的 untracked 文件会消失**
机制：并发会话的清理动作（git clean 类）会带走未提交的新文件；实测有过「新建目录五个文件几分钟内只剩最后写的那个」。tracked 文件不受影响，真正的安全线是「进了 commit」。
正确形态：①单文件产物写完立刻 `git add` + 精确 pathspec 提交，窗口压到秒级；②目录级 / 要迭代 build 的工作先在仓库外私有目录做，完成后经临时 worktree 拷入并提交（worktree 有独立 index，顺带绕开 B1）；③跨回合继续 untracked 工作前先确认文件还在。
详情：卡 `concurrent-session-untracked-file-wipe`（vnext）。

**B4 禁提交路径**
机制：生成的 proof 输出不进 git：`data/checkpoints/`、`data/blueprints/optimal_blueprint.json`、`data/solutions/final_solution.json`、`data/solutions/certified_delivery_manifest.json`（`scripts/preflight_gate.py` 的 `FORBIDDEN_STAGED_PATHS`）。注意 `data/solutions/` **不是整目录忽略**——.gitignore 走精确路径，该目录下其余审计文件正常跟踪。另外 `src/ai_accel` 不得触碰 proof 路径（preflight 扫描强制）。
正确形态：别「顺手」把求解产物提上去；别为了省事把 `data/solutions/` 整目录加进 ignore。
详情：`CLAUDE.md` 禁提交路径节；`scripts/preflight_gate.py`。

**B5 打包审查快照打的是已提交树**
机制：`scripts/package_review_snapshot.py` 从 committed git tree 打包，不含未提交的脏改动。
正确形态：给外审打包前先提交；打完抽查包里有没有你以为已经在里面的改动。
详情：`CLAUDE.md` 命令坑节。

**B6 行尾：pin 一律用 Edit 改，绝不 `write_text` / `json.dump`**
机制：`.gitattributes` 强制 LF，而 Python 的文本写入在 Windows 侧会写 CRLF——本地读磁盘的门能过、CI 读已提交树挂。sha 一律按 LF 字节算（`git show HEAD:<file> | sha256sum`，或确认文件纯 LF 后取 read-bytes 的 sha256）。
正确形态：改任何 tracked 的 pin 文件用 Edit 工具（保持原文件行尾）。这条对 JSON 型 pin 台账同样成立。
详情：`CLAUDE.md` freeze-ritual 节；卡 `close-kernel-reseal-execution-sop`（vnext）。

---

### C. 改钉死文件时

**C1 「好心」更新 expected hash = 把 superseded 链放进证明**
机制：冻结件的 pin 值是身份声明，不是「当前文件的校验和」。历史上有多代 hash-incompatible 的 `candidate_placements.json`，它们**必须**被 `artifact_hash_mismatch` 拒绝。看到 mismatch 就去改 expected 值，等于让 superseded 工件混进证明输入。
正确形态：mismatch 先查「是文件错了还是 pin 该动」；只有确实要换代的批才走 freeze-ritual（SOP-1），单改一个 expected 常量永远是错的。
详情：`CLAUDE.md` Frozen artifacts 节；`scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` / `EXTERNAL_FROZEN_ARTIFACTS`；`src/search/certified_artifact_contract.py` 源码常量。

**C2 写冻结工件会被 hook 拦——那是提示不是敌人**
机制：`cc_memory_vnext/hooks/pre_tool_risk_gate.py` 的 `frozen-artifact-write` 形状与并发无关、任何时候都拦。
正确形态：被拦时的正确反应是「确认这是不是一次真的 freeze-ritual」，而不是找路绕过去。
详情：`cc_memory_vnext/hooks/pre_tool_risk_gate.py`（`FROZEN_REL_PATHS` / `FROZEN_ROOT_BASENAMES`）。

**C3 pin 面查不全（三种系统性漏报）**
机制：①仓库根 `.rgignore`（自称 "Developer-search projection only"）把 `docs/research/**/*.py|.pyi|.sh|.bash|.zsh|.ps1` 整类排出 `rg` 默认结果，而那片里混着被 `src/tests/` 真导入的活契约文件；②pin 值在源码里可能是**相邻字符串拼接**写的（运行时是完整名，grep 完整字面量零命中）；③同一个 sha 在不同文件里大小写不同（一处大写常量、一处小写），大小写敏感的 grep 会漏。
正确形态：**查 pin 面、查影响面、问「还有没有别处钉了这个值」一律 `git grep` 起手**；非要用 rg 就带 `--no-ignore --hidden`，并排除 `.git/`、`.artifacts/`、`.pytest_tmp/`、`.codegraph/` 和 `.claude/worktrees/`（最后一条是别的会话的副本，命中了也不能改）；查集合成员资格用 python import 把集合 print 出来（或跑对应契约测试），别只 grep 字面量。
详情：卡 `rgignore-hides-live-research-code`、`zmd-allowlist-split-string-grep-trap`（均文件层）；样板审计 `docs/research/canonical_batch_20260807/pin_audit_true_values.txt`（python 真值断言，非 grep）。

**C4 「有导入者 = 必须重钉」是启发式，不是判据**
机制：`docs/research/` 下的脚本分两类——活契约（随 freeze-ritual 重钉）与史料 / replay 门（**故意留旧 pin**，重跑时 fail-closed 才是对的）。「被 `src/tests/` 导入」不足以判定：实测 `docs/research/b1_sidewise_marked_membrane_20260724/authority_bootstrap_v1.py` 的 `PROJECT_LOCK_SHA256` 停在旧代，它的导入者 `src/tests/test_b1_sidewise_marked_membrane_v1.py` 却全绿——因为那个常量不在被断言的路径上，只在 bootstrap 生成收据时用。
正确形态：判据细化成「这个 pin 会不会在门跑起来时被真比对」，靠**跑一次目标测试文件**定，不靠是否被 import。改之前先确认它是活契约还是史料门；史料门里的旧 sha 是记代设计，改了反而毁掉复现门。
详情：卡 `rgignore-hides-live-research-code`（文件层，给的是「有导入者」这层启发式）；史料门清单样板见 `docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md` §3。

**C5 删 helper 引出 ruff unused = 整条 reseal 重来**
机制：reseal 途中若因删函数 / 删 import 引出 ruff 报错，修它就是**再改一次源文件**，sha 又变，前面填好的 pin 全部失效。
正确形态：**先把改动源文件的 ruff 弄干净（`ruff check <file>` All passed）再开始 reseal**，别边 reseal 边被 ruff 逼着二次改码。
详情：卡 `close-kernel-reseal-execution-sop`（vnext）。

**C6 checker 自钉在 JSON 不在源码**
机制：改了 checker 里的 V99 map 就改了 checker 自身字节，它作为 registered sink 也有 pin；但那个 self-pin 存在 `data/proof_obligations/p1_2_proof_obligations.json` 里，更新它不会再改 checker——所以**没有鸡生蛋**。
正确形态：checker 自钉**最后**算、最后填；链一步收敛。
详情：卡 `close-kernel-reseal-execution-sop`（vnext）；`scripts/check_p1_2_proof_obligations.py` 的 `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`。

**C7 close-kernel 结构门只证「登记结构未漂移」**
机制：checker PASS、preflight 绿、测试全过、seal 方法存在——都不证明求解数学正确，更不构成 owner 关门动作或 release closure。
正确形态：绿灯只写成「结构未漂移」；阶段门的开关唯一权威是 `data/review_gates/phase_1_2_spike_close.json`，且必须是 owner 真实手动输入。
详情：`PROJECT_LOCK.md`；`CLAUDE.md` 大图 §4。

---

### D. 起长任务 / 盯任务时

**D1 后台 Bash 约 10 分钟被掐**
机制：`run_in_background` 的 timeout 被 clamp 到 600000ms，超时任务半途被 kill、输出文件空、无残留进程；后台脚本里的长 `sleep` 同样被掐。
正确形态：>10min 的命令写成小脚本用 `setsid nohup script.sh &` 跑，脚本末尾 `touch <名>.DONE` 并把退出码写进日志，用 Monitor 盯标记（Monitor 的 until-loop / sleep 是合法轮询宿主）。
详情：卡 `background-bash-timeout-clamp-setsid`（文件层）。

**D2 `| tail` 毁掉失败取证**
机制：管道会把失败细节裁掉，并且退出码被 `tail` 顶掉成 0——BLOCKED 项永远无法回溯。
正确形态：门禁 / 测试类命令永远 `> log 2>&1` 全量落文件，要摘要就完成后再读文件。
详情：卡 `background-bash-timeout-clamp-setsid`（文件层）。

**D3 `pgrep/pkill -f` 会匹配到自己**
机制：`-f` 匹配整条 argv，而监控 / 杀手脚本的 argv 恰好携带它要找的模式文本，形成自指——表现为「把发命令的自己杀了」「监控永远以为被盯的还在跑」。同理，任何会被回显进日志的字符串（ps 输出、prompt 回显、被委托方复述任务书）都可能伪造日志哨兵。
正确形态：①终态判定一律用 **DONE 标记文件**（文件不会被回显、不会自匹配），日志哨兵最多当辅助且必须行首锚定；②进程探测用 comm/exe 级（`pgrep -x <comm>`，或读 `/proc/<pid>/comm` + cmdline 组合判断），杀进程先 ps 核实 PID 再按 PID 杀；③负载判定看资源（采样 CPU/RSS）不看名字——argv 存在 ≠ 真实负载；④设计探测时默认前提是「模式文本会出现在探测对象自身上」。
详情：卡 `process-probe-argv-self-match-pitfall`（文件层）。

**D4 TaskStop 的成功回执不等于进程死亡**
机制：persistent Monitor 底层进程可能原地僵住，TaskStop 回执成功而进程还在；且 `TaskList` 根本不显示 Monitor 类后台任务——用它核查等于拿错工具出假绿报告。
正确形态：①挂 Monitor 时就把「被监任务终态处理完 → 当场 TaskStop」当同一个动作的后半截，不拆开、不攒到收卷；②验尸用**宽模式** `ps -eo pid,etime,args | grep '[t]ail.*<日志名>'`（窄的 `tail -F` 模式会漏 `tail -n 0 -F` 形态），逐个对 etime 与监听路径；③残留连 wrapper 带 grep 全 kill。
详情：卡 `monitor-cleanup-verify-with-ps`、`background-bash-timeout-clamp-setsid`（均文件层）。

**D5 盯守节拍：先实测差价，再定节拍**
机制：按量计费下，prompt cache 冷掉 = 每次唤醒全量重读上下文。保温式高频轻检查与低频冷读之间有一个由**冷/热差价**决定的临界间隔，差价变了临界跟着变——套旧公式会算错账。
正确形态：三分法——①需要盯的任务（可能抛问题 / 有中间产出）→ 短周期保温检查，不设时长上限，活性检查（日志 mtime 是否推进）并入保温流；②纯等终态（watcher / 通知会叫醒）→ **零周期检查**，事件驱动，终态时一次冷读最便宜；③低价值慢盯 → 间隔能拉到超过临界才值得冷读，否则回到保温。能本地判定状态的外部等待源一律改事件驱动（本地脚本判态 → touch flag → harness 侧 watcher 被唤醒），周期检查只留给「无法本地判定」的场景。**具体临界分钟数依赖当时计费口径，属现态，用前实测差价重算，别抄旧数字。**
详情：卡 `background-bash-timeout-clamp-setsid`（文件层）。

**D6 长跑期间别动树**
机制：见 A8——长门禁 / 慢 lane 在跑时整树冻结。
正确形态：长任务发射前把要提交的都提交完；跑起来后只做树外工作。
详情：卡 `sealed-file-edit-poisons-live-test-runs`（文件层）。

**D7 生产 wrapper 的续跑参数不对称**
机制：Linux wrapper `scripts/run_campaign_linux.sh` 会自动注入 `--resume-campaign`；Windows 的 `scripts/run_prod_*.ps1` **不会**，要显式传 `-ResumeCampaign`，否则重跑丢进度。
正确形态：跨侧接手长跑前先确认续跑参数是谁注入的。
详情：`CLAUDE.md` 命令坑节。

**D8 跑完 `main.py` 只会得到 CANDIDATE_PROPOSED**
机制：这是刻意留开的操作链缺口，不是 bug。durable CERTIFIED 的唯一 mint 走独立命令 `scripts/run_supervisor_seal.py`（从已提交的 proposal marker 驱动），`main.py` 不会顺手执行它。
正确形态：别把「跑完没拿到 CERTIFIED」当故障排查。
详情：`CLAUDE.md` 大图 §3。

---

### E. 读写记忆时

**E1 走错层 / 写进档案**
机制：三层里只有两层活跃。写错层的代价是「下次跨层找不到」。
正确形态：见 **SOP-3（记忆写入路由）**。
详情：卡 `memory-three-layer-coexistence-decided`（vnext）。

**E2 改了卡不跑 `build-index` = 改动不生效**
机制：卡片 `cc_memory_vnext/cards/*.md` 是真相源，但**活 hook 消费的是 `.index` 编译缓存**。在 worktree 里改卡、eval 绿、合并回主树，主树 `.index` 不重建的话，改动可以半个月不生效（已退役的正则照旧在活 hook 里拦人）。
正确形态：凡合并了改卡的批，主树验收必含 `python cc_memory_vnext/zmem.py build-index` 与 `python cc_memory_vnext/zmem.py eval`。**`build-index` 必须在主树跑**，worktree 里跑不算。
机械守卫：`.index` 内嵌卡语料内容指纹（`cards_digest`，内容级、不受 git checkout 的 mtime 抖动影响），与 cards/ 不符时 `context`/`verify` 打 `!! STALE INDEX` 警告行并提示重建——advisory-only 不自动重建、hook 路径异常静默降级；activation log 同步记 `stale_index` 位，可事后追溯陈旧服务了多久。守卫测试在 `cc_memory_vnext/tests/test_index_staleness_guard.py`（memory lane 收集）。警告只兜底，纪律照旧。
详情：卡 `vnext-maintenance-discipline`（vnext）。

**E2b 文件层写完卡不跑编译 = 新卡不在索引里 = 不可召回**
机制：2026-08-08 单门牌化后，文件层的 `MEMORY.md`（每会话自动注入的那份索引）**由 `title+description` 机械编译生成**，不再手写。写了卡不跑编译，这张卡就不在注入索引里——和 E2 是同一族病（真相源与编译缓存脱节），只是换到文件层。
正确形态：写卡（`name`/`title`/`description`）→ `python devtools/memory_plate_tool.py compile --memory-dir <memory目录> --write-index --backup-dir <仓外目录>`。过渡期卡若无 `title`，编译器原样保留其现存索引行（不降级成英文 slug）。批量改卡走 `apply --proposals`（默认 dry-run，`--commit` 强制外部备份+原子替换，越权写卡/写索引一律 fail-closed）。
两条一起记的纪律：①**批量改卡的输入天然是快照**，本目录随时有并发写方——落笔前拿快照与现文逐字节 diff，变动过的卡一律重取门牌（08-08 实锤：一张卡在快照后被结论反转式改写）；①b **钩子覆盖检查按「会不会丢信息」挂，不按动作听起来重不重**——08-08 手工压 8 张超长门牌时差点因为「只是压缩不是改写」免掉这道闸，补跑后确认 0 丢失，但免掉的理由本身是错的；②**注入索引按 JS 字符 + 200 行双上限截断且切尾保头**，所以新卡头插、`compile` 每次打水位（>80% 报警）。字符上限是客户端 bundle 硬编码常量（源码级坐实：`eoe`，同段 `_Y=200`、`hSo=4*eoe`；字段名虽叫 `byteCount` 实为 `t.length`＝JS 字符；截断 `slice(0, lastIndexOf("\n", cap))` ＝保头切尾且切在行边界；客户端自身告警线常量 `t7_=0.8` 与本项目 80% 口径一致）。上游默认 25,000，**本机已由 cc-patch 第三个补丁抬到 40,000**——工具不写死这个数，运行时解析并报明来源，补丁被自动回退时会退回 25,000 而不是静默高报余量。
机器闸（08-08 同日补，别再靠自觉）：`memory_plate_tool.py check-index` 纯只读逐字节比对卡与索引，已挂进 `preflight_gate.py` 的记忆 lane（不一致=`gate.warn` 永不 block，目录缺失静默跳过）。**首次真机运行即抓到两条真漂移**，其中一条是并发写方新写的卡完全不在索引里——「写了卡等于没写」有生产实例，不是理论病。
**CC 会重排 frontmatter**（同日实锤）：文件记忆层由 CC 自带 auto-memory 维护，它把**不认识的顶层字段挪进 `metadata:` 子块**（并补 `originSessionId`）——手写的顶层 `title` 被搬走后编译器认不出、索引标题降级成英文 slug。**且这是随时间蔓延的**：迁移时写在顶层的 title，只要该卡被 CC 的记忆工具编辑一次就会被搬。工具侧已做兼容（顶层优先、`metadata.title` 次之，写入跟随卡的现状而不是两处都留——留两处等于制造新的两块门牌）。同族教训：**任何写别人维护的结构化文件的工具，都要假设对方会重排你的字段**。
详情：`CLAUDE.md` 记忆系统节；`.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md`；卡 [[mtime-is-not-an-arrival-signal]]（这批迁移刷 mtime 制造 12 条下游假阳的对偶教训）。

**E3 只读打开 SQLite 会留写足迹**
机制：裸 `mode=ro` 打开 WAL 库仍会在库文件旁创建 `-wal`/`-shm` 侧车——对「零写足迹」要求的冻结档案来说，只读工具留下了写痕迹。
正确形态：连接串必须 `file:...?mode=ro&immutable=1`（`uri=True`）；权威参照实现是 `cc_memory/mem.py` 的 `connect_immutable`；验收断言钉零侧车（`not list(db.parent.glob("memory.db-*"))`）。
更一般的那条：**修复不会自动传播到新代码**。同一原语在仓里已有 fail-closed 的正确形态时，新写码的人（含子代理）不查先例就会原样再犯；委托任务书里显式点名仓内先例符号，能免掉一轮审查返工。
详情：卡 `sqlite-readonly-immutable-sidecar-trap`（文件层）。

**E4 入卡门槛：小失误不入卡**
机制：每个执行层小失误都入卡，噪声会稀释 L0 与召回面。
正确形态：够格入卡的是真决策（owner 拍板 / 方向变更）、真教训（会反复犯的坑、需大量调查才定位的根因）、纠正背后的**通用判断标准**。判据一句话：下个会话不知道这条会不会付出真实代价？不会 → 当场改正就完。
详情：卡 `vnext-maintenance-discipline`（vnext）。

**E5 发现旧卡过时不能绕过去**
机制：一张 stale 的 active 卡比没有更糟——它还在每回合被注入，继续误导以后的会话。
正确形态：干活中撞见已有卡过时 / 被新证据推翻 / 与现状矛盾，当场处理：小订正就地改；结论真变了走 supersede 并声明；不再成立就 archive。改完跑 `build-index` + `eval`。这是模型主动发起的动作，不等 owner 开口。
详情：卡 `vnext-maintenance-discipline`、`vnext-card-lifecycle`（均 vnext）。

**E6 卡里的转述会丢失败分支**
机制：卡与收据里的 semantics / 结论字段是对代码的转述，天然丢掉「失败时怎么办」那一支。照转述做决策，会把「不阻塞」这种结论建在一个其实会队头阻塞的机制上。
正确形态：卡只当索引；凡结论依赖某分支不存在，回原码验那个不存在性。
详情：卡 `sibling-line-receipt-paraphrase-not-evidence`（文件层）。

**E7 压缩后第一动作是读 `latest.md`**
机制：压缩摘要必有损，PreCompact hook 写出的 `latest.md` 是被压段全文，只有对照原文才能发现没落库的知识。
正确形态：看到压缩注入提示后先**完整分页读完** `latest.md` → 对照补录记忆 / 文档 → 再接续主线；主线再急也排在补录之后。本项目有 Stop hook `.claude/hooks/latest_md_debt_guard.py` 兜底拦停，但 hook 是兜底不是替代。
详情：卡 `compact-first-action-read-latest-md`（文件层）。

**E8 三个 advisory 扫描器的基线是「0 候选」**
机制：`devtools/memory_reference_scan.py`（记忆层完整性）、`devtools/docs_reference_scan.py scan`（文档引用完整性）、`devtools/memory_gap_lens.py assemble|verify`（查漏镜头，引文逐字比对、幻觉候选整条 drop）都是只读、无 apply 通路，报告落 `.prune/`。稳态基线是 0 候选（记忆侧另有一小撮已核的 said_card 静态底噪），**新增才是信号**。
另有两条使用前提：`docs_reference_scan.py scan` 的自检**只允许在 `main` 分支、且被扫真相源已提交**时出报告，分支 / worktree 上一律拒绝出报告（无 override 开关）；未登记进 `data/repository_governance/doc_classes.json` 的在扫描范围内文档只会被记成 `unregistered_doc`，**不会被真扫**。
正确形态：跑完看的是「比基线多了什么」，不是「有没有候选」；在分支上要检查引用完整性，得自己按扫描器的 API 搭定点 harness，或等合回 main 再跑。
详情：`CLAUDE.md` 记忆系统节；`devtools/docs_reference_scan.py` 模块 docstring。

---

### F. 派子代理 / 编排时

**F1 Fable 子代理要 owner 允许才能派**
机制：Fable 是最贵的模型，fan-out 烧配额极快，单席长活也能吃掉可观日额度。**`subagent_type: claude` 不带 model 参数 = 继承主线程模型**，这是最容易中的默认陷阱。
正确形态：所有子代理**显式写 `model: opus`**（机械 / 搜索 / 汇总类用 sonnet）；确实需要 Fable 级推理的单点难题（对抗性终审、soundness 裁决）先向 owner 报「任务 + 为什么需要 Fable」拿允许。主循环自己就是顶配，多数难活直接自己干而不是派。
详情：卡 `ultracode-fable-spawn-discipline`（文件层）。

**F2 子代理没有 Workflow，只有 Agent**
机制：claude 型子代理的工具面里没有 Workflow 工具（精确 select 也查无匹配）；Agent 工具完整可用，可派 claude / codex / Explore / Plan / general-purpose。
正确形态：多层编排 = 主线程开 wf、子代理做「单席主导 + Agent fan-out」；子代理需要 wf 级编排就发消息回主线程代开。派长线子代理时任务书直接写死这个模式。
详情：卡 `subagent-orchestration-tool-surface`（文件层）。

**F3 异步孙代理的产出投主会话，父代理收不到**
机制：**同步派**（Agent 调用直接等返回）父代理能拿到结果；**异步派**（后台 / 带 name 的 teammate 型）的 final report 与 task-notification 一律投主会话主循环，父代理零感知，孙代理自己也观测不到投递去向。带不带 name 都一样。
正确形态：①异步孙代理任务书必须写死「完成时 SendMessage 结论给父代理 `<名>`」；②主线程收到孙代理通知，默认动作是转发要点给父代理；③快查类小活让父代理同步派。
详情：卡 `subagent-orchestration-tool-surface`（文件层）。

**F4 SendMessage 对长跑 teammate 可能整批不投递**
机制：席在连续长跑期间，主线程发出的消息即使 API 返回 success/queued 也可能一条都没送达；席按默认路径收口，整个变更方案没做。
正确形态：①关键拍板要求**回执**（「回一句已接再动工」），无回执不得假设已达；②任务书里写死兜底通道：席在关键节点 N 分钟内无回复就写标记文件、只推进可独立部分，主线程挂 watcher 查标记；③收到席的完工报告先对账「它有没有引用我发过的指令」——没引用 = 大概率没收到，别当它抗命。
详情：卡 `subagent-orchestration-tool-surface`（文件层）。

**F5 worktree 席开工必红（缺 untracked 环境件）**
机制：worktree checkout 天生没有 untracked 的环境件，全量 gate 必红。
正确形态：派 worktree 席的任务书直接带预置清单——① `ln -s` 主仓的 `.venv` 与 `.venv-uvbolt-backup`（有验证器硬断言解释器身份）；②拷 review-gate 引用的 `.artifacts` 历史证据路径；③先 check/restore `candidate_placements`；④建 `.pytest_tmp` 父目录（fixture 的 mkdir 不建父级）。修复全走 untracked，不碰 tracked 树。
详情：卡 `subagent-orchestration-tool-surface`（文件层）。

**F6 Workflow 脚本里的插值转义手癖**
机制：文档里把插值写成转义形态是为了防渲染，但 workflow 脚本要的是真求值——转义后座席收到的是字面文本。字面占位符对座席是硬盲区：它不知道那里本该有值，于是几个席拿到完全相同的提示词。
正确形态：①agent() 提示词里的插值一律裸写、不转义；②发 Workflow 前扫一眼脚本文本里有没有多余的 `$` 转义序列（有 = 几乎必错）；③收到座席「任务里有未替换模板变量」类来信，第一反应是「我的编排 bug」，走停 → 修 → resume（贵席用 resumeFromRunId 缓存回放，别重做）。
详情：卡 `workflow-template-literal-escape-pitfall`（文件层）。

**F7 codex 单发不 spawn 中介**
机制：codex 转发 agent 只在 Workflow / agent team 场景有用（需要它当成员、当结构化出口）。单发委托多一层转发延迟、多烧一份中介额度。
正确形态：主会话直接 Bash 跑 `codex exec -o <落盘文件> "<任务全文>"` 后台 + 等待脚本轮询；协议见 `~/.claude/agents/codex.md`。另外 codex 返回可能是通过 schema 校验的占位输出，并行读者的结果要逐个验真。
详情：卡 `codex-default-delegation-routing`、`codex-structured-output-placeholder-pitfall`（均文件层）。

**F8 批收口要清当批 teammate**
机制：idle 代理不干活但进程挂着占内存、堆满注册表，能积到横跨多个批次都没人发现。
正确形态：「批收口 = 提交 + 全量门 + 清当批 agent」三件套，收口时顺手 TaskStop 当批 spawn 的具名 teammate。
详情：卡 `ultracode-fable-spawn-discipline`（文件层）。

**F9 `/branch` 后原线程 resume 会开出撞车副本**
机制：`/branch` 时「主线程」身份立刻转移给分支线程——活的 workflow、shell、monitor 连人带 worktree 无缝搬过去，原线程进程被关。之后 resume 原线程，wf 看似消失，但 journal 缓存还在原会话目录下，一调 resume 就开出第二份副本，与分支线程里活着的那份在同一 worktree 路径上撞车。
正确形态：resume 一个被 `/branch` 过的会话后，默认假设活 wf/shell/monitor 都在分支线程那边；别动 `.claude/worktrees/` 下任何目录；别用 journal 续跑该 wf；收到疑似「自己的」wf 完成通知先核对是不是分支线程那份。
详情：卡 `branch-resume-topology-wf-inheritance`（文件层）。

**F10 长自治委托的默认失效模式 = 自加固循环**
机制：防御基建自带繁殖推力，长线自治席会不断加固自己的脚手架，把科学本体吃掉。
正确形态：开线就定「科学产出」的阶段验收标准；心跳问产出、不问状态。
详情：卡 `delegation-self-hardening-loop`（文件层）。

**F11 编排者自己写的推理文书是审查盲区**
机制：收尾窗口里由编排者自产的综合推理文书零覆盖，反复出现的错误类型是证据等级混用（把实测当上界、把上界当最优值）。
正确形态：承重文书入库 / 外发前过一个独立的证伪席；文书里的数字前提逐条标证据等级。
详情：卡 `referee-authored-docs-blind-spot`（文件层）。

---

### G. 定位与审计时

**G1 codegraph 索引静默丢失 = 整段会话退化为全仓 grep**
机制：`.codegraph/` 是 git-ignored 的可重生 cache，丢了没有任何报错，只是每次搜索变贵。「无索引就跳过」的通用规矩在本项目会造成大量无谓 token 消耗——本项目的索引是 owner 明确要的。
正确形态：会话开工（或发现自己在连续全仓 grep 时）先 `codegraph status .`，缺失 / stale 就当场 `codegraph init .`（全仓约十秒级，已获授权，不用问）；符号 / 调用链 / 影响面优先 `codegraph explore`。本项目已有 SessionStart hook `.claude/hooks/codegraph_index_guard.py` 自动守卫（缺失→后台 init，存在→后台 sync；flock 防并发互踩），手动检查降级为 hook 挂掉时的兜底。
注意：codegraph **不是权威**——proof 敏感的结论要回源码 + `PROJECT_LOCK.md` + 目标测试核实；feature 分支上可能 stale（`codegraph sync .`）。
详情：卡 `codegraph-index-check-at-session-start`（文件层）；`CLAUDE.md` 读代码的工具约定节。

**G2 承重结论别只靠一次默认参数的文本搜索**
机制：见 C3 的三种漏报（ignore 文件投影、拼接字符串、大小写）。共同点是：默认参数下的一次搜索给出的是被裁剪过的投影，而「搜不到 = 不存在」在这个仓库不成立。
正确形态：审计动作把「工具完备性」当显式检查项写进清单，不靠临场回忆；`git grep` 起手；集合成员资格用 python 真值。
详情：卡 `zmd-allowlist-split-string-grep-trap`、`rgignore-hides-live-research-code`（均文件层）。

**G3 分辨「我的红」和「旧红」靠对照树，不靠肉眼**
机制：`git clone --local --no-hardlinks` 出一份 HEAD 干净树（大工件 symlink 过去）跑同一组测试做对照——但**「clean-clone 也红」只证明「先于该提交」，不证明「陈年」**：同日的环境副作用（修 venv 软链、换解释器）也会先于你的提交出生。
正确形态：红的出生时刻单独考古；修任何环境身份（venv / 软链 / 解释器路径）之前先 `git grep` 老身份字符串找 pin 面——解释器路径也是身份 pin。
详情：卡 `rgignore-hides-live-research-code`、`project-lock-sha-succession-chain`（均文件层）。

**G4 工具坏了先修工具，不绕行**
机制：绕行会把一次性摩擦变成长期税，并且常常绕的是一个其实不存在的问题（「某工具有分钟级延迟」这类过期印象）。
正确形态：遇到工具摩擦先验证它真不真实，真实就并行派人修。工具报错 / 失败 / 不可用时明说哪个工具失败、错误是什么，别假装成功、别用猜测替代工具结果、别因「下一步看起来很明显」就跳过失败。
详情：卡 `fix-the-tool-not-route-around`（文件层）；全局 CLAUDE.md 工具失败诚实性节。

**G5 `select_tests_for_paths.py` 的 exit 2 是「建议跑全量」**
机制：它是开发期 advisory 选择器（不进 CI 硬门）：碰锁面 / checker / frozen 工件、或 codegraph affected 算不出闭包时一律返回 FULL 模式，exit code 2。在无 `.git` 的 stripped 审查树里它只剩保守回退。
正确形态：exit 2 读成「跑 `python scripts/preflight_gate.py --full`」，别把它的保守回退当成精确受影响闭包。
详情：`scripts/select_tests_for_paths.py` 的 `TestSelection.exit_code`；`CLAUDE.md` 权威顺序节末段。

---

## 二、操作规程（SOP）

### SOP-1 freeze-ritual（改任何被字节级钉死的文件）

适用面：`rules/canonical_rules.json`、`rules/preprocess_plan.json`、`data/preprocessed/mandatory_exact_instances.json`、`data/preprocessed/generic_io_requirements.json`、`data/preprocessed/candidate_placements.json`（清单权威 = `scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` / `EXTERNAL_FROZEN_ARTIFACTS`，runtime 侧另有 `src/search/certified_artifact_contract.py` 的源码常量）、以及 close-kernel V99 名单里的源文件。**本页不抄任何 sha / 字节数。**

1. **判定 pin 面**。用 `git grep`（不是裸 rg，见 C3）搜旧值，大小写不敏感；集合类用 python 真值打印。分三堆记账：代码 / 测试运行时 pin、文档展示 pin、**史料门 / replay 门（故意留旧值，不改，见 C4）**。样板台账见 `docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md`。

   **canonical 这条 pin 面的三个实测常识**（都被现场咬过，别照抄旧清单——旧清单只会更短）：
   - **必改站点是 18 处**（4 处活代码/测试 + 14 处文档）。历史上两份现成清单都漏：一份只列 14 处，另一份列 17 处（漏了 `docs/项目说明/27_status_dashboard.md`，它是后加的）。**照抄任何一份旧清单都会漏**，每批重新 `git grep` 数。
   - **两处是大写 sha**：`scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS`，以及 `README.md` 的冻结工件表格行。只 grep 小写必漏这两处 ⇒ 扫描一律 `-i`。
   - **一处活代码被 `.rgignore` 藏起来**：`docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py`。仓库的 `.rgignore` 把 `docs/research/**/*.py` 整类投影出 rg 默认结果，但这个文件被 `src/tests/test_witness_campaign.py` / `test_witness_shelf_constructor.py` 真导入执行，**是活契约不是史料**。用 `git grep`，或 `rg --no-ignore --hidden` 并**排除 `.claude/worktrees/`**（别的会话副本）与 `.git/`。
2. **先清 ruff**。要改的源文件先 `ruff check <file>` 全绿，避免 reseal 中途被逼二次改码（C5）。
3. **改字节**。tracked 文件一律用 Edit 工具（保 LF，见 B6）。
4. **重生成依赖派生产物**——或者机器验证「派生工件字节不变」并写明理由（例如新增内容全落在不被 solver 消费的段内、八段逐字节比对 identical）。别口头断言，留验证输出。
5. **更新 pin**，走迭代法：填一处 → 重跑 checker → 它精确报下一处 drift → 再填，直到 PASS。比先啃懂全部 pin 结构快。
6. **跑全套门**：两个结构 checker（`scripts/check_p1_2_proof_obligations.py`、`scripts/check_strong_status_write_allowlist.py`）+ `python scripts/preflight_gate.py --full` + `python scripts/preflight_gate.py --slow-tests`。慢 lane 不能省（A2）。
7. **提交**：pathspec = 完整一致集（B1）；push 前用 `git show HEAD:<file>` 核对钉死表期望值。
8. **禁止项**：单独改一个 expected 常量去迎合现状（C1）；用 `write_text`/`json.dump` 写 tracked pin（B6）；在门跑起来的时候改树（A8）。

### SOP-2 reseal 连锁（四条链，按需触发）

判定入口：**你改的字节被谁钉着？** 一次批可能同时触发多条链，逐条走完。

**链 A — 冻结工件字节变**
→ `scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` / `EXTERNAL_FROZEN_ARTIFACTS`（注意这里是大写 sha）
→ `src/search/certified_artifact_contract.py` 的源码常量（小写）
→ 各处展示型文档 pin（`CLAUDE.md`、`README.md`、`docs/项目说明/` 等）
→ `docs/research/` 下的**活契约**文件（如 witness 线的 `EXPECTED_SHA256`，被 `.rgignore` 从默认 rg 投影排除，必须 `git grep` 或 `--no-ignore` 才看得见）。

**链 B — 被 V99 钉死的源文件字节变（close-kernel）**，按序三步：

1. `scripts/check_p1_2_proof_obligations.py` 的 `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`——**同一个 dict 兼任两职**（registered sink pin + v99 sealed floor），源码里就是同一个遍历，别当两处找；
2. `data/proof_obligations/p1_2_proof_obligations.json` 里该文件 entry 的 `source_sha256`（checker 要求 JSON 与 dict 一致）；
3. checker 自身字节因步 1 变了 → 更新它在**同一个 JSON**里的 self-pin 条目。**self-pin 在 JSON 不在源码，所以无鸡生蛋；最后算、最后填**（C6）。

如果这次改动是「把逻辑从 sealed sink 抽成新 core」，连锁更长（red-line golden 的 source-tree 指纹归一化、打旧代码位置的对抗测试全量挪位、checker 的结构 lookup 跟着改指向、新 core 进 close-kernel 登记含 critical gate）——照卡 `extracting-proof-core-from-close-kernel-sink-sop`（vnext）走。

**链 C — `scripts/preflight_gate.py` 字节变**
→ `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` 的 `_PROTECTED_SURFACE_SHA256` 里对应条目 + authorized successor 注释改写（successor 记代保留，别把上一代抹掉）。

**链 D — `PROJECT_LOCK.md` 字节变：6 + 1**
`PROJECT_LOCK.md` 不是普通文档，改它（哪怕只更新一行引用）必须走完整条链，否则一大批测试红：

- **3 处测试 pin**：`src/tests/cuts/test_rule_cut_evolution_authority_parity.py` 的 `_PROJECT_LOCK_SHA256`、`src/tests/test_w0_d6_gate.py` 的 `PROJECT_LOCK_SHA256`、`src/tests/test_w0_d6_replay.py` 的 `EXPECTED_PROJECT_LOCK_SHA256`；
- **3 个 D6 研究脚本常量**（**常量名不统一，别按一个名字去搜**）：`docs/research/w0_power_cycle_domino_d6_20260728/` 下 `run_d6_research.py` 与 `replay_d6_certificate.py` 是 `EXPECTED_PROJECT_LOCK_SHA256`，`d6_joint_completion_gate.py` 是 `PROJECT_LOCK_SHA256`（**无 `EXPECTED_` 前缀**）。三者里**只有 `run_d6_research.py` 对活的 `PROJECT_LOCK.md` 做 hash 校验**（它把常量喂给 `devtools/research_run_contract.py` 的 `read_stable_snapshot`，对不上就抛 `ResearchRunContractError("SHA256_MISMATCH")` 拒跑，见 `devtools/research_run_contract.py:433`）；另外两个只把常量嵌进 antecedent / protocol-identity 载荷，不读活文件，但值不更会让下游身份哈希对不上；
- **+1 派生环**：D6 antecedent 内嵌 lock sha，所以 gate 测试里的 antecedent 哈希要用 gate 模块**重建重算**（加载模块跑 antecedent 构造函数，再对 canonical-json 字节取 sha），不能手填；同时 `docs/research/w0_power_cycle_domino_d6_20260728/README.md` 的继承段记新一代。
- **改完跑**：parity + `src/tests/test_w0_d6_gate.py` + `src/tests/test_w0_d6_replay.py` 三个文件全绿再提交。
- **实操判据：排查全不全一律按 `sha` 值 `git grep`，不是按常量名。** 常量名在各处不统一（上一条就是实例），按名字搜必漏；按上一代 sha 的字面值搜能一次找全所有钉点，包括测试、研究脚本、文档展示 pin 与 README 继承段。
- **清单会增长，以 `git grep` 实测为准**；命中的 `docs/research/` 脚本先按 C4 判定是活契约还是史料门（史料门形态的旧代 lock pin 确实存在，别顺手改）。

**同型清单（不止文件 sha）**：canonical sha、解释器路径（验证器 + test fixture 钉的 venv 路径）、外部根路径类常量——修任何环境身份之前先 `git grep` 老身份字符串找 pin 面。

### SOP-3 记忆写入路由

1. **新记忆写文件记忆层**（收件箱）：`~/.claude/projects/-home-zhuran24-zmd-pj/memory/`，`MEMORY.md` 是索引、每张卡一个 `.md`。
2. **达到「必须每回合主动推送」门槛的**，才做成 vnext 卡：写 `cc_memory_vnext/cards/*.md`，并补一条金标准 frame 到 `cc_memory_vnext/eval/regression.jsonl`——frame 要从**真实发生**的信号构造（owner 原话 / 踩坑场景），**禁止照卡片的 `scope.paths`/`symbols` 反填**（那是规则考自己）。
3. **在主树跑** `python cc_memory_vnext/zmem.py build-index` 与 `python cc_memory_vnext/zmem.py eval`，确认新 frame 过、且没把别的搞坏。worktree 里跑不算（E2）。
4. **`cc_memory/`（SQLite）是只读档案**：考古用 `python cc_memory/mem.py search|read <id> --body|impact <id>`；`find <id>` 是跨三层入口（一个 id 在哪层，它替你查完再答）。写命令保留只为档案订正，跑前会打一行提醒不会拦；订正后照旧 `finalize` 收口，`cc_memory/exports/MEMORY.md` 是生成视图别手改。边与 impact 图永久留在这一层（vnext 结构上吞不下），所以查牵连面仍来这里。
5. **不给 vnext 补通用低摩擦写入**——authoring triggers 的摩擦就是质量闸。
6. 入卡门槛见 E4；发现旧卡过时的处理见 E5；只读连库见 E3。

### SOP-4 prod-scale 单跑铁律

**本机 prod-scale master solve 一次只跑一个。** 两个并发把内存吃穿（本机 24 逻辑核 / 47.7GB），Windows 侧已实测双杀。

- **为什么**：C1 编码的 master solve 在**出解时刻**有固有大分配尖峰——稳态十几 G，尖峰把 RSS 顶到物理上限再往 swap 溢出，总需求到 60G 量级。尖峰是出解事件本身，挤过去进程就成功结束。
- **资源条款**：禁 swap 的 42G 帽必死。可行条款 = 无帽（物理内存 + zram 兜底），或 `MemoryMax` 配合足够的 `MemorySwapMax` 让 zram 吸收尖峰。**注意 62G 修订条款对现行池已失效**（见 `docs/项目说明/27_status_dashboard.md` §4），条款要随池版本重标定。
- **内存采样纪律**：≤1s 间隔 + `VmHWM` + `VmSwap` 三列。30s 采样会整个漏掉尖峰，给出「温和」的假象——历史上所有「稳态即峰值」的结论都是这么错的。RSS 采样器抓 PID 要按 `/proc/<pid>/comm == python` 过滤，`pgrep -f` 会匹配到命令行含脚本名的 shell 包装（同 D3）。
- **发射前**：先 `df -h`（根盘容量有限，大输出去挂载的大盘）；确认树已冻结（A8）；用 setsid + DONE 标记 + Monitor 的长任务形态（D1/D3/D4）。
- **让路规则**：低占用的常驻复验任务（单核 + 几 G 级，worker 数 pin 成 1）与逐房间小模型工作零争抢，只有 prod-scale 大求解才真需要给它让路；停这类任务用 **SIGINT**（温和中断能把长跑缓冲的 stdout 刷出来留档），别 `kill -9`——它们的结果 JSON 常常只在收尾一次落盘，中停 = 求解进度全丢、只剩日志。
- **绝不 `pkill claude` 到自己头上**（进程名 `claude`）；确需重启由 owner 手动操作。

详情：卡 `c1-solve-peak-memory-truth`、`m5-run-until-resources-needed`（均文件层）；卡 `p1-3-batch1-m5-current-20260805`（vnext）；全局 CLAUDE.md 原生进程隔离节。

---

## 三、速查：症状 → 先看哪条

| 症状 | 先看 |
|---|---|
| 一批测试莫名 error / fixture 阶段炸 | A6（缺 candidate_placements） |
| 认证链测试莫名红，但代码没动逻辑 | A8（树冻结）→ `git status` |
| 本地全绿、CI 报 source-hash drift | B1（pathspec 漏）+ B6（行尾） |
| checker 报 hash drift / v99 sealed floor drift | SOP-2 链 B（迭代法，checker 自钉最后） |
| 改了 `PROJECT_LOCK.md` 后一大批测试红 | SOP-2 链 D（6+1） |
| 门禁跑了十分钟就没了、输出文件空 | D1（后台 clamp）→ 改 setsid |
| 监控永远以为任务还在跑 / 把自己杀了 | D3（argv 自匹配）→ 改 DONE 标记 |
| 搜遍全仓改完了，全量门还是炸出漏网 | C3 / G2（rgignore 投影、拼接字符串、大小写） |
| 手造装置跑出「突破性正结果」 | A9（绿灯资格三问） |
| 改了记忆卡但行为没变 | E2（主树 `build-index`） |
| 文档引用扫描器在分支上拒绝出报告 | E8（自检要求 main + 已提交） |
| 子代理干完活我什么都没收到 | F3（异步孙代理产出投主会话） |
| 座席提示词里出现未替换的模板占位符 | F6（插值转义手癖） |
| 跑完 `main.py` 没拿到 CERTIFIED | D8（这是设计，不是故障） |

---

**本页的维护责任**：改动了本页任何一条机制、或让某条 SOP 的步骤增减的批，把本页的对应条目一并改掉，别在别处补一条「注意上面那条已经变了」。数值型事实一律不进本页——需要数字时去它的唯一真相源取。
