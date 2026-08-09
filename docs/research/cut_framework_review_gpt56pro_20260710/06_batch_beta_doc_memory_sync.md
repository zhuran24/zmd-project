# 修复批 β:文档/记忆层同步(2026-07-12 文档实态外审十四项处置)

- 立项:2026-07-12(owner「现在开始吧」;05 规格 §3 登记的「文档/记忆债 ~14 项」)
- 外审出处:`zmd_doc_audit_20260712`(文档层与代码实态一致性审计,审计对象=97e91c5 打包树;独立发现 14 项 = 5 BLOCK + 8 CONCERN + 1 NOTE)。同日同源的 `zmd_doc_consistency_audit_20260711`/`zmd_doc_reality_audit_20260711` 两包与其发现面重叠,以 07-12 包为准归并处置。
- 性质:**纯文档/记忆层批,零源码改动、无 reseal**(F14 除外——裁定不做,见下)。外审包内补丁 P01-P07 依对抗语料卫生惯例只当参考,全部自己重写。
- 基线注意:审计数字对 97e91c5 打包树取得(428 文件/4284 收集/cuts 792);β 落笔一律按当前树(HEAD `07d04b3`)重新实测:**455 个 test*.py / 4424 收集 / slow 24 登记→31 实例 / cuts 833 / sinks 67 / strong-status 65-83**。

## §1 十四项逐项处置

| # | 级别 | 病 | 处置 |
|---|---|---|---|
| F01 | BLOCK | 最高权威/导航层停在 B0-B4 世界(声称 F5 有 step_8 apply、B5 未完成、legacy 族走 NotImplementedError fallback) | ✅ 五件套全部校准到 07-12 实态:PROJECT_LOCK(§1A B-2 块 + unsafe-map 分类段)、CLAUDE.md(§2 大图 + §4 P1.3 状态)、NAV_MAP/FILE_STATUS 的 src/cuts 行、README(现状速览 + §4 src/cuts + 开放问题#6)。统一口径:F1/F6/F7=typed lowering 唯一通路,F5=shadow-only 无 lowering,F2/F3/F4/F9=LEGACY_DIAGNOSTIC registry 拒绝,F8 retired,gate 仍 unsafe/default-off |
| F02 | BLOCK | Stage B 规格 §2.1 拍板「bundle 每 session 一次」vs 实现每 attach round 重建(~15s/2.3GiB),规格自身两套说法且无显式改判 | ✅ 规格 §2.1 增审计校准块:**登记 promotion 前 BLOCK**——B6 前须 bundle 所有权提升到 session 或 owner 显式改判;注明这是实现债、不属 β 关闭范围。实现侧证据 `benders_loop.py:8150-8161` 复核属实 |
| F03 | BLOCK | 批D 规格「真实 e2e/可信度升级」是测试替身结论(真 adapter 在 verifier 前被拒) | ✅ 04 规格 §3 item5 + §4 各加拆层校准:e2e=测试 oracle 贯通 typed 编排,independently-verified tag 仅测试链可达、非生产背书;roadmap 批D 段同步 |
| F04 | CONCERN | 多处仍写 legacy 四族走 step_8 NotImplementedError fallback,且漏写 F3 | ✅ 随 F01 五件套统一改写为「registry 边界拒绝(旧 fallback 机制已随 B5a 退役)」,F2/F3/F4/F9 四族全列 |
| F05 | CONCERN | checklist §1 的 PIC-2/PIC-6 与 §2 批次日志互相矛盾;PIC-5 未分层 | ✅ checklist §1 三条改写:PIC-2=CLOSED BY ARCHITECTURE(B5a 物理删除 F5 apply,未来 F5 promotion 须另立 lowering 设计,不得复活旧分支);PIC-5=拆两层记账(集成 harness 层✅/生产 campaign 层⬜);PIC-6=DONE(B5a replay 双表);roadmap/06_current_status 同步 |
| F06 | CONCERN | 测试/台账数字过时且三种口径混写(登记条目/收集实例/通过实例) | ✅ 全部按当前树重取并标注口径与实测命令:CLAUDE.md(checker 输出样例 65→67 sinks;slow 26→「24 条登记/31 实例」双口径)、FILE_STATUS Test inventory 重写、README 校准段、06_current_status;各处明示「批次 commit 的 cuts N=当时快照」 |
| F07 | CONCERN | 「candidate_placements 当前存在」写成 lock/台账断言(交付副本实际没有) | ✅ PROJECT_LOCK 两处 + FILE_STATUS 两处改政策式表述:在不在位=打包属性、用 `check_external_artifacts.py` 实测,certified/freeze/require-large 前必须恢复 pinned bytes 并核 size/SHA256 |
| F08 | CONCERN | git/codegraph/selector 命令未声明「真实 checkout」前置 | ✅ CLAUDE.md ⚠交付副本段扩写:remote 因副本而异;无 .git 的 stripped 树中 git/selector 只剩保守回退,不得当精确受影响闭包。顺带修正「本仓库无 remote」过时句与 es(Windows)/fd(Linux) 工具口径 |
| F09 | CONCERN | 「可机器核对的事实更新」被绑在 B6 owner 门上→最高权威在等门期间持续失实 | ✅ Stage B 规格 §9 增校准:B6 只保留授权性变更(unsafe map/红测翻转/release boundary/owner promotion);描述性事实必须随实现批即时同步。β 对 lock 的校准=事实同步,不是、也不得被解读为 owner 关门动作 |
| F10 | BLOCK | vnext P0 卡(m3-step8-landed/m4-ladder-landed/kickoff-recon-facts)当前态断言与源码相反,召回层可能压过正式文档 | ✅ 三卡 `status: superseded` + 指针横幅;新立 **`cut-framework-stage-b-current-20260712`**(kind:status,P0,L0 must_know,supersedes 三旧卡);`p1-2-closed-p1-3-open-20260707` 走就地订正(核心事实未变,summary+正文两处过期子句加日期订正指向新卡)。zmem verify 52 卡 OK/index 45 active/eval 28-28 全绿 |
| F11 | BLOCK | M5/Batch0/M6 三张 P0-L0 卡把已关闭问题写成开放项(A/B 待 owner、1D 待开工、供电可行性 OPEN) | ✅ 三卡 superseded + 横幅;新立 **`p1-3-batch1-m5-current-20260712`**(1A-1F 全落地、C1 默认、存在性关闭、默认参数病态证伪 OPTIMAL@649.1s);prod-scale 单跑铁律与采样纪律并入新卡不丢失 |
| F12 | CONCERN | SQLite 库(cc_memory)只有旧测试状态,缺 cut framework 与 Batch1/M5 current | ✅ 经 mem.py CLI(非手编二进制):add-entry ×3(cut-framework/batch1-m5/test-lane 三条 current)+ supersede 旧 `test-suite-speedup-2026-07-04`(快lane 5.5min/slow 19/60 sinks 快照过时;史实由新条目指回)+ RELATED_TO 边 ×2 + `finalize --no-gpu` status OK |
| F13 | CONCERN | README 顶部/「当前」段与历史段未隔离,旧状态被当现行导航 | ✅ 新增「📌 2026-07-12 校准(cut framework 实态与阅读规则)」块:凡与本段冲突以本段为准、历史段不改写也不再当操作指令;现状速览与 07-07 📌 块的过期尾巴改为指向新块 |
| F14 | NOTE | 三处源码注释旧词汇(frozen_artifacts「Session-scoped」等),修复触 close-kernel reseal 面 | ⬜ **裁定不做**(与外审默认口径一致):纯注释不改行为,单独为它走 reseal 不值;登记为「下一个本来就要 reseal 的批搭车带掉」,且 F02 的 session-bundle 实现批天然顺路(正是同一处注释) |

## §2 处置原则(本批沉淀)

1. **数字必须现取**:审计基线树 ≠ 当前树(打包排除+α/α2 后落地),照抄审计报告数字=引入新漂移。β 全部数字按 HEAD `07d04b3` 实测并写明测量命令/口径。
2. **描述性校准 ≠ 授权动作**(F09):lock 的状态段是事实,owner 门是授权;二者解绑后,「等 owner 期间文档持续撒谎」的结构病根消除。
3. **记忆层=第二文档系统**:vnext 卡按生命周期规程 supersede(禁静默覆盖),SQLite 走 CLI+finalize;两层各立 current 载体并互指,防再分叉。
4. **F02 是实现债不是文档债**:文档能做的只是把矛盾显式化并登记 BLOCK;关闭它需要代码批(session-bundle 所有权),已挂 B6 前置。

## §3 验证

- zmem:verify 52 卡 OK;build-index 45 active;eval 28/28 PASS。
- cc_memory:finalize status OK(entries 7 总/6 active、edges 9 含 1 SUPERSEDES+2 RELATED_TO、facts 4;export 重生成)。
- checker 双绿(15/67、65/83)——β 零源码改动,口径与提交前一致。
- 残留状态串扫描:`B0-B4 landed`/`NotImplementedError fallback`/`26 条 slow`/旧 sink 数在五件套+roadmap+06_current_status 中已清零(历史叙事段与外审归档目录除外,按 F13 阅读规则豁免)。
