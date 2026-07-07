---
id: deferred-verifier-hardening-toctou-os-isolation
kind: decision
title: 更深的 verifier TCB 硬化(fd-held read-once/TOCTOU + OS 文件隔离)——是真 soundness 项、child 自列残余,但 2026-07-05 决定暂缓;记暂缓判据 + 何时该翻转去做
summary: 2026-07-05 owner 确认暂缓 PR2 两项更深硬化并要求存档"有这东西 + 为何现在不做"。是什么：fd-held read-once(攥住 fd 只读一次,防 TOCTOU=check 到 use 之间文件被掉包)、阶段4 OS 文件隔离(OS 层围住 verifier 的文件读写)。child 自己在 verify() response 里把 os_process_file_isolation / windows_write_isolation_residual 列为残余 TCB 项(pr2_l0_true_verifier_child.py:490),soundness_gap_roadmap 也把 PR2 read-once/TCB 相关标 OPEN——不是瞎归类,是真项。防的是同一种攻击者：能在封印那一瞬往运行机器硬盘写文件、还卡准时机掉包的人。暂缓四判据：①该攻击者在"自己一台可信机器上跑封印"的现实里基本不存在(能那样写盘的人早在机器里、能干更狠的);②是 defense-in-depth 不是补漏洞——现有已隔离子进程 + 每快照文件执行前验 sha + 冻结工件 hash 钉死,这俩修不了"诚实输入算错答案"的 bug(没这种 bug);③07-05 暂缓时推不动真瓶颈——P1.2 close 当时是 owner 手动 review 门(repo 外),TCB 再硬化那门也不自动开;07-07 该门已由 owner_manual_decision 正式 CLOSED(P1.2 CLOSED/P1.3 开启),但本项仍按发布时点/威胁模型触发条件暂缓,暂缓理由不变;④是最贵最难缠的活(Windows OS 级文件隔离尤其磨人)。翻转条件(何时该做)：封印要在不可信机器上跑、或 CERTIFIED 结果要交给"不信任你机器/你本人"的第三方(别人控制的 CI runner、有写权限的对抗审查者)——那时机器/操作者被动手脚成现实威胁,这俩变重要;但即便那时终极解是"第四路"proof-carrying 小核证书(结果不依赖谁的机器),OS 隔离只是补丁。通用判据内核：一件事值不值得做看三样——挡的风险现不现实、推不推得动真瓶颈、成本配不配收益;07-07 更新只改项目瓶颈时点,不改发布时点暂缓结论。
scope:
  domains:
    - certified-exact
    - pr2
    - tcb
    - soundness
  paths:
    - src/search/pr2_l0_true_verifier_child.py
    - docs/项目说明/soundness_gap_roadmap.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - decide-whether-to-do-deeper-tcb-hardening
    - plan-toctou-readonce-or-os-isolation
    - assess-verifier-residual-tcb-items
  keywords:
    - fd-held read-once
    - TOCTOU
    - OS 文件隔离
    - os_process_file_isolation
    - windows_write_isolation_residual
    - 残余 TCB
    - 暂缓硬化
    - 何时该做
    - 不可信机器
    - 信任交给第三方
    - proof-carrying 第四路
  negative_keywords: []
  paths:
    - src/search/pr2_l0_true_verifier_child.py
  symbols: []
  error_regex: []
  examples:
    - 要不要做 fd-held read-once / OS 隔离 / TOCTOU 硬化
    - verifier 还有哪些残余 TCB 项没做、为什么没做
    - 什么情况下该回头做那两项更深硬化
activation:
  layer_hint: L1
  must_know: false
  reason: 规划 verifier TCB 深化、或有人问"还有哪些硬化没做/为什么没做"时该读——记了两项真 soundness 硬化(TOCTOU read-once + OS 隔离)的存在、暂缓判据、和"威胁模型变了才该做"的翻转条件。不读容易要么忘了它们存在,要么在自可信机器上白投最贵的活。
provenance:
  op: record
  reason: '2026-07-05 owner 听完暂缓推理后要求存档"有这东西 + 为何现在不做",把决定与判据固化,供未来重估。'
  evidence:
    - "2026-07-05:child response 自列 os_process_file_isolation / windows_write_isolation_residual 为残余项(pr2_l0_true_verifier_child.py:490);soundness_gap_roadmap.md 标 PR2 read-once/TCB 相关 OPEN。暂缓是判断非实测,判据见 summary。同日刚落地 PR2-1 (b)/① commit 9d224d8。"
  updated_at: "2026-07-07"
---
2026-07-05 owner 听完"为何暂缓"的推理后,要求存档:有这么两项更深硬化、以及为什么现在不做。记事实 + 判据,供未来威胁模型变化时重估。

== 是什么(两项都是真 soundness 项,不是瞎归类)==
- **fd-held read-once(TOCTOU 硬化)**:TOCTOU = "检查完到真正用之间,文件被掉包"。verifier 现在"先看一眼对不对、隔会儿再拿来用",中间有空档能被换(检查的是 A、用的是被换成的 B)。硬化 = 打开文件后攥住 fd、只读一次,让检查的就是用的、掉包窗口消失。
- **阶段4 OS 文件隔离**:在操作系统层面围住 verifier,别人没法经文件系统动它读写的文件。
- 出处:child 自己在 `verify()` response 里把 `os_process_file_isolation` / `windows_write_isolation_residual` 列为**残余 TCB 项**(`pr2_l0_true_verifier_child.py:490`);`soundness_gap_roadmap.md` 也把 PR2 read-once/TCB 相关标 OPEN。
- 防的是同一种人:**能在封印那一瞬往运行机器硬盘写文件、还卡准时机掉包的攻击者。**

== 为什么 2026-07-05 决定暂缓(四判据)==
1. **要防的攻击者现在基本不存在**:能在封印瞬间往硬盘写、还卡准时机的人,早就已经在机器里了——他能干更狠的(改 Python/OS/git),TOCTOU 只是最不划算的一种。自己一台可信机器上跑封印,这是理论人物不是现实威胁。
2. **是 defense-in-depth,不是补漏洞**:现有已做隔离子进程 + 每个快照文件执行前验 sha + 冻结工件 hash 钉死。这俩把"已经很紧的隔离"再拧紧,修不了"验证器对诚实输入算错答案"那种真 bug——因为没这种 bug。不做,封印也不是"不可信",只是"再难攻一点"。
3. **时点注/真瓶颈**:2026-07-05 暂缓时,项目真卡着的是 owner 手动 review 门(P1.2 close,repo 外计数、只 owner 能推),TCB 再硬化那门也不自动开;2026-07-07 该门已由 owner_manual_decision 正式 CLOSED(P1.2 CLOSED/P1.3 开启),但本项仍按发布时点/威胁模型触发条件暂缓,暂缓理由不变。
4. **是最贵最难缠的活**:Windows OS 级文件隔离出了名磨人(child 自标 windows_write_isolation_residual 是硬骨头),read-once 碰的是最敏感的代码。高成本、防理论攻击者,性价比最低。

== 何时该翻转去做(暂缓不等于永不做)==
- **封印要在不可信机器上跑**,或 **CERTIFIED 结果要交给"不信任你机器/你本人"的第三方**(别人控制的 CI runner、有硬盘写权限的对抗性审查者)——那时"机器/操作者本身被动手脚"成现实威胁,这俩立刻变重要。
- 但即便到那步,真正的终极解是那条**第四路 = proof-carrying 小核证书**(让结果不依赖谁的机器,见 [[tcb-has-solver-hard-floor-replay-mandatory]]),OS 隔离只是补丁不是终极。

== 判据内核(通用,可复用到别的"要不要现在做")==
一件事现在值不值得做,看三样:**它挡的风险现不现实、它推不推得动真正的瓶颈、它的成本配不配得上收益。** 这三条 #3/OS 隔离现在都不占,所以往后放。这跟判 (b)/② 是同一条线。

关联:语义 TCB 硬地板 + 第四路 proof-carrying [[tcb-has-solver-hard-floor-replay-mandatory]];主线排期(收口 vs TCB backlog)[[p1-2-closeout-then-tcb-backlog-order]]。
