# 审查：重写后的《代码体检方案》（opus 席）

日期：2026-09-22。被审文件为 `内核维护/代码体检方案.md` 的工作区版本（未提交，mtime 18:43:55，SHA-256 `24654bd905fef808ca90e51e08ed02d59858f92a4706a6eed5b7f7952896cb9e`）。对照材料：同目录 R1–R5、`GPT-Pro-意见.md`、`GPT-Pro-第二份/`、`主会话说明.md`。下文路径相对 `求解器/`。本席的脚本、日志和 JSON 都在 [审查-opus/](审查-opus/) 下。

判定用语：**重现了**指本席实际执行并得到结果；**代码上成立但没重现**指由代码或数据推出，但没有执行；**不成立**指核查后否定。

## 0. 要点（按影响排序）

1. **缺少“第 0 批完成前”的即时规则。** 审查期间，18:55 的第四次正式源同步又跑了 `cargo test --workspace`，改写了历史证据，并永久丢失 5 个被忽略的大文件（§1、A1）。
2. **266 个被 `.gitignore` 排除的历史文件（923,691,956 字节）不受 Git 保护，方案没有安排备份。** 今天丢失的 14+5 个文件全部属于这一类。`分流器三路轮询-absolute.json` 唯一的同哈希来源也是被忽略文件，而且已知有脚本会改写它（A2）。
3. **恢复被排在隔离之后，恢复后也不提交。** 这样 HEAD 一直是被覆盖后的字节，“还原到 HEAD”这一常规补救只会把文件还原成覆盖后的版本（A3、B6）。
4. **排序与主会话判据不一致。** 第 1 批仍是 API 加固加来源绑定，候选接入不在任何批次的完成门槛里。这正是主会话批评 GPT Pro 第二份意见的地方（D1）。
5. **结构等价线里有几项改动会改变对外输出，或必然产生 A/B 差异，却没有归线：**
   - 新增或移动 `.rs` 文件与手工指纹清单的冲突（E4）；
   - 记录输出只按“解码后相等”验收（E5）；
   - 公开结构类型化和删除公开项（E2、E3）；
   - 白名单可以在结构批内扩充（E1）；
   - 第 0 批会改动参照实现（E8）。
6. **恢复块的只读部分在当前状态下全部通过（重现了）。** 但部分恢复后会有 4 处按哈希的历史引用失效；另有 13 个历史路径上现存的是后来运行写出的字节，方案没有决定怎么处理（B5、B7）。

## 1. 审查期间发生的第四次覆盖

事实经过：

- **18:51**：工作区有一轮未提交的正式源/样例同步，已跟踪文件有 67 个未提交改动，包括 `数据/正式静态目录.json`、全部 `数据/样例` 输入、8 个 fixture 和 topology 源码/测试。
- **18:55:50–18:56:23**：`crates/kernel/evidence` 下有 144 个文件的 mtime 更新（`find -newermt`），分布在 revision-r2、`round6/regressions/revision-r3`、`round6/revision-r5/cli` 等目录。其中 `revision-r2/regression-results.json` 当时的哈希为 `71c8ec89…`，`round6/regressions/revision-r3/results.json` 为 `e620d15b…`，都已不同于 HEAD（见 [spot_history.log](审查-opus/spot_history.log)）。本席随即两次通知主会话。
- **主会话处置**（据其回信和 `内核维护/2026-09-22e/第四次覆盖-处置清单.json`）：
  - 停掉了同步和测试进程；
  - 用 `git restore` 把 78 个已跟踪文件还原到 HEAD；
  - 另有 5 个被忽略文件无法还原：`revision-r4/cli/{empty-branch-run-result,full-branch-run-result,working-prefix-result}.json`、`round6/revision-r5/cli/original-cycle.record.json`、`round6/revision-r5/cli/package/full_state_each_instant/records/record.json`；
  - `delete_new` 为 0。
- **本席复核（重现了）**：18:58 重跑只读预检 [restore_dryrun.py](审查-opus/restore_dryrun.py)，输出在 [restore_dryrun-after-4th.json](审查-opus/restore_dryrun-after-4th.json)：
  - 159 项的当前哈希全部等于 manifest 的 `current_sha256`，也等于 HEAD 和 `220f7b6` 的 blob；
  - `分流器三路轮询-absolute.json` 仍等于 R3 登记的 `after_sha256`；
  - 13 个未解决项中，上述 5 个的现有哈希已不等于 R3 登记的 `after_sha256`，其余 8 个仍相等；
  - evidence 下不在 `2026-09-22/before.json` 里的文件，仍只有 R3 登记的 7 个新增文件。
  - 同目录的 `restore_dryrun-after-1857.json`（18:58:44）不是本席写的，内容与 after-4th 相同。
- **`2026-09-22e/commands.jsonl` 的记录**：
  - 第一条 `cargo test --workspace -j 6` 没有设 `KERNEL_TEST_EVIDENCE_DIR`，也没有用 PATH 包装，以 exit 143 终止；
  - 之后两条 `cargo-test-workspace-isolated` 设了变量，也用了 `bin/` 包装；
  - 它的 `history_guard.py` 做法是：测前快照，测后把已跟踪文件 `git restore --source=HEAD`，被忽略文件从测前备份拷回；
  - 备份目录 `history-untracked-backup` 在 19:01 才建立，晚于 18:55 的覆盖。

这件事对方案的含义：

1. 需要一条立即生效的规则（A1）。
2. “先跑、再还原”不是隔离，对被忽略文件无效（A5）。
3. manifest 里已跟踪项的 `current_sha256` 仍然可用；未解决项登记的 `after_sha256` 有一部分已经过期（B8）。

## 2. 第 0 批能否先于任何代码改动安全执行

**结论：照现在的写法不能。** 第 0 批本身就要改测试和工具代码（7 个入口、`tests/support`、Python 脚本、两份新工具），而且把历史恢复排在隔离验收之后。真正可以在任何代码改动之前完成的只有四件事：即时规则、备份、恢复加提交、写权限保护。建议把这四件事单列为“第 0 批第一步”。

### A1 即时规则（重现了：事故本身）

方案 §8 说“第 0 批的安全入口是重锁的前置条件”，但没有说第 0 批完成之前重锁怎么测。今天第四次同步就按惯例跑了 `cargo test --workspace`。

建议在 §1 之前加一节“即时生效”，写两条：

- **禁止运行的命令。** 第 0 批隔离验收之前，任何会话都不运行：
  - `cargo test --workspace`、`cargo test -p kernel --tests`；
  - `--test` 指定七个 CLI 目标中的任何一个；
  - R3 §3.2、§3.3 列出的脚本的 main。

  需要回归时只跑 §3.3 里不写历史的五组：kernel lib、topology lib、`--test reference`、topology `--test validation`、两组 `--doc`。R3 §3.1 和 R5 §1 核过这些入口不写固定历史路径。topology validation 只在 `求解器/target` 下建临时目录。这个子集的历史口径是 134 项，缺七个 CLI 目标。
- **任务书要求。** 派发重锁或同步任务时，把上一条原样写进任务书。

### A2 被忽略的历史大文件（重现了：统计与路径）

[ignored_inventory.py](审查-opus/ignored_inventory.py) 读仓库根 `.gitignore` 里逐路径列出的条目，结果见 [ignored_inventory.json](审查-opus/ignored_inventory.json)。共 266 个，全部存在，合计 923,691,956 字节，分布如下：

| 位置 | 文件数 |
|---|---:|
| `crates/kernel/evidence` | 18 |
| `crates/kernel/复核` | 180 |
| `数据/样例` | 34 |
| `规格/…` | 31 |
| `数据/复核` | 2 |
| `crates/kernel/tests/fixtures` | 1 |

这些文件一旦被改写，Git 无法还原；今天的 14+5 个损失全部属于这一类。方案 §3.2 只处置已经漂移的 14 个，没有保护其余 252 个。`.gitignore` 的注释写“可由内核重算”，对历史字节不成立（见 B4）。

还有一个具体风险：`分流器三路轮询-absolute.json` 唯一的同哈希来源 `数据/样例/分流器三路轮询-运行记录-v3-kernel.json` 也在忽略清单里。而 `crates/kernel/tests/finalize_round5.py` 第 13 行生成 `数据/样例/<名>-运行记录-v3-kernel.json`，第 40 行对全部 `*-v3-kernel.json` 做压缩重写（R3 §3.2 已列这个脚本；这一点代码上成立但没重现）。

建议：

- 第 0 批第一步，把这 266 个文件按内容哈希复制到仓库外的备份位置（位置由 owner 定），生成 path/size/sha256 清单，只把清单提交入库。
- §3.2 恢复块读取 absolute 源时，改为读这份备份，不直接读 `数据/样例` 下的活文件。
- `.gitignore` 的那条注释改掉。

### A3 恢复不必等隔离（代码上成立但没重现）

方案 §3.2 要求“运行前完成 §3.1 的测试隔离和现场快照”。但恢复只读 Git blob、写 160 个文件，不依赖任何代码改动；隔离则要改 7 个入口和若干脚本，周期更长。

在隔离完成之前，HEAD 里存的一直是 b/c 覆盖后的版本。任何“按 HEAD 还原”的补救（今天 18:57 那次，以及 `2026-09-22e/history_guard.py`）都会把文件还原成覆盖后的字节。先恢复并提交之后，历史树的任何写入都会出现在 `git status` 里，`git restore` 还原出来的也是正确的历史。

建议：把 §3.2 移到 §3.1 之前，前置条件改为“A1 已生效且 A2 备份完成”。

### A4 用写权限让误写立即失败（代码上成立但没重现）

恢复并提交之后，把历史树的文件和目录都去掉写权限，范围包括 `crates/kernel/evidence`、`crates/kernel/复核`、`数据/复核` 和 `规格/` 下的验证/复核子目录。

- Git 只记录可执行位，去掉写权限不会产生 diff。
- 七个入口写这些目录时会以 PermissionError 失败，而不是静默覆盖。`revision_r3_cli.py` 先 unlink 再写，也需要目录写权限。
- 代价：维护时要先临时加回写权限；`kernel_file_guard` 的权限字段要把这一状态登记为预期。
- 这一步不替代 §3.1 的隔离，作用只是把“静默覆盖”变成“测试失败”。

### A5 不能用“先跑、再还原”代替隔离

`2026-09-22/bin/python` 的包装和 `2026-09-22e/history_guard.py` 都是调用方自己临时想的办法。后者还原被忽略文件，前提是测前备份已经存在；今天备份晚于覆盖，所以失效。

方案 §3.1 已要求先在 `/tmp` 副本验收隔离。建议补一句：隔离验收之前，不得以“测后按快照还原”作为运行七个入口的条件。

### A6 第 0 批内部的先后顺序

§3.1 说“开始时保存文件保护清单”，用的是 §2 里还没写的 `kernel_file_guard.py`。写这个工具只是新增文件，不影响保护集，但方案应写明顺序：

1. 写 guard 工具（工具写好之前，可以用 R2 的 `protect.py` 或 `before.json` 的格式先做一份快照）；
2. 快照；
3. 备份、恢复、提交；
4. 隔离改造。

## 3. 恢复清单与办法

### B1 清单、版本和预检（重现了）

[restore_dryrun.py](审查-opus/restore_dryrun.py) 只读地执行了方案恢复块的全部读取与断言部分，不备份、不写入。18:49 和 18:58 两次结果相同：

```text
rows=159 unique_paths=159 resolve_ok=159
expected_matches_source=159 equivalent_equal=159
current_is_current_sha=159 current_is_expected_sha=0 current_other=[]
head_equals_current=159 blob_220f7b6_equals_current=159
history_check_fail=[]            # f8f6129..7da52a7 之间没有提交改动这 159 个路径
untracked_drift=14 untracked_key_current_is_after=True untracked_key_source_matches_before=True
```

另外，159 项的 `expected_sha256` 与 `2026-09-22/before.json` 登记的当天执行前哈希全部相同（0 个不符）。

`2026-09-22/before.json` 的全部 5906 项与当前字节对比，有 263 项不同（[full_before_compare.json](审查-opus/full_before_compare.json)）：evidence 159 个已跟踪项和 14 个未跟踪项之外，其余都是活动源、样例、规格、会议成果等当天的正常改动，不属于历史恢复范围。方案“恢复 `f8f6129`，完成数为 160 个目标、13 项待找”的判断成立。

### B2 抽查 Git 历史（重现了）

见 [spot_history.log](审查-opus/spot_history.log)：

- 抽查的 5 个旧文件，`f8f6129` 与 `7da52a7` 的 blob 相同，`a7539f5` 都改了。其中 3 个在 `220f7b6` 又改了一次，另外 2 个（`revision-r4/cli/extra-trigger-run-result.json`、`round6/revision-r5/cli/results.json`）在 `220f7b6` 没有再变，这与 R3 §8 的“—”标记一致。
- `round5/round5_cli/resource-statistics.json` 和 `bounded-reference-batch-unsupported.log` 在 `f8f6129`、`7da52a7` 都不存在，首次出现在 `a7539f5`，与“7 个新增文件”的分类一致。
- `round6/cli/none.json` 旧版 `61d1e7d1…`、新版 `37897c0b…`，与 R3 §4.1 一致。

### B3 13 项找不到原字节（重现了：在下述范围内未找到）

- **按大小搜索。** 用 `before.json` 登记的原始大小，在 `/home /tmp /var/tmp /mnt /media /opt /srv` 下做 `find -xdev` 等长搜索（[size_candidates.txt](审查-opus/size_candidates.txt)），只找到 5 个同长文件：
  - absolute 的已知来源；
  - 4 个同哈希 `3bf914b6…` 的复核记录，不匹配任何目标。
- **搜索 Git 对象。** 4 个 Git 仓库的全部对象里都没有同长 blob（[git_object_search.json](审查-opus/git_object_search.json)）：本仓库、`~/zmd-project-cc`、`~/.claude/skills`、`~/文档/ChatGPT/New project`。
- **注意数据陷阱。** R3 `pre_day_hash_drift.json` 的 `bytes` 字段是覆盖后的大小，不是原大小。例如 `empty-branch-run-result.json` 在该字段记为 2,032,087，`before.json` 记为 2,034,563。拿这个字段去找备份会全部错过；[unresolved_targets.json](审查-opus/unresolved_targets.json) 给出了正确的原大小。

### B4 13 项无法重算（代码上成立但没重现）

[fingerprint_vs_f8.py](审查-opus/fingerprint_vs_f8.py) 取 `f8f6129` 里的 `round6/cli/referenced-zero-prefix.record.json`，比对它记录的 36 项来源。其中 20 项与 `f8f6129` 同路径文件的哈希不同，包括：

- 源码：`config.rs`、`engine.rs`、`warehouse.rs`、`polling.rs`、`transition.rs`、`output.rs`、`cycle.rs`、`cycle_io.rs`、`main.rs`；
- 配置、目录、规格和两份正式源。

也就是说，这批历史记录出自 `f8f6129` 之前、从未入库的实现。用任何现存版本重跑，都得不到原字节。

建议：§3.2 不要写“查到匹配备份才核销”这种没有期限的待办，改为写明本次搜索的范围与结果，把 13 项登记为“已丢失（仅存哈希与大小）”；owner 如另有离线备份，找到后再核销。

### B5 部分恢复后的失效引用（重现了：读 blob 比对哈希）

恢复后的 `f8f6129` 版本中，有 4 个文件按哈希引用了无法恢复的文件：

| 恢复后的文件 | 引用的不可恢复文件 |
|---|---|
| `round6/cli/referenced.json` | `round6/cli/referenced.record.json` |
| `round6/cli/referenced-relative.json` | `round6/cli/referenced.record.json` |
| `round6/revision-r5/cli/original-cycle.json` | `round6/revision-r5/cli/original-cycle.record.json`（与上面那个文件原哈希同为 `6a3a68e6…`） |
| `round6/revision-r5/cli/package/full_state_each_instant/certificates/cycle.json` | 同包内的 `records/record.json` |

`revision-r2/regression-results.json` 引用的 absolute 文件可以恢复，不在此列。

建议：`history_recovery=partial` 的登记逐条列出这 4 处引用，写明这些证书的记录引用已不能核验。以后任何验证工具读这几个旧包时报错，属于已知项。

### B6 恢复后要提交（代码上成立但没重现；今天 18:57 的处置演示了这个机制）

方案没有写恢复之后提交。不提交的话，HEAD 仍是 `220f7b6` 的字节，`git restore`、`git checkout`，以及 `history_guard` 一类“还原到 HEAD”的操作，都会把恢复撤销。

建议：恢复验收后，由主会话单独提交一次，只包含这 160 个文件和 restore-journal 摘要。从这次提交起，HEAD 才是历史树的基准。

### B7 13 个历史路径上现存的字节（代码上成立但没重现）

恢复块不动这 13 项，所以它们原位留着 b、c 或第四次运行写出的字节，而路径属于历史树。§3.2 对 159 项采用的原则是“历史路径只存原字节”。这些文件留在原位，会被验证和审计脚本当作历史读取，而且与引用它们的证书哈希不符（B5）。

建议 owner 二选一：

- **(a)** 移到本次运行目录保存，原位不留文件，在登记里写明；
- **(b)** 原位保留，在登记和树内的说明文件里标明它们不是历史。

本席倾向 (a)。

### B8 恢复块的细节

- **写入不是原子的。** `p.write_bytes(old)` 如果中途中断，会留下截断文件，其哈希既不是 current 也不是 expected。方案说新运行“按当前哈希预检后可处理上次中断”，但预检会在这里断言失败。建议先写同目录临时文件再 `os.replace`；或者预检时额外接受“等于上次运行备份目录中登记的哈希”（代码上成立但没重现）。
- **未解决项的哈希已过期。** journal 的 `unresolved` 直接复制 drift 行，其中 5 项的 `after_sha256` 已经过期（§1）。建议恢复时逐项记录当时实测的哈希和大小。
- **7 个新增文件只给了一个例子。** 建议给出完整循环，并保持相对目录：

```bash
for rev in a7539f5 220f7b6; do
  for p in round5/round5_cli/{invalid-cycle-input,invalid-cycle-result,relocated-seed,resource-statistics}.json \
           round6/revision-r5/cli/bounded-reference-batch-unsupported.log \
           'round6/revision-r5/cli/bounded-reference-package/分流器三路轮询-reference.json' \
           'round6/revision-r5/cli/bounded-reference-package/混做粉碎机两下游-reference.json'; do
    mkdir -p "$HEALTH_RUN/relock-history/$rev/$(dirname "$p")"
    git -C .. show "$rev:求解器/crates/kernel/evidence/$p" > "$HEALTH_RUN/relock-history/$rev/$p"
  done
done
```

- **7 个新增文件继续留在历史树里。** `round5/round5_cli/` 和 `bounded-reference-*` 是 9-22 测试写出的当前产物，建议在所在目录放一份说明，写明来源提交和“不是 round5/round6 原始证据”。

### B9 维护记录里的失实声明（R3 §5 已核：重现了）

`2026-09-22b`、`2026-09-22c` 的 `relock.json` 写着 `"historical_outputs": "unchanged; not relabeled as current evidence"`，已被 Git 和 `before.json` 反证。`2026-09-22e` 是同类情况。方案没有处置这件事。

建议：不改这些维护目录的原文件，另写一份勘误登记，逐条指出失实的声明和实际改动清单。§8 第 6 步已把“历史未变”限定为最终字节审计的结论，可以保持。

## 4. 与核实报告不符或说过头的地方

### C1 §3.3 说该安全入口“同时包含已有来源篡改与负例测试”（对 `reference.rs` 不成立）

`reference.rs` 只有 3 个测试：`crusher_reference`、`splitter_reference`、`live_python_differential`（`grep '#\[test\]'` 和 R5 §5 都是如此），没有篡改负例。CLI 级的来源篡改负例在 `revision_r5_cli.py`（reject-hash、reject-producer 等）和 `round6_cli.py`（tamper）里，恰好属于隔离前不能跑的七个入口。库测试里也有一部分篡改负例，例如 `tests_revision_r2.rs:272` 的 run_id 伪造。

建议改为：“隔离前的安全子集不含 CLI 级来源篡改负例；库测试内的篡改负例另列。”

### C2 §4.2 放进缺陷修复线（与 R5 不一致）

R5 明确说“不表示失败封存本身是缺陷”，并核到：

- 4 个失败态送入 `checkpoint_input` 和 `Engine::new_production` 都被拒绝；
- 输出层已经区分完整前缀与部分审计。

加固线的验收要求是“每项有最小反例……反例须表现出预定变化”，而 §4.2 没有这样的反例。

建议：§4.2 改为“候选接入需要在 Rust API 层做 checkpoint/resume 时再做”；或者先补出一个会导致错误交付物的反例，再列入第 1 批。

### C3 §1 说“第 1 批先固定候选所需输入/恢复契约”（与 R1 §4.1 不一致）

R1 核到：活动的非测试调用方中，没有在构造后改写 `engine.state`、`memory`、`production_abstraction` 的地方。候选经 JSON 进入 `Input::parse` 再走 CLI，§9.1 本身也是这样写的，并不经过这些公开字段。§4.1 的 30 个测试函数迁移不是候选接入的前提。

建议删去这句，或写明候选实际依赖第 1 批的哪一项（见 D1）。

### C4 没有标判定等级的陈述

§3.1 说“`benchmark_round6.py --out-dir` 仍固定改写样例”，R3 §6.2 对此的判定是“代码上成立但没重现”，方案却按已证事实陈述。建议照 §4.3 对 verify-batch 依赖的写法，加上判定标注。

### C5 数字核对：未发现不符

以下数字都与对应报告一致：

- R1：24 个公开字段、8 处访问、16 条诊断、30 个函数、50 个起点；
- R2：44 组、5 组、`/elapsed_ns`；
- R3：159/7/14，目录计数 2/23/12/79/43，106；
- R4：各测点数值；
- R5：134/141、reference 覆盖；
- `functions.json`：超过 80 行的函数 30 个，其中测试函数 2 个。

## 5. 排序与主会话判据

### D1 第 1 批的内容与主会话判据相反

主会话说明的判据是：第一，实际损害；第二，挡住候选接入的；第三，证据可信度，只修到结论依赖它的程度；第四，纯整理。主会话批评 GPT Pro 第二份意见“把来源闭包清单、API 加固这类事排在最前面”。

新方案的批次表里，第 1 批仍是“状态边界与来源绑定”；候选接入只在 §9.1，写的是“完成第 0 批和候选所需的第 1 批边界后……即可独立推进”，没有任何批次以候选接入作为完成门槛。方案全文也没有引用候选的输入契约 `数据/送料契约.md`。

建议批次改为：

- **第 0 批**：
  1. 即时规则、备份、恢复与提交（不改代码）；
  2. 测试隔离；
  3. 基线与 A/A。
- **第 1 批：候选接入。** 适配器在现有合法样例上完成一次往返：导出 → `Input::parse` → seed/check → run/cycle（即 §9.1 已写的内容），以 `数据/送料契约.md` 为输入契约。每个接入阻塞用一个最小修复子批解决。
- **第 2 批：证据可信度，按交付物的依赖取舍。**
  - §4.3 构建来源：候选交付记录会引用实现来源，属于结论依赖，保留。它也是 E4 的前置条件。
  - §4.1 先做最小版本：公开字段改为 `pub(crate)`，适配 `main.rs` 的 8 处访问（R1 §5.1 已在副本上核过这个代价），并让 `Engine::cycle_key` 与独立入口的校验一致。完整的“可编辑输入与已验证实例”拆分和 30 个测试迁移，等候选或外部调用方确实需要 Rust API 时再做。
  - §4.2 的处理同 C2。
- **之后**：结构批和资源批不变。

## 6. 两条线的验收是否分开，结构线里是否混入了对外行为变化

§1 两条线的验收栏写法本身是分开的。问题出在具体条目上：

### E1 白名单可以在结构批内扩充

§1 说“只有第 0 批登记的来源映射和测量字段采用专门比较”。§3.5 末段又说“出现新差异先定位原因，确有测量/来源理由时补独立证据、更新表并重跑 A/A”。两处冲突，后者让结构批的实施者可以在同一单元里先扩白名单、再过验收。

建议：

- 测量类豁免只能由 A/A（同一二进制重复运行）中出现的差异产生。只在 A/B 中出现的差异，按定义就是行为差异，不能登记为测量字段。
- 来源映射的新实例按第 0 批登记的规则机械展开。
- 要增加新规则，单列为一个工作单元，由不同席位复核。

### E2 Progress 的内部类型化（§5）

`model::Progress` 和 `State` 都是 pub 结构（`model.rs:38–48、121–130`），同时也是 JSON 序列化类型。如果直接改 `phase` 字段的类型，Rust 公开 API 就变了，这属于 §1 “外部接口：Rust API 的可用性”这一观察层。

建议写明：公开的序列化类型 `model::Progress` 保持不变；受约束的阶段类型只存在于内部，在校验通过处转换。否则这项改动归加固线。

### E3 §6.3 删除“真正无入口的冗余代码”

对 lib crate 的 pub 项来说，“仓库内无调用”不等于“无入口”。R1 §4.4 列出了 `tests/legacy_probes`、`复核/` 下依赖公开字段的外部程序。

建议：删除 pub 项（字段、函数、类型、模块）归加固线，并附迁移表；结构线只删 private 和 `pub(crate)` 项。

### E4 新增或移动 `.rs` 文件与手工指纹清单冲突

`output.rs:173–196` 手工列了 20 个源文件（R2 §2）。第 2、3 批如果把结构体或 helper 提取到新文件，只有两种结果：

- **不改清单**：新文件不进入来源，这正是 R2 已重现的遗漏；
- **改清单**：所有记录的 `fingerprints` 和 `evidence_scope/context_bindings` 数组的长度与索引都会变，属于对外输出变化。

两种都不是结构等价。

建议：把“§4.3 构建身份已上线，并覆盖模块图”列为新增、移动、删除任何已编译 `.rs` 文件的前置条件。在此之前，结构批只在现有 20 个文件内部搬移。

### E5 记录输出只按“完整解码记录”验收不够（§7.2）

记录文件的字节会被其他产物按 SHA-256 引用。本席在 §8 正向链的实测里看到，`cycle.json` 的 `/run_record_ref/sha256` 等于 `cycle.record.json` 的实测哈希 `60b9593f…`，`/replay_input_ref/sha256` 同理。记录由 `main.rs:319–324` 和 `cycle_io::write_json` 用 `to_string_pretty` 一次写出。格式、空白或键序一变，即使解码后相同，这些哈希也会变。

建议：结构线下的输出优化，以 CLI 输出文件逐字节相同作为验收标准；只要逐字节不同，就归加固线的格式变更。

### E6 派生哈希字段的连锁差异（§3.5）

任何一个源文件改动都会连锁：记录的 fingerprints 变 → 记录字节变 → 证书的 `/run_record_ref/sha256` 必然变。§3.5 只举了 `/producer/path`、`/out`、`/verified_record` 作例子。

建议登记一条规则：引用型哈希字段的验收，是“等于候选侧被引用产物的实测哈希，且被引用产物本身通过 A/B”，不用白名单跳过。

### E7 基线不能跨重锁复用

§3.5 写“`HEALTH_BASELINE` 指向上批封存的同语料 capture 目录”。今天一天就有四次正式源/样例同步，每次都改 `数据/样例` 的输入和目录（本次工作区有 67 个已跟踪文件改动）。上一批封存的输入哈希与当前不同，“同语料”就不成立了。

建议：A/B 比较时，A 从冻结的改动前源码副本（§3.4 的 `/tmp` 方法）重新构建，对当前输入做 capture，B 同时 capture。封存的旧基线只用于 A/A 自检和回溯，不直接与跨过重锁的 B 比较。另一种办法是规定结构批期间冻结重锁。

### E8 第 0 批会改动参照实现（重现了：读取参考记录）

§3.1 计划把 `check_golden_trace.py`、`check_splitter_trace.py` 拆成只读函数入口和写回用的 main。这两个脚本有两重身份：

- 它们是 `reference.rs` 现场差分导入的独立参照（R5 §5）；
- 它们作为 checker 登记在两份当前参考记录（`数据/样例/*-参考运行记录.json`）的 fingerprints 里。这两份记录的 checker 共有 12 个脚本，还包括 `test_round4.py`、`test_runtime_input.py`、`check_port_meeting.py` 等，其中几个也在 R3 的写入清单上。

建议：

- 第 0 批对这些脚本的改动，验收标准是改前改后 `run()` 对两个场景的输出逐字节相同；
- 两份参考记录的 checker 指纹会因此过时，登记为下一次重锁的更新项，不在第 0 批顺手重新生成。

### E9 `crates/kernel/周期键读取审计.md` 与代码耦合

这份文档以 semantics 角色进入每条记录的指纹（`output.rs:172`），正文引用了 `engine.rs::compute_physical`、`validate_inventory` 等函数名。结构批一旦移动这些函数，要么文档失真，要么改文档从而改变指纹。

建议：在第 2、3 批的读写对照中，列出这份文档需要同步更新，并按来源映射登记。

## 7. 命令能否照着执行

- **F1 shell 语法（代码上成立但没重现）。**
  - 问题：方案的代码块是 bash 语法（heredoc、`: "${…:?}"`、`for…do`），而会话环境登记的登录 shell 是 fish（`/bin/fish`）。在 fish 里直接粘贴 §3.2、§3.3、§7.1 的代码块会失败；各块还依赖 §2 导出的变量。本席的 Bash 工具实际是 zsh，没有在 fish 里试。
  - 建议：§2 把变量写进 `"$HEALTH_RUN/env.sh"`，每个代码块用 `bash` 执行，开头先 `source` 它；或者把这些步骤全部做成运行器的子命令。
- **F2 `exit` 会关掉终端。** §3.3 循环里的 `|| exit "$?"` 在交互 shell 里会关闭终端，建议改为脚本内 `set -e`，或改用 `|| break`。
- **F3 `HEALTH_BIN` 未定义且同名异物（重现了取值方法）。**
  - 问题：§8 说“使用 §3.4 已绑定的 `HEALTH_BIN`”，但 §3.4 没有定义这个变量；§7.1 又用 `HEALTH_BIN` 指 release 性能产物。
  - 建议：分成 `HEALTH_DEV_BIN` 和 `HEALTH_PERF_BIN` 两个名字，并给出取值命令。`jq` 已安装，本席用同样格式在独立 profile `healthreview721412` 下构建后，取得 `target/healthreview721412/kernel`：

  ```bash
  jq -r 'select(.reason=="compiler-artifact" and .target.name=="kernel" and (.target.kind|index("bin"))) | .executable' \
    "$HEALTH_RUN/build-artifacts.jsonl.log"
  ```

- **F4 GNU time 不存在（重现了：调用失败）。**
  - 问题：`/usr/bin/time` 不存在，本席第一次调用即失败，与 R4 一致。R4 当时是用 curl 下载软件包再解出程序。
  - 建议：owner 用 `sudo pacman -S time` 安装；或者让运行器用 Python 的 `os.wait4` 读取 `ru_maxrss`，那是 GNU time 读的同一份内核统计，就不再依赖外部程序。
- **F5 `kernel_file_guard.py verify` 缺少允许清单参数。** §2 的职责表要求它对照“允许变化清单”，但命令行里没有对应参数，建议在契约里写明 `--allow <json>`。
- **F6 §8 正向链照原文可以执行（重现了）。** 本席用独立 profile 构建的二进制，把 `HEALTH_RUN` 指向 [section8/](审查-opus/section8/)，照 §8 原文执行 8 条命令，全部退出 0（[exit-codes.log](审查-opus/section8/positive/exit-codes.log)）：cycle 结果为 `diagnostic_cycle`，verify-cycle 返回 `cycle_replayed=true`、`period=20`。执行时工作区处于第四次同步的未提交状态。
- **F7 §3.2 恢复块的只读部分可以执行（重现了）。** 见 B1。
- **F8 `cargo metadata` 可以执行（重现了）。** `cargo metadata --locked --offline --no-deps --format-version 1` 退出 0。
- **F9 codegen 环境覆盖会让共享 target 反复重编？（不成立）** §2 设了 `CARGO_PROFILE_*_CODEGEN_UNITS`，本席担心这会和其他会话互相冲掉编译产物。在独立 profile 上实测（[codegen-env.log](审查-opus/codegen-env.log)）：
  - 加上覆盖后重编了一次；
  - 保持覆盖再构建，Fresh；
  - 去掉覆盖再构建，仍是 Fresh。

  两套产物按不同的元数据哈希并存，代价只是第一次多编一次。

## 8. 本席执行的命令与原始输出

以下命令都在 `/home/zhuran24/zmd-research-fresh/求解器` 下执行，`CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target`。

| 命令 | 输出 |
|---|---|
| `python -B 内核维护/2026-09-22d/审查-opus/restore_dryrun.py` | 18:49 一次、18:58 一次，见 B1；[restore_dryrun.json](审查-opus/restore_dryrun.json)、[restore_dryrun-after-4th.json](审查-opus/restore_dryrun-after-4th.json) |
| `python -B …/full_before_compare.py` | 5906 项中 263 项不同，没有缺失文件 |
| `python3 -B …/ignored_inventory.py` | 列出 266 个，全部存在，923,691,956 字节 |
| `find /home /tmp /var/tmp /mnt /media /opt /srv -xdev -type f \( -size …c -o … \)` | 5 个候选，均不匹配 13 个目标 |
| `python -B …/git_object_search.py <4 个仓库>` | 同长 blob 均为 0 |
| `python3 -B …/fingerprint_vs_f8.py <两个 f8f6129 记录>` | referenced-zero-prefix：36 项来源中 20 项不符 |
| `git log` 及 `git show <rev>:<path> \| sha256sum`（7 个文件） | [spot_history.log](审查-opus/spot_history.log) |
| `cargo build --locked --offline -p kernel --lib/--bin kernel -j 2 --profile healthreview721412 --config 'profile.healthreview721412.inherits="dev"'` | 退出 0；[codegen-env.log](审查-opus/codegen-env.log)、[review-build.jsonl.log](审查-opus/review-build.jsonl.log) |
| §8 正向链 8 条命令 | 全部退出 0；[section8/positive/](审查-opus/section8/positive/) |

## 9. 写入范围

- 本报告，以及 `2026-09-22d/审查-opus/` 下的脚本、日志、JSON 和 §8 正向链输出（`section8/positive/`，约 4 MB 的 JSON）。
- 共享 target 下的 `target/healthreview721412/` 编译产物。
- 没有修改生产源码、测试、黄金、历史证据、正式文件、样例或方案原文；没有运行 `cargo test`；没有做 Git 写操作。
- 第四次覆盖不是本席造成的，处置由主会话完成（§1）。
