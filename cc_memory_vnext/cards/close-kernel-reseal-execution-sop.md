---
id: close-kernel-reseal-execution-sop
kind: reference
title: close-kernel reseal 一次做对的实操 SOP——改 V99 钉死源文件后更新 4 处 pin(sink dict=v99 floor 同 dict + obligations JSON source_sha256 + checker self-pin 在 JSON)、迭代法填 sha 重跑、sha=read-bytes(纯 LF)、self-pin 在 JSON 无鸡生蛋、删 helper 触发二次 reseal
summary: 2026-07-03 T1 loader parity 改了被 V99 钉死的 binding_subproblem.py / master_model.py,一次做对完整 close-kernel reseal 的实操(补 CLAUDE.md reseal 铁律的具体步骤,发布面负责人常用)。**改一个被钉源文件要更新的 pin**:①`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` dict(在 `scripts/check_p1_2_proof_obligations.py`,同一个 dict 同时充当 registered sink pin 和 v99 sealed floor——两处检查都读它);②obligations JSON(`data/proof_obligations/p1_2_proof_obligations.json`)里该文件 entry 的 `source_sha256`(checker 要求 JSON 与 dict 一致);③**checker 自钉**——改了 checker(dict)后 checker 自身 sha 变,更新它在 **JSON** 里 sink entry 的 source_sha256(checker self-pin 在 JSON、不在源码,所以更新它不再改 checker → **无鸡生蛋**)。**sha 算法** = 文件 read-bytes 的 sha256(文件纯 LF 时 = checker `_sha256_file` 期望;先 `[IO.File]::ReadAllText` 查 hasCRLF=False)。**迭代法**:填一处 pin → 重跑 checker → 它报下一处 drift → 再填 → 直到绿(比先读懂全部 pin 结构快)。**大坑**:改被钉源文件若因删 helper 引出 ruff unused(如 `Tuple`),删它 = 再改源文件 = sha 又变 = 整条 reseal 重来一遍——所以**先把源文件 ruff 弄干净再 reseal**。**用 Edit 工具改所有 pin(保持 LF),绝不 write_text/json.dump**(Windows 会写 CRLF → 本地绿 CI 挂)。提交 pathspec 覆盖 reseal 全集(改的源文件 + checker + JSON)。external artifact(candidate_placements.json,非 tracked)另走 restore/copy,见下。
scope:
  domains:
    - close-kernel
    - reseal
    - release-engineering
  paths:
    - scripts/check_p1_2_proof_obligations.py
    - data/proof_obligations/p1_2_proof_obligations.json
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - reseal-close-kernel
    - update-source-hash-pin
    - modify-v99-sealed-file
  keywords:
    - reseal
    - close-kernel
    - V99
    - source_sha256
    - hash drift
    - sink pin
    - sealed floor
    - checker 自钉
    - self-pin
    - 鸡生蛋
    - LF
    - freeze-ritual
    - candidate_placements
    - external artifact
  negative_keywords: []
  paths:
    - scripts/check_p1_2_proof_obligations.py
    - data/proof_obligations/p1_2_proof_obligations.json
  symbols: []
  error_regex:
    - "hash drift"
    - "drifted from the v99 sealed floor"
  examples:
    - 改了 binding_subproblem.py 触发 close-kernel hash drift 怎么 reseal
    - checker 自己的 sha 变了要更新哪
    - reseal 后 preflight 又报 ruff unused
activation:
  layer_hint: L1
  must_know: false
  reason: 改到被 V99 钉死的源文件、preflight 报 hash drift 时该想起——reseal 连锁不显然(4 处 pin + 迭代 + 二次 reseal 坑),不照流程走容易漏 pin 或陷入 ruff/sha 循环。
provenance:
  op: record
  reason: 2026-07-03 T1 loader parity 一次做对完整 close-kernel reseal 的实操固化(补 CLAUDE.md 铁律骨架的具体步骤)。
  evidence:
    - "2026-07-03 T1:binding/master 各改 loader → 更新 dict(:3945/:3953)+ JSON registered(:1138/:1248)+ checker self-pin(JSON :906);删 helper 引出 binding Tuple unused,删它 sha 再变、整条 binding reseal 重来;双 checker 绿(14/59·64/82)、--full 19、--slow 44;merge 后主 checkout copy mixflow 的新 candidate_placements(45774305)同步 external。"
    - "2026-07-03 pr2-5 merge:合 +8.6k 行 close-kernel 硬化分支进 main;git ort 自动解 10/14、手动解 6 处冲突(取 theirs 超集键集);实测确认 artifact pin 保住 main 新值(a914/32664/45774305)不被分支旧值(adcc/36a)覆盖;round-20 checker 静默 exit 1→写诊断脚本 import checker 逐个跑 _check_* 挖出 20 处 drift→按实际字节 reseal(9 V99 floor + allowlist + 2 sink + checker self-pin d53731f2);双 checker 60 sinks·65/83、--full 3780、--slow 44;merge commit 6e06922。"
  updated_at: "2026-07-03"
---
close-kernel reseal 一次做对的实操(2026-07-03 T1 亲历;补 CLAUDE.md reseal 铁律的具体步骤)。

== 改一个被 V99 钉死的源文件,要更新的 4 处 pin ==
1. **`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` dict**(在 `check_p1_2_proof_obligations.py`)——**同一个 dict 兼任两职**:registered sink hash 检查 + v99 sealed floor 检查(源码里就是同一个遍历,别当成两个地方找)。
2. **obligations JSON `source_sha256`**(`data/proof_obligations/p1_2_proof_obligations.json` 里该文件 entry)——checker 有一条一致性检查要求 JSON 的 declared sha 与 dict 的 expected sha 相等,不改会报 "changed without checker-floor reseal"。
3. **checker 自钉**——你改了 dict(=改了 checker 源码),checker 自身 sha 变;它的 self-pin 在 **JSON** 里(checker 也是一个 registered sink,有自己的 entry + source_sha256)。**关键:self-pin 在 JSON 不在 checker 源码,所以更新它不会再改 checker → 无鸡生蛋**;最后算、最后填。

== sha 怎么算(和 checker 一致)==
`_sha256_file` = 文件字节的 sha256。文件**纯 LF** 时,`[IO.File]::ReadAllBytes` 的 sha256 就等于 checker 期望值。先查 `hasCRLF`:纯 LF 才这么算;有 CRLF 说明文件被污染(先修行尾)。

== 迭代法(比啃源码快)==
填一处 pin → 重跑 `check_p1_2_proof_obligations.py` → 它精确报下一处 drift(binding/master/checker...)→ 再填 → 直到 "check passed"。不必先读懂全部 pin 结构。

== 两个坑 ==
- **删 helper 触发二次 reseal**:改源文件若删了函数/import 引出 ruff unused(2026-07-03 是 binding 的 `Tuple`),删它 = **再次改源文件** = sha 又变 = 前面填的 pin 全失效、整条 reseal 重来。**对策:先把改动源文件的 ruff 弄干净(`ruff check <file>` All passed)再开始 reseal**,别边 reseal 边被 ruff 逼着二次改码。
- **绝不 write_text / json.dump 写 pin**:Windows 写 CRLF、`.gitattributes` 强制 LF → 本地绿 CI 挂。**一律用 Edit 工具**(保持原文件 LF)。

== 合并 close-kernel 分支的 reseal(2026-07-03 pr2-5 merge 亲历)==
把一条 close-kernel 硬化分支(pr2-5,+8.6k 行 checker)合进 main,reseal 面比 T1 大得多,还踩到 checker 静默失败:

- **冲突常比 `git merge-tree --trivial` 预测的少**:git ort 三方合并自动解大部分(pr2-5 merge-tree 报 18 处,实际只剩 6 处手动冲突,全在 close-kernel pin 区:V99 dict / obligations sink)。
- **冲突取硬化侧(theirs)超集键集,值靠完整 reseal**:两侧的 pin 值都别信(合并后要重算),关键是**键集取硬化分支超集**(round-20 把更多源文件纳入 V99 floor + 新增 certified_artifact_contract 为独立 sink)。解冲突时整块取 theirs,后面 reseal 按实际字节统一所有值——别手动猜 sha。
- **pin 保护陷阱(致命)**:分支侧 `certified_artifact_contract.py` 的 **artifact pin**(candidate/canonical 的 sha + size)是**合并前旧值**(pr2-5 的 adcc/36a/45,773,799)。git ort 若两侧同改 pin 行会冲突;若只 main 改了(分支没碰)则自动采纳 main 新值——但**必须 grep pin 行实测确认**(`grep -nE '"candidate_placements"|a914|adcc' contract.py`),别假设。采纳分支旧 pin = 回滚工件修复 + 运行时全 fail(CLAUDE.md「别好心更新 expected hash」的反面)。
- **checker 静默 exit 1 的诊断法(round-20 关键坑)**:round-20 checker 的 `main()` 在 `if errors: return 1`(约 `:14130`)**不打印**主检查块的 errors(只有 preflight self-check `_print_p1_2_errors` 才 print)。合并后裸跑 checker 只得 `exit 1` + **0 行输出**,挖不出 drift。**诊断法**:写脚本 `import` checker 模块(`importlib.util.spec_from_file_location`),照 `main()` 的顺序逐个调 `_check_*` 函数(`_check_close_kernel_contract` / `_check_strong_status_write_allowlist_gate` / `_check_certified_artifact_contract_runtime_anchor` …),打印每个返回的 error 列表 → 一次拿全 drift(pr2-5 合并这么挖出 20 处:1 allowlist + 19 close_kernel)。
- **reseal 顺序**:诊断挖全 drift → 用 hashlib 算每个 drift 文件的实际字节 sha(`open(f,'rb').read()`,确认 `count(b'\r\n')==0`)→ Edit 更新 V99 dict + obligations sink + allowlist pin(`STRONG_STATUS_WRITE_ALLOWLIST_SHA256` 常量,`_SIZE` 若变也改)——这些都是**稳定值**(源文件不再改)→ **最后**算改完后的 checker 自身 sha 填 obligations self-pin(改 obligations 不改 checker,无鸡生蛋)→ 重跑诊断脚本确认 0 errors → 双 checker exit 0。
- **收敛数字会增,是硬化真进 gate 的证据**:吸收硬化后 sink/allowlist 计数上涨(pr2-5:59→60 sinks、64/82→65/83),别当成错。

== 收尾 ==
- 双 checker 都要绿:`check_p1_2_proof_obligations.py` + `check_strong_status_write_allowlist.py`(删 helper 若让 strong-status write 的 AST 行号漂移,后者要更新 allowlist;2026-07-03 没漂)。
- 提交 **pathspec 覆盖 reseal 全集**(改的源文件 + checker + JSON),别裹别的。
- **external artifact**(`candidate_placements.json` 等,非 git-tracked):merge/改动后主 checkout 的副本要单独同步(copy 或 `restore_external_artifacts.py`),否则 preflight 的 external 冻结检查会 hash mismatch(`external_artifacts.json` 是 tracked、随 merge 更新,但大文件本体不随)。

reseal 铁律骨架见 CLAUDE.md;哪些文件被钉、freeze-ritual 全集见 `PROJECT_LOCK.md` 与 README 第 5 章。分工(reseal=发布面=leader 直做)见 [[agent-role-division-and-codex-collaboration]]。
