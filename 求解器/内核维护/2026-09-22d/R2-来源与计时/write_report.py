from probe_common import *
aa=json.loads((OUT/'aa/results.json').read_text());summary=json.loads((OUT/'aa/summary.json').read_text());source=json.loads((OUT/'source/summary.json').read_text());old=source['existing_source'];module=source['new_module'];base=json.loads((OUT/'baseline.json').read_text());protect=json.loads((OUT/'protection-summary.json').read_text());cache=json.loads((OUT/'cache-origin/summary.json').read_text())
P='R2-来源与计时/'
commands=['# A/A 完整命令与原始输出索引','', '每组 a、b 的 argv、cwd、环境和目标路径相同，按 a 完成后 b 开始的次序执行。结果写入同一个自有目标路径，再分别保存其原始字节；没有路径映射或字段过滤。环境、二进制身份见 [baseline.json](baseline.json)。','']
rows=[]
for r in aa:
 name=r['name'];un=[]
 for channel,v in {'stdout':r['stdout'],'stderr':r['stderr'],**r['files']}.items():
  if not v['byte_equal']:un.extend(channel+'.'+x['path'] for x in v.get('json_differences',[]))
 commands += [f'**{name}**','', '```sh',r['shell_command'],'```','', f"退出码 a/b：{r['exit_codes'][0]}/{r['exit_codes'][1]}；不稳定路径："+('、'.join(un) or '无')+'。','',f'[a 命令](aa/{name}/a.command.json) · [a stdout](aa/{name}/a.stdout.log) · [a stderr](aa/{name}/a.stderr.log) · [b 命令](aa/{name}/b.command.json) · [b stdout](aa/{name}/b.stdout.log) · [b stderr](aa/{name}/b.stderr.log)','']
 for key in r['files']:commands += [f'产物 `{key}`：[a](aa/{name}/a.{key}.json) · [b](aa/{name}/b.{key}.json)','']
 cmdname=Path(r['argv'][0]).name
 args=r['argv'][1:]
 concise=[]
 for x in args:
  xp=Path(x)
  concise.append(xp.name if '/' in x else x)
 short=' '.join(concise) or '（无参数）'
 rows.append(f"| [{name}]({P}aa/{name}/a.command.json) | `{short}` | {r['exit_codes'][0]}/{r['exit_codes'][1]} | "+('；'.join('`'+x+'`' for x in un) or '无')+' |')
(OUT/'commands.md').write_text('\n'.join(commands))
allow={'scope':'Observed A/A cases only; do not filter other fields or automatically extend this list. Original byte outputs remain authoritative.','paths':[{'command':'run','conditions':'--no-output and reaches timed execution, including completed, ticks=0, or step-stop branches','transport':'stdout when --out absent; JSON file specified by --out otherwise','json_path':'$["elapsed_ns"]','json_pointer':'/elapsed_ns','type':'string of decimal nanoseconds'}],'observations':summary['unstable'],'all_other_observed_fields':'strictly equal','not_exempt':['event/state time','run_id','result_id','fingerprints','evidence_scope.context_bindings','stop','basis','out','verified_record','array_order']}
dump(OUT/'observed-unstable-fields.json',allow)
# Persist small, line-numbered source extracts, not source-tree snapshots.
ranges={'crates/kernel/src/output.rs':[(148,212),(214,224),(518,526),(580,620)],'crates/kernel/src/catalog.rs':[(47,68),(83,91)],'crates/kernel/src/main.rs':[(14,45),(138,150),(225,275),(319,347)],'crates/kernel/src/cycle_io.rs':[(58,73)],'crates/kernel/tests/verify_all.py':[(7,16),(17,58)]}
excerpts=[]
for rel,spans in ranges.items():
 lines=(ROOT/rel).read_text().splitlines();excerpts.append(rel+'\n')
 for lo,hi in spans:excerpts.extend(f'{i}: {lines[i-1]}\n' for i in range(lo,hi+1))
 excerpts.append('\n')
(OUT/'code-evidence.log').write_text(''.join(excerpts))
text=f'''# 来源指纹与 CLI A/A 复核

日期：2026-09-22。状态：已完成。范围：GPT Pro 意见第二、三节。总体判定：**重现了**；(a) 来源未绑定二进制及新增模块遗漏均已实测复现；(b) 严格字节比较被真实计时破坏已复现。A/A 共 44 组、88 次执行，5 组有差异，观测到的全部不稳定字段只有根字段 `$["elapsed_ns"]`，其余 39 组的全部输出逐字节相同。

来源对照证明实现身份失配；物理轨迹正确性和完整周期证明有效性不在本次验证范围。

**1. 被核版本、方法与证据位置**

工作区 `/home/zhuran24/zmd-research-fresh/求解器`；开始时 Git HEAD 为 `5574911008304c6b01d0fa76c234d0d519e72e1b`。先全文读取 [GPT Pro 意见](GPT-Pro-意见.md)，再读取 [体检方案](../代码体检方案.md)。三个重锁提交的只读清单保存为 [git-history.stdout.log]({P}git-history.stdout.log)，不将历史测试通过当成本次验证。

工具链为 rustc 1.98.1 / Cargo 1.98.1。全部构建使用 `CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target`；Cargo `-j 1`、codegen-units=1、Rayon/OMP=1，执行进程限制在 0–5 共 6 个 CPU 上。没有启动代理并行工作，没有运行 Cargo 测试或任何历史目录写入测试。构建采用独立 `r2audit` profile（继承 dev，debug=0），不覆盖既有 debug/release 标准二进制。完整命令、环境和输入哈希在 [baseline.json]({P}baseline.json)。

```sh
CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target CARGO_BUILD_JOBS=1 \\
cargo build --locked --offline --workspace --bins --profile r2audit \\
  --config 'profile.r2audit.inherits="dev"' \\
  --config profile.r2audit.codegen-units=1 --config profile.r2audit.debug=0 -j 1
```

基线 kernel 保存为 `target/r2-source-timing-20260922/kernel-baseline`，SHA-256 为 `{base['binaries']['kernel']['sha256']}`；topology 为 `{base['binaries']['topology']['sha256']}`。A/A 前后重新核哈希一致。此处计时用于检测不稳定性，不是性能基准，不能直接与 release 耗时比较。所有新记录、标准输出、错误输出、命令元数据和比较结果都在 [证据目录]({P})，二进制和编译产物仅在共享 target。源码对照副本仅在 `/tmp`。

**2. (a) 代码级证据：运行时磁盘指纹与手工清单**

| 代码定位（相对于求解器） | 原文关键片段 | 含义 |
|---|---|---|
| `crates/kernel/src/output.rs:153–156` | `PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize()` | `env!` 在编译期嵌入目录字符串；路径解析和后续哈希在函数运行时发生，并非在编译期嵌入源码字节。移动或重命名二进制不改变该字符串。 |
| `crates/kernel/src/output.rs:173–195` | `for p in ["value.rs", ... , "lib.rs", "main.rs"]`；`root.join("crates/kernel/src").join(p)` | 20 个 Rust 源文件手工枚举，没有遍历目录、Cargo 模块图或自动跟踪新模块。 |
| `crates/kernel/src/output.rs:197–200` | `for p in ["Cargo.toml", "Cargo.lock", "crates/kernel/Cargo.toml"]`；`paths.extend(extra.iter().cloned())` | 另列 3 个 Cargo 文件；extra 只有显式传入才加入。 |
| `crates/kernel/src/output.rs:203–210` | `p.canonicalize()`；`json!({{"role":role,"path":path,"sha256":sha256(&path)?}})` | 逐个读取当前路径的字节，没有从二进制身份反推源码。 |
| `crates/kernel/src/catalog.rs:48–52` | `Command::new("sha256sum").arg("--").arg(path).output()` | 运行时启动外部 sha256sum，实际读当时磁盘文件。 |
| `crates/kernel/src/output.rs:518–521` | `let sources = fingerprints(...)`；`"fingerprints":sources` | 每次生成记录时重新取来源。 |
| `crates/kernel/src/output.rs:221` | `"context_bindings":sources.iter().map(...)` | 同一份哈希也复制进证据范围绑定。 |
| `crates/kernel/src/cycle_io.rs:58–73`；`output.rs:587,607–618` | `sha256(&p)? != row["sha256"]`；`let recomputed = run_record(...)`；`if record != recomputed` | 验证器先核当前磁盘哈希，再由自身重跑同一枚举，不能独立发现两端共漏的模块或旧产物与现源码失配。 |

20 个 Rust 文件的完整名单是：`value.rs`、`config.rs`、`model.rs`、`catalog.rs`、`input.rs`、`interfaces.rs`、`engine.rs`、`event_identity.rs`、`warehouse.rs`、`polling.rs`、`transition.rs`、`output.rs`、`ledger.rs`、`cycle.rs`、`cycle_io.rs`、`digest.rs`、`seed.rs`、`cache.rs`、`lib.rs`、`main.rs`。逐行摘录在 [code-evidence.log]({P}code-evidence.log)。结论针对这个手工机制，不声称当前已经遗漏某个既有生产模块；下面用真实新增模块验证遗漏风险。

**3. (a) 实测：旧二进制输出修改后源码哈希**

探针 [source_probe.py]({P}source_probe.py) 从原工作区复制必要源码、清单、嵌入数据及语义文件到 `{source['copy_root']}`，复制清单与初始 SHA 在 [copy-manifest.json]({P}source/copy-manifest.json)。正式实验使用共享 target 下独立 `{source['build_argv'][source['build_argv'].index('--profile')+1]}` profile，并断言初始输出的 `producer.path` 正确指向这个 `/tmp` 副本。

实验按以下顺序执行：

1. 编译未修改副本，保存旧二进制；对原始 `生产循环环带.json` 运行 2 tick，保存记录。
2. 仅修改 `/tmp` 的 `output.rs`，把生成记录的 `producer.claim` 常量替换为 `R2_TMP_NEW_SOURCE_PRODUCER_MARKER`；此时不重新编译。改动是可观察的输出差异，避免只改注释无法分辨新旧执行逻辑。补丁在 [existing-source-change.log]({P}source/existing-source-change.log)。
3. 使用同一个旧二进制、同一个输入和同一组参数再次运行。二进制 SHA 不变；输出仍含旧 claim，但 `output.rs` 的来源哈希已更新。
4. 用旧二进制验证第 3 步记录，退出 0；用它验证修改源码前的第 1 步记录，退出 2，提示来源指纹不符。
5. 重新编译新源码，输出新 claim；新二进制验证第 3 步旧逻辑记录，退出 2，提示交付记录与完整重算逐字段不同。

| 对象 | 源码修改前 | 修改后、尚未重编译 |
|---|---|---|
| 旧二进制 SHA-256 | `{old['old_binary_sha256_before']}` | 相同 |
| `output.rs` SHA-256 | `{old['source_sha256_before']}` | `{old['source_sha256_after']}` |
| 输出所报 `output.rs` SHA | 修改前 SHA | 修改后 SHA |
| `producer.claim` | 原 claim | 原 claim；重编译后才出现新 marker |

两份旧二进制输出的完整差异恰为：

```text
$["fingerprints"][25]["sha256"]
$["evidence_scope"]["context_bindings"][25]["sha256"]
```

索引 25 对应该输入下的 `/tmp/.../crates/kernel/src/output.rs`，不是跨输入固定索引。新二进制输出与旧二进制修改后输出仅差 `$["producer"]["claim"]`。机器结果与全长哈希在 [source/summary.json]({P}source/summary.json)。这里不是 A/A 自发波动，而是有意改变外部源码、保持二进制不变的对照。

可直接查看实际命令与原始结果：

- [修改前运行]({P}source/original-before.command.json) → [记录]({P}source/original-before.json)。
- [旧二进制运行新源码目录]({P}source/old-binary-new-source.command.json) → [记录]({P}source/old-binary-new-source.json)。
- [旧二进制验新记录]({P}source/verify-old-on-new-source-record.command.json) → [stdout，退出 0]({P}source/verify-old-on-new-source-record.stdout.log)。
- [旧二进制验旧记录]({P}source/verify-old-on-pre-edit-record.command.json) → [stdout，退出 2]({P}source/verify-old-on-pre-edit-record.stdout.log)。
- [重编译新源码]({P}source/build-tmp-marker.command.json) → [新记录]({P}source/rebuilt-new-source.json)；[新二进制验旧逻辑记录]({P}source/verify-new-on-old-record.command.json) → [stdout，退出 2]({P}source/verify-new-on-old-record.stdout.log)。

判定：**重现了**。演示只改变副本中的来源说明字段，证明实现身份不能由当前来源哈希推出；不据此声称真实转移逻辑错误。

**4. (a) 实测：新增已编译模块遗漏**

同一副本中添加 `pub mod r2_omitted_probe;`，令 `output.rs` 的 claim 使用 `crate::r2_omitted_probe::CLAIM`，新文件内容为：

```rust
pub const CLAIM: &str = "R2_MODULE_A";
```

编译 A 并生成记录后，**只**将新模块中的 A 改成 B；`lib.rs`、`output.rs`、Cargo 文件及手工指纹清单不再变化。旧模块 A 二进制验证自己的记录仍退出 0。重新编译 B 并生成记录，两次输出的 claim 分别为 `R2_MODULE_A`、`R2_MODULE_B`，完整差异只有 `$["producer"]["claim"]`，全部 37 条 `fingerprints` 和对应 `context_bindings` 完全相同，均没有新模块路径。

模块 A/B 的 SHA-256 分别为 `{module['module_sha256_a']}`、`{module['module_sha256_b']}`；二进制 A/B 的 SHA 也不同，完整值在 [source/summary.json]({P}source/summary.json)。[接线补丁]({P}source/module-wiring-change.log)、[A 编译命令]({P}source/build-module-a.command.json)、[B 编译命令]({P}source/build-module-b.command.json)、[A 输出]({P}source/module-a-record.json)、[B 输出]({P}source/module-b-record.json)、[修改模块后旧验证器的输出]({P}source/verify-module-a-after-module-edit.stdout.log)组成可复核证据。

判定：**重现了**。新增模块注册时 `lib.rs` 的哈希当然会变；问题在于新模块自己的内容并未进入清单，后续仅改变该模块并重编译也不改变来源指纹。

**5. (b) A/A 比较方法与全部不稳定字段**

每组执行同一个已保存的二进制，固定 cwd、环境、输入、配置、预算、选项和 `--out` 路径，a 完成后立即执行 b。验证命令两次读取同一份固定记录；不分别读 a/b 生成的不同路径。对比退出码、stdout 原始字节、stderr 原始字节、所有直接/附带产物原始字节；再对 JSON 递归逐字段比较，保留类型和数组顺序。没有预先删除 elapsed、时间、ID、路径或哈希。普通 `run` 的 stdout 只是状态/路径摘要，因此也完整比较了文件内容；带记录的 `cycle` 同时比较证书和 `.record.json`。

实现为 [aa_probe.py]({P}aa_probe.py)、[aa_extra.py]({P}aa_extra.py)、[probe_common.py]({P}probe_common.py)。全部命令和 a/b 原始输出的直接索引在 [commands.md]({P}commands.md)；机器差异表为 [aa/results.json]({P}aa/results.json)，摘要为 [aa/summary.json]({P}aa/summary.json)。

| 命令/分支 | 不稳定字段的精确位置 | a → b（ns，原 JSON 类型是字符串） | 退出码 |
|---|---|---|---|
'''
for r in summary['unstable']:
 d=r['differences'][0];ex=next(x['exit_codes'] for x in aa if x['name']==r['name']);channel='stdout' if r['output']=='stdout' else '--out 所指 JSON 文件（stdout 不变）'
 text+=f"| `{r['name']}` | {channel} 的 `{d['path']}` | `{d['a']}` → `{d['b']}` | {ex[0]}/{ex[1]} |\n"
text+='''
这是本次所有差异，JSON Pointer 均为 `/elapsed_ns`。源码的两个赋值点是 `crates/kernel/src/main.rs:253–271`：开始执行前 `Instant::now()`，完成和 step-stop 分支均调用 `start.elapsed().as_nanos().to_string()`。`--ticks 0` 也走计时分支；输入装载失败发生在计时之前，没有这个字段。`--no-output --out` 把这个 JSON 写进指定文件，不会在 stdout 摘要中保留 elapsed。

未发现第二个不稳定字段。`run_id`、`result_id`、`producer.path`、来源 SHA、`out`、`verified_record`、仿真时间、事件 ID、Stop/basis、物料账、周期键和证据等级在对应 A/A 中均未变化。活动 kernel 源码的时钟/随机/HashMap/HashSet/PID/UUID 入口扫描也未找到另一条实际墙钟输出路径；`cycle.rs:428` 的 elapsed 是模型时间差，不是性能计时。

对 GPT Pro 第三节的判定为 **重现了**。若将说法扩大成“seed、check、普通 run 或所有子命令都存在不稳定字段”，本次证据不支持：这些路径的 A/A 完全一致。有限样例不能证明全部输入或系统故障下全局确定性，不能把“未观测到”升级为全域定理。

下表列出全部 44 组；“无”表示退出码、stdout/stderr 和该命令写出的全部产物都一致，不是只检查 elapsed。完整绝对路径命令由第一列链接及 commands.md 提供。

| 组名 / 命令元数据 | 参数摘要（路径仅显示文件名） | a/b 退出码 | 全部不稳定字段 |
|---|---|---|---|
'''+ '\n'.join(rows)+f'''

正常与拒收分支均实际执行。`cycle --max-ticks 20` 为 `inconclusive`；补充 50 tick 后实际 `completed_ticks=21`、`status=diagnostic_cycle`、周期 20，覆盖了真正找到周期后的 verify-cycle 和 checkpoint。诊断等级保持原输出，没有称为完整认证。`verify-batch` 两种目录集合均退出 0，stderr 中“已核 …”逐行一致；topology 的 Markdown stdout 也做原始字节比较。

精确豁免候选在 [observed-unstable-fields.json]({P}observed-unstable-fields.json)：只登记到达计时执行分支的 `run --no-output` 根 `/elapsed_ns`，按 `--out` 决定比较通道。性能字段保留原值并单独比较；其余已观测字段仍严格相等。这里没有修改原方案，也没有扩大为通用“时间字段过滤”。

**6. 与本任务相关的额外发现**

**已重现：共享 target 中复用同一 profile，成功构建未必得到新目录来源的产物。** 在 `shutil.copy2` 保留源码时间戳的 `/tmp` 副本上，用 `--manifest-path` 指向副本、继续使用 `r2audit` profile，Cargo 1.98.1 的 `-vv` 输出将副本 kernel/topology 判为 `Fresh`，构建退出 0、耗时显示 0.00s；返回的 kernel SHA 仍为基线 SHA，`producer.path` 仍指向原工作区，而不是指定 `/tmp` 副本。

复核命令及输出在 [cache-origin/build.command.json]({P}cache-origin/build.command.json)、[build.stderr.log]({P}cache-origin/build.stderr.log)、[run.command.json]({P}cache-origin/run.command.json)、[summary.json]({P}cache-origin/summary.json)。预期路径 `{cache['expected_producer_path']}`，实际 `{cache['actual_producer_path']}`。探针为 [cache_origin_probe.py]({P}cache_origin_probe.py)。这记录的是本机、本 Cargo 版本、保留时间戳复制及同 profile 的实测结果；未审 Cargo 内部实现，根因和跨版本普遍性不作断言。

正式来源对照已用共享 target 内独立 profile 排除该混淆，并断言 `producer.path` 符合副本路径。最初被断言挡下的尝试单独保存在 `{P}source-initial-cache-reuse/`，不混入成功来源演示。只检查 `cargo build` 的退出码不足以证明双版本构建身份，仍须核二进制哈希及实际嵌入路径。

**代码上成立、未做篡改实验：批量验证还依赖未纳入上述实现清单的 Python/Node 代码。** `main.rs:19–28` 从编译目录运行 `tests/verify_all.py`，后者 `:7–16` 导入 `audit_task7` 并加载绝对路径 AJV；这些文件没有列在 `output::fingerprints()` 的 checker 清单中。本轮正常 A/A 包含 verify-batch，输出稳定；没有修改这些依赖、也没有据此声称已绕过验证。这是来源覆盖边界，不是新的计时不稳定字段。

**7. 写入保护、复算入口与结论边界**

保护摘要 [protection-summary.json]({P}protection-summary.json) 显示：生产源码、测试、数据/样例/黄金/历史证据、规格、三个重锁维护目录、Cargo 清单、原方案、意见原文及仓库根正式文件等共 {protect['protected_existing_files']} 个受保护既存文件，字节哈希未变，无删除、无新增。更宽的全仓清单从 {protect['before_files']} 项变为 {protect['after_files']} 项：另有 251 个新增和 R1 的两个 build 日志更新，位于其他工作输出路径；保留 [完整差异]({P}protected-diff.json)，不将整个共享工作区称为“零变化”，也未回滚这些外部变化。清单排除 target、Git/索引/依赖缓存及本任务输出。

本任务没有 git 写操作，没有修改生产源码、测试、黄金、历史证据、正式文件、样例或方案。全部有意源码改动只在 `/tmp` 副本，任务产物目录只含脚本、日志、JSON、Markdown，没有源码树快照或编译产物。

从工作区根目录复算：

```sh
python -B 内核维护/2026-09-22d/R2-来源与计时/build_baseline.py
python -B 内核维护/2026-09-22d/R2-来源与计时/aa_probe.py
python -B 内核维护/2026-09-22d/R2-来源与计时/aa_extra.py
python -B 内核维护/2026-09-22d/R2-来源与计时/source_probe.py
python -B 内核维护/2026-09-22d/R2-来源与计时/cache_origin_probe.py
```

这些脚本会写本任务同名产物；若需要保留本次原始证据，应先给新执行设置不同的输出位置。`source_probe.py` 每次建立新 `/tmp` 副本与独立 profile；已保存的来源演示记录针对各阶段当时的磁盘字节，后续有意修改副本后不能要求旧记录仍通过现时来源核验。

第二、三节的核心主张都已复现。当前指纹能够说明枚举文件运行时的内容，不能单独绑定执行二进制；A/A 的测量豁免须精确到输出通道和 `/elapsed_ns`，不能过滤事件、仿真时间、路径或来源字段来掩盖其他差异。
'''
(OUT.parent/'R2-来源与计时.md').write_text(text)
print('report written',len(text),'characters; cases',len(aa))
