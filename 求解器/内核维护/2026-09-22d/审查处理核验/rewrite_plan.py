"""Rewrite only the authorized plan; review evidence stays read-only."""
import hashlib
from pathlib import Path

P = Path('/home/zhuran24/zmd-research-fresh/求解器/内核维护/代码体检方案.md')
s = P.read_text()
assert hashlib.sha256(P.read_bytes()).hexdigest() == '24654bd905fef808ca90e51e08ed02d59858f92a4706a6eed5b7f7952896cb9e'

def replace(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)

replace('历史证据恢复列在第 0 批。本文各批验收均为执行要求，已有实测结果注明其核实报告。', '第 0 批先保存保护清单、恢复可恢复历史并独立提交，再改造测试隔离。本文各批验收均为待执行要求；方案审查完成不代表恢复、改码或回归已完成。已有实测结果注明核实报告及适用时点。')
replace('只有第 0 批登记的来源映射和测量字段采用专门比较。', '只有按 §3.5 程序登记的来源映射和测量字段采用专门比较；公开 API 及原始 JSON 字节契约冻结。')
replace('测试输出隔离、周期键入口一致性', '周期键入口一致性')
replace('一个实施单元只采用一条线的验收契约。', '第 0 批是基础设施与历史恢复批：只改变测试输出管理和已登记的恢复目标，不改变生产实现、公开 API 或运行时验证脚本。其专用验收见 §3.5。生产维护的一个实施单元只采用一条线的验收契约。')
replace('结构差分固定同一输入、配置、起点和预算，逐层比较：', '结构线冻结所有公开可达 `pub` 项的存在、签名、可见性及 serde 形状；仓库内无调用者不构成删除公共 API 的依据。公共项删除、可见性收窄和对外类型替换进入加固线，附调用方迁移表。§4.3 来源协议验收前，不新增、删除、改名非测试编译源文件，函数抽取限于原文件内。\n\n结构差分固定同一输入、配置、三份正式源、规格语义文件、正式目录及编译期嵌入副本、Python/Node/AJV 等验证依赖、起点和预算；每批使用 §3.4 的冻结来源树。逐层比较：')
replace('full/delta 原格式契约及解码后的完整记录、检查点、完整前缀、恢复后的后续轨迹', 'full/delta 落盘字节契约及解码后的完整记录、检查点、完整前缀、恢复后的后续轨迹')
replace('隔离输出、恢复历史、冻结来源与产物、A/A、字段白名单', '保护清单、历史恢复与独立提交、隔离输出、冻结来源与产物、A/A、字段白名单')
replace('连续两轮安全回归、保护清单通过、恢复逐项对账、A/A 通过', '恢复逐项对账、连续两轮安全回归、保护清单与编译闭包通过、同路径同 profile 的生产二进制字节相同、A/A 通过')
replace('R1/R2 反例回归通过，合法轨迹等价，迁移调用方编译通过', 'R1/R2 反例及 R5 停止态（§4.2）回归通过，合法轨迹等价，迁移调用方编译通过；跨文件结构抽取前通过 §4.3')

start = s.index('## 2. 执行环境')
end = s.index('## 4. 第 1 批')
s = s[:start] + r'''## 2. 执行环境、输出目录与共用入口

全部编译使用共享 `CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target`。运行目录只保存脚本、探针源码、日志、JSON、Markdown；源码树实拷只放 `/tmp`，编译产物只放共享 target。测试进程串行；Cargo jobs=2、codegen-units=1，测试及计算池单线程，总线程预算 ≤6。保存 CPU affinity、实际进程/线程配置；构建工具若超预算须进一步限并发，CPU affinity 不能替代线程数核查。

以下 Bash 块均保存为脚本，以 `bash -euo pipefail /绝对路径/脚本.sh /绝对路径/env.sh` 执行，适用于从 fish 或新的工具 shell 启动。初始化脚本不接收 env.sh；后续块首行加载同一份环境文件，不依赖前一次 shell 的变量。待实现的运行器接口在正文明确标明，不能在工具尚未实现时当作可执行命令。

初始化脚本（保存为 `/tmp/kernel-health-init.sh`，执行 `bash -euo pipefail /tmp/kernel-health-init.sh`）：

```bash
set -euo pipefail
cd /home/zhuran24/zmd-research-fresh/求解器
export HEALTH_REPO="$PWD" HEALTH_SRC="$PWD"
export CARGO_TARGET_DIR="$PWD/target"
export CARGO_BUILD_JOBS=2 CARGO_PROFILE_DEV_CODEGEN_UNITS=1
export CARGO_PROFILE_TEST_CODEGEN_UNITS=1 CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
export RUST_TEST_THREADS=1 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
export HEALTH_RUN
HEALTH_RUN=$(mktemp -d "$PWD/内核维护/体检-$(date +%Y%m%d-%H%M%S)-XXXXXX")
export KERNEL_TEST_EVIDENCE_DIR="$HEALTH_RUN/cargo-test-evidence"
mkdir "$KERNEL_TEST_EVIDENCE_DIR"
python -B - <<'PY'
import os, shlex
from pathlib import Path
keys = ['HEALTH_REPO','HEALTH_SRC','HEALTH_RUN','CARGO_TARGET_DIR',
        'CARGO_BUILD_JOBS','CARGO_PROFILE_DEV_CODEGEN_UNITS',
        'CARGO_PROFILE_TEST_CODEGEN_UNITS','CARGO_PROFILE_RELEASE_CODEGEN_UNITS',
        'RUST_TEST_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS',
        'OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE','GIT_OPTIONAL_LOCKS',
        'KERNEL_TEST_EVIDENCE_DIR']
path = Path(os.environ['HEALTH_RUN']) / 'env.sh'
path.write_text(''.join('export '+k+'='+shlex.quote(os.environ[k])+'\n' for k in keys))
print(path)
PY
rustc -Vv > "$HEALTH_RUN/rustc.log"
cargo -V > "$HEALTH_RUN/cargo.log"
cargo metadata --locked --offline --no-deps --format-version 1 > "$HEALTH_RUN/cargo-metadata.json"
git -C .. rev-parse HEAD > "$HEALTH_RUN/head.log"
git -C .. -c core.quotePath=false status --short > "$HEALTH_RUN/worktree.log"
```

工具链、Python/Node/AJV、GNU time、`sha256sum` 的解析后路径、版本与文件哈希进入环境清单。离线依赖缺失先单独补齐并登记，再执行固定命令。

第 0 批拟新增两个工具，命令契约如下：

| 拟新增文件 | 职责与输出 |
|---|---|
| `数据/工具/kernel_file_guard.py` | `snapshot --root .. --out <json>` 记录文件、目录（含空目录）、链接、权限、大小、SHA-256 和链接目标；`verify --before <json> --out <json>` 核新增、删除、改写。覆盖跟踪、未跟踪及忽略项。 |
| `数据/工具/kernel_regression.py` | `tests`、`aa`、`capture`、`compare` 按 cases/binaries/fields 清单执行；保存 argv、cwd、环境、退出码、stdout/stderr、产物及首个差异；核源码闭包、构建来源和隔离验收凭据。 |

恢复前的保护清单不依赖这两个工具实现，可使用经只读审查的一次性盘点脚本。从仓库根盘点三份正式源、规格、源码、样例、fixture、黄金、历史证据和已有维护目录；只排除明确登记的 target、Git 内部、工具缓存和本次输出根。目录及忽略文件同样受保护。源码编辑、历史恢复和测试运行各自建立检查点；测试允许写入仅为本次新建空输出目录及专属 target 临时目录。其他会话的变化单列前后哈希及归属依据，不自动回退。

测试产物根固定为 `$HEALTH_RUN/cargo-test-evidence`，其名字匹配已有 Git ignore 规则；仍须实际用 `git check-ignore` 核验，不对该目录使用强制添加。大型 A/A、A/B 和性能原始产物放共享 target 的专属目录，运行目录保存索引、大小、哈希及摘要，保留原字节供复核。可提交范围见 §9.3。

代码问题先查询 CodeGraph，`projectPath=/home/zhuran24/zmd-research-fresh/求解器`；按活动 Cargo 模块图筛选，缺失部分才补读。每批保留实际编译及 Clippy 诊断，新告警逐项处理。

## 3. 第 0 批：恢复历史、隔离测试与冻结基线

### 3.1 保存保护清单后，首先恢复可恢复历史

本步骤先于测试隔离改码。开始即保存保护清单、当前工作区差异、R3 恢复清单及源材料的 SHA-256；暂停会写恢复目标的任务，按 §8.0 限制回归。恢复只读取已核实的 Git blob/匹配副本，不运行内核或测试。恢复完成后独立提交，再进入 §3.2。恢复提交只包含逐项登记的恢复路径、来源说明、缺失标记和 journal，不夹带活动重锁或源码改动。

依据为 [restore_manifest.json](2026-09-22d/R3-测试写历史/restore_manifest.json) 的 `files`。当日 `7da52a7` 没有 evidence 变更；`a7539f5` 改写 159 个旧文件并新增 7 个，`220f7b6` 再改其中 106 个旧文件及 5 个新增文件。审查基点 `5b4b3e3` 的 HEAD 仍保留受损字节，不能用 HEAD 或 `220f7b6^` 作为统一恢复点；以后须记录恢复提交的完整 ID。

| 集合 | 处置和验收 |
|---|---|
| 159 个入库旧文件 | 从逐项 `source_commit=f8f6129` 恢复完整 blob；`equivalent_commit=7da52a7` 字节相同，按 `expected_sha256` 验收。目录计数为 revision-r2 2、revision-r4/cli 23、round6/cli 12、round6/regressions/revision-r3 79、round6/revision-r5/cli 43。 |
| 7 个当天新增文件 | 保留现场字节及来源；提取 a7539f5、220f7b6 的两个版本，保持完整相对路径。实施恢复时将历史目录里的新增路径移出，归到对应重锁运行档案；不冒充旧轮次证据。 |
| 14 个未跟踪漂移 | `pre_day_hash_drift.json` 中 `tracked=false` 的目标以 `before_sha256` 为准。1 项有同哈希副本；其余 13 项状态为“原字节缺失”，不能用重生成结果冒充恢复。 |
| 首次已恢复的 3 个 round5 文件 | 对照 `2026-09-22/early-test-output-restoration.json` 核原哈希；它们直接位于 round5 下，与新增 round5/round5_cli 不同。 |

恢复执行器须实现以下完整事务步骤，并把每一步及异常写进 `restore-journal.json`：

1. 用 `git ls-files --error-unmatch -- <path>` 确认 159 项仍被跟踪；用 `git check-ignore -- <path>` 及 ls-files 确认那 1 项的忽略/未跟踪身份。根路径、路径穿越、符号链接、缺失目标、源 blob 哈希不符都停止；这些错误不能当作“意外当前哈希”放行。
2. 核全部源 blob、目标哈希及等价提交。已知未跟踪恢复目标为 `crates/kernel/evidence/round6/revision-r5/cli/分流器三路轮询-absolute.json`，来源是 `数据/样例/分流器三路轮询-运行记录-v3-kernel.json`；实际字节必须匹配 `before_sha256`。
3. 读取全部目标的当前字节，当前哈希与旧审计值不同只记 `unexpected_current`，不因此阻止有确定来源的恢复。先将所有现场字节按原相对路径备份到本次 `cargo-test-evidence/history-before-restoration/`；包括 13 个缺失原件路径及 7 个新增路径。校验备份哈希后才能开始覆盖。
4. 在保持恢复目标单写者的前提下，每次写前重读并断言 `p.read_bytes() == now`；发现并发变动立即停止。用目标同目录的唯一临时文件写入已核源字节，保留权限、flush/fsync，重新核当前字节后 `os.replace` 原子替换，核替换后完整哈希。journal 也采用临时文件加替换；记录 pending/completed/error，使中断后可按目标哈希核销，不宣称整批原子完成。
5. 13 项在所查范围内未找到原字节。opus 已按原大小查 `/home`、`/tmp`、`/var/tmp`、`/mnt`、`/media`、`/opt`、`/srv`（`-xdev` 的范围限制照录），并查四个本地 Git 对象库：本仓库、`/home/zhuran24/zmd-project-cc`、`/home/zhuran24/.claude/skills`、`/home/zhuran24/文档/ChatGPT/New project`。结果见其 [查找清单](2026-09-22d/审查-opus/unresolved_targets.json)、[对象库结果](2026-09-22d/审查-opus/git_object_search.json)；这是限定时点/范围的查找结论。旧记录 36 个来源指纹中有 20 个不等于 f8f6129 同路径 blob，不能把该提交重跑当作原字节恢复依据。
6. 实施恢复时由 owner 选择 13 项现存替代字节原地保留或移入本次归档；两种方式均在相关原目录新增 `原字节缺失.json`，逐路径写原 SHA-256、原字节数、现存 SHA-256、处置位置和查找依据。原大小取 `2026-09-22/before.json`，与 opus 查找清单交叉核对。已知同哈希来源的 1 项是否强制入库单独决定，不阻塞其按哈希恢复。
7. 恢复与标记验收通过后，只暂存清单列出的路径，核暂存差异及全部大文件，再单独提交，提交说明引用 journal。现有 post-commit 会启动推送，实施者须按当前会话授权范围安排提交。记录提交 ID 和提交后复核结果，之后才开始隔离改码。

七项版本提取脚本只向新输出目录写入（保存为运行目录的 `extract-relock-versions.sh`，用 §2 的 Bash 调用方式）：

```bash
set -euo pipefail
source "${1:?传入本次 env.sh 的绝对路径}"
for c in a7539f5 220f7b6; do
  for rel in round5/round5_cli/{invalid-cycle-input,invalid-cycle-result,relocated-seed,resource-statistics}.json \
             round6/revision-r5/cli/bounded-reference-batch-unsupported.log \
             round6/revision-r5/cli/bounded-reference-package/{分流器三路轮询,混做粉碎机两下游}-reference.json; do
    dest="$HEALTH_RUN/cargo-test-evidence/relock-history/$c/$rel"
    test ! -e "$dest"
    mkdir -p "$(dirname "$dest")"
    git -C "$HEALTH_REPO/.." show "$c:求解器/crates/kernel/evidence/$rel" > "$dest"
    sha256sum "$dest"
  done
done
```

a7539f5 版归 `内核维护/2026-09-22b/cargo-test-outputs/<evidence 相对路径>`，220f7b6 版归 `内核维护/2026-09-22c/cargo-test-outputs/<evidence 相对路径>`；provenance 记录原路径、提交、哈希、大小。当前现场若又有第三种字节则留在本次运行目录，不能误标为 c 版。历史原路径的移出和两个版本的提取是不同操作，一次 `git mv` 不能取得两个历史版本。这些小型历史归档按 §9.3 逐文件审查入库。

**恢复验收：**159+1 个可恢复目标完整哈希匹配，7 个新增项脱离旧轮次目录且两个提交版本可定位，原三份 round5 恢复哈希仍相同，13 项缺失有原目录标记和完整清单。`history_recovery=partial` 可与 `regression_ready=true` 并存，后者还要求新基线和活动测试不依赖缺失原字节。旧件原字节缺失不因测试通过而核销。

### 3.2 统一测试输出并验收副本来源

恢复提交完成后改造七个活动 Cargo CLI 入口：

| `crates/kernel/tests/` 入口 | 原写出位置 |
|---|---|
| `round5_cli.rs` | `evidence/round5/round5_cli/` |
| `revision_cli.rs` → `revision_cli.py` | `evidence/revision-r2/prior-regression-results.json` 及过程目录 |
| `revision_r2_cli.rs` → `revision_r2_cli.py` | `evidence/revision-r2/regression-results.json` 及过程目录 |
| `revision_r3_cli.rs` → `revision_r3_cli.py` | `evidence/round6/regressions/revision-r3/` |
| `revision_r4_cli.rs` → `revision_r4_cli.py` | `evidence/revision-r4/cli/` |
| `revision_r5_cli.rs` → `revision_r5_cli.py` | `evidence/round6/revision-r5/cli/` 及材料包 |
| `round6_cli.rs` → `round6_cli.py` | `evidence/round6/cli/` |

路径台账见 [R3 §3](2026-09-22d/R3-测试写历史.md)。六个 Python 入口目前忽略 `KERNEL_TEST_EVIDENCE_DIR`；只设置变量不能隔离它们。

新建 `crates/kernel/tests/support/mod.rs` 与 `crates/kernel/tests/evidence_paths.py`，统一为每测试、每执行实例分配新空目录。输出根白名单只有本次 `HEALTH_RUN` 下的新空目录，以及共享 target 下本次专属测试临时根；其余拒绝。解析绝对路径、真实路径和所有祖先链接，不能通过符号链接逃回历史目录。Rust 显式把实例目录传给 Python；缺省只允许共享 target 的唯一临时目录，失败保留并报告。日志、变异输入、附带 record、材料包及子进程全部遵守同一边界。

Python 主体放显式 `main`，import 无写入；只读输入与输出使用不同变量。`revision_r3_cli.py` 的 `gate-expired-after-closure-input.json`、`tiny-expired-cycle.json` 在运行主体前必须存在并匹配登记哈希；缺失硬失败，禁止 `if exists` 静默减覆盖。若为归档而迁移，按原字节复制到只读 fixtures 并保存来源映射、两组负例名和计数。

按 [活动写点清单](2026-09-22d/R3-测试写历史/active-source-writers.md)核全部子进程。`benchmark_round6.py --out-dir` 仍写样例，进入 suite 前迁移该副作用；黄金生成器只使用已核只读函数。`test_formal_catalog.py` 的临时正式源副本放 `/tmp`，编译仍用共享 target。第 0 批禁止修改生产 `src`、`tests/verify_all.py`、`tests/audit_task7.py` 及其实际导入依赖；确需修改运行时验证逻辑，另立行为批并重新建立 A。两份已跟踪 pyc 单列缓存清理，不混进语义变更。

在 `/tmp` 实拷中先验收，副本不得有符号链接，也不得缺少被忽略但活动测试需要的只读资源；复制资源逐项登记哈希。先构建测试但不运行（脚本第二参数是副本求解器绝对路径）：

```bash
set -euo pipefail
source "${1:?传入本次 env.sh 的绝对路径}"
export HEALTH_COPY="${2:?传入 /tmp 副本求解器根}"
cd "$HEALTH_COPY"
case "$PWD/" in /tmp/*/) ;; *) exit 2 ;; esac
export HEALTH_PROFILE="healthtest$(date +%s)$$"
cargo test --locked --offline --workspace --tests --no-run -j 2 \
  --profile "$HEALTH_PROFILE" --config "profile.$HEALTH_PROFILE.inherits=\"dev\"" \
  --config "profile.$HEALTH_PROFILE.codegen-units=1" --message-format=json \
  > "$HEALTH_RUN/test-build.jsonl.log" 2> "$HEALTH_RUN/test-build.stderr.log"
python -B - <<'PY'
import json, os
from pathlib import Path
run, root = Path(os.environ['HEALTH_RUN']), Path(os.environ['HEALTH_COPY']).resolve()
rows = [json.loads(s) for s in (run/'test-build.jsonl.log').read_text().splitlines() if s.startswith('{')]
artifacts = [r for r in rows if r.get('reason') == 'compiler-artifact'
             and r.get('executable') and r.get('profile', {}).get('test')]
assert artifacts, 'no test harnesses'
for r in artifacts:
    assert r['fresh'] is False, r
    assert Path(r['manifest_path']).resolve().is_relative_to(root), r
    assert Path(r['target']['src_path']).resolve().is_relative_to(root), r
(run/'test-harnesses.json').write_text(json.dumps(artifacts, ensure_ascii=False, indent=2)+'\n')
PY
```

运行器先核 `test-harnesses.json` 与 metadata 目标集合完全对应、内嵌路径/dep-info/二进制哈希均来自副本，另核被调用 kernel bin 的构建来源；随后直接执行清单中的 harness 绝对路径，先 `--list` 留档，再 `--test-threads=1`，不让第二次 Cargo 调用重新选择产物。实际 Python `__file__`、ROOT 及读取路径须在副本或已登记外部依赖内。首次构建任何 harness 为 Fresh、缺失或指回原仓库都拒绝运行。

**验收：**显式根、无配置、两轮重复、两个实例并发（线程总数 ≤6）、不同 cwd、中文/空格路径、子进程失败及非法根拒收；每次核包括空目录和忽略项的保护清单。`isolation-accepted.json` 记录通过的用例、源/脚本/运行器/依赖哈希、profile、所有 harness 与 bin 来源、输出落点及保护结果。正式 CLI suite 执行前重核这些绑定，文件存在本身不足以验收。路径或实现变化使凭据失效，须重新验收。原仓库入口只在相应源码版本的隔离验收完成后运行。

### 3.3 分开安全命令与受守卫的 CLI suite

下列安全脚本只包含经写点核查的 build/check/Clippy、库测试、reference、topology validation 和 doc。从冻结根或登记的稳定工作区执行；源码/依赖变化后重新核写入边界。运行器逐命令保存退出码和输出，失败即停；预期非零的 CLI 反例由运行器显式核预期码。

```bash
set -euo pipefail
source "${1:?传入本次 env.sh 的绝对路径}"
cd "$HEALTH_SRC"
cargo build --locked --offline --workspace -j 2
cargo check --locked --offline --workspace --all-targets -j 2
cargo clippy --locked --offline --workspace --all-targets -j 2 --message-format=json
cargo test --locked --offline -p kernel --lib -j 2 -- --test-threads=1
cargo test --locked --offline -p topology --lib -j 2 -- --test-threads=1
cargo test --locked --offline -p kernel --test reference -j 2 -- --test-threads=1
cargo test --locked --offline -p topology --test validation -j 2 -- --test-threads=1
cargo test --locked --offline -p kernel --doc -j 2 -- --test-threads=1
cargo test --locked --offline -p topology --doc -j 2 -- --test-threads=1
```

七个 CLI 入口使用另一个脚本；其中 `check-isolation` 是第 0 批运行器须实现的凭据核验接口：

```bash
set -euo pipefail
source "${1:?传入本次 env.sh 的绝对路径}"
cd "$HEALTH_SRC"
test -s "$HEALTH_RUN/isolation-accepted.json" || exit 2
python -B 数据/工具/kernel_regression.py check-isolation \
  --acceptance "$HEALTH_RUN/isolation-accepted.json" --source-root "$HEALTH_SRC"
for health_test in revision_cli revision_r2_cli revision_r3_cli revision_r4_cli revision_r5_cli round5_cli round6_cli; do
  cargo test --locked --offline -p kernel --test "$health_test" -j 2 -- --test-threads=1
done
```

在共享 target 的副本环境中，安全脚本也须使用本次唯一 profile：运行器将 §3.2 构建参数应用到各 Cargo 命令并验证来源；测试可直接运行已验收 harness。不能在副本中退回共享默认 profile。两个脚本互不串接，禁止以全工作区测试命令替代。

按 metadata 枚举所有 harness，保存 `--list` 和本次实际通过数。历史计数 kernel lib 100、topology lib 1、reference 3、topology validation 30、CLI 7，合计 141；134 是去掉七个 CLI 的历史口径。两个 bin harness 的零测试及 doc 也要按本次列举记录，新增目标先核副作用再纳入。

`reference.rs` 的三个差分测试覆盖粉碎机 4 刻、分流器 12 刻和现场 Python 重算；手工黄金按原字节保护。来源篡改与负例属于 §3.3 的 suite 整体，包括库测试及 CLI，不能归到 reference 的三项上。

### 3.4 必须冻结构建与运行时来源

每批从明确的已提交 commit，以 `git archive` 读取 Git 对象，在 `/tmp` 建最小完整冻结树，包含项目根三份正式源及求解器资源。只按清单抽取必需路径，不归档整棵历史仓库；所需未跟踪 fixture 或本批选定的未提交正式源按登记哈希实拷覆盖，A/B 使用同一覆盖集。提交 ID 不是工作区内容的替代标识。采用 archive 不创建 worktree，不改原仓库 Git 元数据；副本不含符号链接或编译产物。

冻结范围必须同时包括：输入和配置、三份正式源、全部消费的规格/轴表/schema/证明来源、正式静态目录及 include 嵌入资源、样例/fixture/黄金、Cargo.toml/lock、features/cfg/构建参数、活动 kernel/topology 编译闭包、`tests/verify_all.py`、`tests/audit_task7.py` 及其导入的样例模块、Python/Node/AJV 实际依赖闭包、外部 `sha256sum`。AJV 使用绝对路径，至少核入口、依赖文件及 package 版本；外部可执行文件保存解析后的路径/版本/哈希，在每次执行前后核其未变。仅保存版本号不等于冻结。

可以在同一 `/tmp` 物理根顺序完成 A 和 B：先放 A 源码，构建、运行整条 A 链并封存其输出和验证回执；之后仅替换清单登记的 crates 源码为 B，再构建并完成 B 链。非源码资源保持相同，测试基础设施改动另列。A 源码被替换后禁止再次运行 A；若需重跑先按完整清单还原 A 上下文并核哈希。持续交替运行则使用两个独立冻结根，各自构建、绑定来源并登记路径映射，不能让旧 A 在 B 源码根“签来源”。两种方式均使用唯一 profile 和同一共享 target。

构建脚本接受 env.sh 和本阶段冻结求解器路径，生成并持久化 `HEALTH_BIN`/`HEALTH_TOPOLOGY_BIN`（每阶段保留 env.sh 副本和构建日志，再开始下一阶段）：

```bash
set -euo pipefail
source "${1:?传入本次 env.sh 的绝对路径}"
export HEALTH_SRC="${2:?传入本阶段 /tmp 冻结求解器根}"
cd "$HEALTH_SRC"
case "$PWD/" in /tmp/*/) ;; *) exit 2 ;; esac
export HEALTH_PROFILE="health$(date +%s)$$"
cargo build --locked --offline --workspace --bins -j 2 --profile "$HEALTH_PROFILE" \
  --config "profile.$HEALTH_PROFILE.inherits=\"dev\"" \
  --config "profile.$HEALTH_PROFILE.codegen-units=1" --message-format=json \
  > "$HEALTH_RUN/build-artifacts.jsonl.log" 2> "$HEALTH_RUN/build.stderr.log"
python -B - <<'PY'
import hashlib, json, os, shlex
from pathlib import Path
run, root = Path(os.environ['HEALTH_RUN']), Path(os.environ['HEALTH_SRC']).resolve()
rows = [json.loads(s) for s in (run/'build-artifacts.jsonl.log').read_text().splitlines() if s.startswith('{')]
bound = {}
for name, key in [('kernel','HEALTH_BIN'), ('topology','HEALTH_TOPOLOGY_BIN')]:
    hits = [r for r in rows if r.get('reason') == 'compiler-artifact'
            and r['target']['name'] == name and 'bin' in r['target']['kind']
            and not r['profile']['test']]
    assert len(hits) == 1, hits
    r = hits[0]
    assert r['fresh'] is False and r['executable'], r
    assert Path(r['manifest_path']).resolve().is_relative_to(root), r
    path = Path(r['executable']).resolve()
    bound[key] = str(path)
    (run/(name+'-bin.sha256')).write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path)+'\n')
bound.update(HEALTH_SRC=str(root), HEALTH_PROFILE=os.environ['HEALTH_PROFILE'])
with (run/'env.sh').open('a') as f:
    for k,v in bound.items(): f.write('export '+k+'='+shlex.quote(v)+'\n')
PY
source "$HEALTH_RUN/env.sh"
sha256sum --check "$HEALTH_RUN/kernel-bin.sha256" "$HEALTH_RUN/topology-bin.sha256"
```

每次执行前后核二进制和冻结清单，并检查实际 `producer.path`/嵌入源码根。R2 已观察到同 profile 的 copy2 副本被 Cargo 判为 Fresh 却沿用原目录产物；只核退出码或可执行文件名不能验来源。

第 0 批运行器还必须做**编译闭包核对**：从本次 compiler-artifact 的精确产物标识找到对应 `.d`，解析 Makefile 转义及续行，不通配选一个旧文件。取非 test 构建的 kernel lib 和 bin 的 Rust 源/嵌入资源闭包，分别与记录 checker 中 Rust 路径、catalog/profile 的对应嵌入路径比较；Cargo.toml/lock、语义来源、运行时验证依赖单列核验。kernel lib 的 `.d` 不含 `main.rs`，不能把仅 lib 的集合与所有 checker 条目直接判相等。topology 编译闭包独立绑定到外层清单；按 cfg/编译产物判别测试专用源，不能靠文件名前缀过滤。重复项、漏项和无解释的多项均失败。在 `/tmp` 注入新增编译模块而不登记的负例必须被拒收。正式 build ID 协议见 §4.3；该子批通过前，结构抽取仍限原文件内。

批次中途发生正式源重锁时，既有冻结树不随工作区自动更新。若本批继续评价旧上下文，结论明确绑定旧来源；若须评价新上下文，则用旧内核源码加新正式源/目录/输入/规格构建 A′，先重做 A′/A′，再以同一新上下文构建 B′比较。旧 A 输出只存档，不与新 B 混用；核重锁自身的接受域/语义变化，不能用来源映射掩盖规则改变。

### 3.5 A/A、字节等价及引用闭包

每例 A/A 和 A/B 都在同一固定物理输出根 `$CARGO_TARGET_DIR/health-capture/<run_id>/<case_id>/` 顺序捕获。运行器创建独占标记，只允许清理本次登记的该 case 目录；每次捕获开始前清空，结束后将整条链所有原始产物、stdout/stderr 和退出码复制到专属封存目录并核哈希。封存目录放共享 target 或本次 cargo-test-evidence，索引留运行目录；不因封存改变产物内路径。验证须在捕获根仍完整且对应源码上下文未换版时完成。A/B 不并行写同一根。

从 [R2 的 44 组命令](2026-09-22d/R2-来源与计时/commands.md)提取分支模板生成 `cases.json`；R2 目录只读，其过期 batch、bad-input、contract、checkpoint 不作为新输入直接复用。每个 prerequisite 登记为本次链中的生成步骤：记录/周期/种子由该链同一二进制生成，变异负例及 topology contract 由本次生成物和冻结资源按显式变换生成。每轮 A/A 都重走前置步骤，缺失前置产物硬失败。verify-* 只验证本链对应版本的刚生成产物；跨版本拒收实验单列预期结果，不混入等价测试。

`cases.json` 逐例列 ID、角色、argv、cwd、环境、输入哈希、前置步骤、预期退出码和所有输出；`binaries.json` 绑定实际产物、源码根、构建清单与哈希。覆盖 seed/check/request、full/delta、缓存开关、零 tick、停止/装载失败、周期命中/耗尽、verify-record/cycle、两类 checkpoint、verify-batch、topology 和 CLI 参数错误。

第 0 批运行器须实现 `aa --cases ... --binaries ... --fields ... --out ...`、`capture --cases ... --binaries ... --out ...`、`compare --baseline ... --candidate ... --fields ... --out ...`；baseline 指本批同冻结上下文的 A capture，加固批另接 `--changes <行为变更契约>`。运行器先用缺字段、错类型、数组交换、JSON 重排/改缩进、错来源映射、坏引用哈希、缺被引用文件及未登记差异检验拒收能力。

**结构线逐字节验收落盘 JSON 和文本。** 保留所有原始字节；在比较副本中只把已登记的 B 字段替换为 A 的原始 token 字节，然后与 A 逐字节比较。替换须由保留位置的 JSON 解析器定位到确切 Pointer，不能 parse 后整份重新序列化，不能全局字符串替换；重复键或定位不唯一拒收。键序、空白、转义、换行和数字拼写的未登记变化均失败。解析层比较只用于定位差异，解码 full/delta 相等不能替代文件字节相等。这一要求同样适用于第 4 批等价优化。

初始测量白名单只来自 R2 的 44 组 A/A：

| 用例 | 通道 | Pointer | 字段契约 |
|---|---|---|---|
| `run-no-output` | stdout JSON | `/elapsed_ns` | 十进制非负整数字符串 |
| `run-no-output-no-cache` | stdout JSON | `/elapsed_ns` | 同上 |
| `run-no-output-zero` | stdout JSON | `/elapsed_ns` | 同上 |
| `run-no-output-stop` | stdout JSON | `/elapsed_ns` | 同上，Stop 其他字段全保留 |
| `run-no-output-out` | `--out` JSON | `/elapsed_ns` | 同上，stdout 仍逐字节比较 |

只在实际到达计时分支时应用；装载失败没有该字段，不补造字段。原计时值保留并另入性能表。

`comparison-fields.json` 每批按 `case_id + artifact + JSON Pointer` 登记映射，包含 A/B 原值、依据及验证器。来源路径/哈希先分别核闭包；按 role 和规范路径展开到具体索引，核数组长度、顺序及条目身份。`producer.path` 和因两个冻结根产生的路径差异逐项登记；固定捕获根使 out 路径无需因版本改名。新增/删除来源字段及数组结构改变进入 §4.3 协议变更契约。

**引用闭包验收：**逐条解析 `run_record_ref`、`replay_input_ref`、`normalization.definition`、`mapping_proof`、`proof_sources` 等引用。在各自原上下文先核实际目标原字节 SHA-256，不能先归一化再通过原始验证。对叶子来源先做已登记来源映射；对本次生成产物按依赖顺序证明目标在登记替换后逐字节等于 A，才允许把引用方的 B 哈希映射为 A 哈希。记录“引用方 Pointer → 目标路径/原哈希 → 字节等价证据 → 映射依据”。缺目标、坏原哈希、未核差异或无法闭合的循环引用均拒收；不能整类忽略名为 sha256 的字段。修改只发生于比较副本，原证据和同版本验证回执不变。

状态、事件 ID、模型时间、basis、Stop、账、周期键及证据义务严格相等。出现新差异先定位，确有来源/测量依据才登记并重跑 A/A；行为变化进入加固线。

**第 0 批总验收：**恢复先行并独立提交、隔离入口连续两轮通过、完整文件/目录保护通过、A/A 满足字段和引用闭包契约、编译闭包检查能拒收新增遗漏模块。另在同一路径、同 profile、同工具链和环境下比较测试隔离改码前后的 kernel/topology 生产二进制，须逐字节相同；运行时 Python/AJV/sha256sum 依赖也须相同。正式源并发变化则使此对照失效，重建前后上下文再验，不能将差异过滤。A 的源码—二进制—输入—原始输出—回执完整绑定后，才能冻结基线进入第 1 批。

''' + s[end:]

replace('构建身份按需新增 `crates/kernel/build.rs`。', '构建身份可新增 `crates/kernel/build.rs`；§4.3 的来源完整性门槛必须在任何跨文件结构抽取前完成。')
replace('本批采用结构等价线。按当前文件组织逐步缩小参数和写权限，先建立下表职责，再决定是否提取结构体；每个 helper 附读集、写集、缓存失效集、失败点及提交前/后位置。', '本批采用结构等价线，只收窄 crate 内部 helper 的参数和写权限，所有公开可达 API 保持冻结。§4.3 未通过前，非测试编译文件集合不变，只在原文件内抽函数；通过后才按已验收的构建身份协议提取文件或结构体。每个 helper 附读集、写集、缓存失效集、失败点及提交前/后位置。')
replace('局部改为受约束内部阶段类型时，在原校验通过处转换；', '只有第 1 批 API 边界收口通过后，才在原校验成功处引入受约束的私有运行阶段类型；该类型不得出现在任何对外类型中，公开 `Progress`/`State` 的字段与 serde 形状不变；')
replace('每步先用原入口调用提取 helper，对照分支顺序、短路求值、返回值及写入时机；通过后再收窄内部权限。', '§4.3 未验收前仅在原非测试文件内抽取，禁止新增、删除、改名非测试编译文件。每步先由原入口调用 helper，对照分支顺序、短路求值、返回值及写入时机；通过后只收窄私有实现权限，公共签名与可见性保持。')
replace('真正无入口的一组冗余代码附定义/调用/暴露证据后删除。', '仅 crate 私有且确证无入口的冗余项可附定义/调用/暴露证据后删除；公开项即使仓库内零调用也保留，删除或收窄须另立 API 加固批及调用方迁移表。')
replace('等价优化以完整解码记录及原 CLI 文件契约验收；', '等价优化以 §3.5 登记替换后的落盘 JSON 逐字节相等、完整解码记录及原 CLI 契约验收；')
replace('唯一计时字段、共享 target/profile 来源串用', '44 组 A/A 中观测到的唯一不稳定字段、共享 target/profile 来源串用')

# Make all remaining executable bash blocks independent scripts loading env.sh.
perf_start = s.index('### 7.1 ')
perf_end = s.index('### 7.2 ')
perf = s[perf_start:perf_end].replace('HEALTH_BIN', 'HEALTH_PERF_BIN')
perf = perf.replace('```bash\n', '```bash\nset -euo pipefail\nsource "${1:?传入本次 env.sh 的绝对路径}"\ncd "$HEALTH_SRC"\n')
perf = perf.replace('构建独立的 release 继承 profile，从 Cargo 产物消息选择 `HEALTH_PERF_BIN`：', '在本阶段冻结源码根构建独立 release 继承 profile，从本次 Cargo 产物消息选择 `HEALTH_PERF_BIN`，不得覆盖行为基线的 `HEALTH_BIN`：')
perf = perf.replace('  > "$HEALTH_RUN/perf-build.jsonl.log" 2> "$HEALTH_RUN/perf-build.stderr.log"\n```', '''  > "$HEALTH_RUN/perf-build.jsonl.log" 2> "$HEALTH_RUN/perf-build.stderr.log"
python -B - <<'PY'
import hashlib, json, os, shlex
from pathlib import Path
run = Path(os.environ['HEALTH_RUN'])
rows = [json.loads(s) for s in (run/'perf-build.jsonl.log').read_text().splitlines() if s.startswith('{')]
hits = [r for r in rows if r.get('reason') == 'compiler-artifact'
        and r['target']['name'] == 'kernel' and 'bin' in r['target']['kind']]
assert len(hits) == 1 and hits[0]['fresh'] is False and hits[0]['executable']
assert Path(hits[0]['manifest_path']).resolve().is_relative_to(Path(os.environ['HEALTH_SRC']).resolve())
p = Path(hits[0]['executable']).resolve()
(run/'perf-bin.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p)+'\\n')
with (run/'env.sh').open('a') as f: f.write('export HEALTH_PERF_BIN='+shlex.quote(str(p))+'\\n')
PY
```''')
perf = perf.replace('运行器为矩阵、重复次数分配独立文件名，', '有输出测点的主记录、附带记录及周期包一律写 `$CARGO_TARGET_DIR/health-perf/<run_id>/`，不落入待提交的日志目录；原始字节保留，运行目录仅保留哈希、字节数、路径索引和摘要。运行器为矩阵、重复次数分配独立文件名，')
s = s[:perf_start] + perf + s[perf_end:]

replace('第 0 批的安全入口是重锁的前置条件。每次重锁按以下顺序执行，所有命令输出归入新的 `HEALTH_RUN`：', '''第 0 批完成前按 §8.0；完成后按 §8.1。每次重锁独立分配 HEALTH_RUN，记录当前源字节与允许写入范围。

### 8.0 第 0 批完成前的过渡规则

默认只运行 §3.3 第一块的 build/check/Clippy、kernel/topology lib、reference、topology validation 和 doc；不执行七个 CLI 入口，不使用全工作区测试命令。检查前后读取资源保持稳定，实际命令仍受线程与共享 target 约束。

确需 CLI 时，在本次输出目录实拷 `2026-09-22/run_checks.py` 与 `bin/python` 作为过渡实现素材，原文件只读。将 runner 的 O、日志、PATH 和包装器输出根参数化到本次目录，删除全工作区测试入口，只枚举七个明确目标；设置 KERNEL_TEST_EVIDENCE_DIR。原脚本固定写旧日期目录，不能直接重跑。

包装器以“脚本绝对路径及哈希 → 预期输出常量及次数”映射校验：当前六个 Python 入口各自只命中五种候选常量之一，预期一次；先 assert 对应原串 count==1，再只替换该串为 Path 类型的新根，确认旧输出常量已消失。不得要求每个脚本五种常量全命中，也不得在未命中时静默执行原脚本。包装器末尾的类型补换同样登记次数；更简单的实现直接构造 Path 表达式，避免第二轮宽泛替换。未知脚本只允许已登记的只读子进程，禁止泛化放行历史生成器。

在 /tmp 无链接副本按 §3.2 的 no-run、Fresh=false 和来源验收流程验证过渡包装器；产出绑定本次源/包装器哈希的 `transition-isolation-accepted.json` 才能运行指定 CLI 目标。过渡通过不替代永久隔离验收。运行前后核完整保护清单，至少覆盖四棵历史树 `crates/kernel/evidence`、`crates/kernel/复核`、`数据/复核`、`规格/复核`，并包含 R3 写点表中的其他历史位置、旧维护目录、忽略文件和空目录。发生差异保留现场，不用 HEAD 批量回退。

### 8.1 隔离入口验收后的重锁

按以下顺序执行，所有命令台账归入新的 HEALTH_RUN：''')
replace('恢复按 §3.2 对账', '恢复按 §3.1 对账') if '恢复按 §3.2 对账' in s else None
replace('```bash\nmkdir -p "$HEALTH_RUN/positive"', '```bash\nset -euo pipefail\nsource "${1:?传入本次 env.sh 的绝对路径}"\ncd "$HEALTH_SRC"\nsha256sum --check "$HEALTH_RUN/kernel-bin.sha256"\nmkdir -p "$HEALTH_RUN/cargo-test-evidence/positive"')
s = s.replace('$HEALTH_RUN/positive/', '$HEALTH_RUN/cargo-test-evidence/positive/')
replace('第 1 批的只读/恢复 API 与这条输入路径一起验收。', '接入前按候选实际使用的每种转移建立独立参考或独立不变量检查的最小正例、负例及来源/覆盖清单，不等待第 2 批。箱体无线传输须包含非零实际入库正例、空箱/冷却/拒收负例，以及物品在两次传输判断间经出口离箱、无线入库为零的反例；事件名为 transfer 或返回 success 不能替代正数量入库核验。对依赖箱子无线交货的候选，明确采用不接出箱传送带的结构约束，或另有覆盖其相位/判定次序的留存与交货证明；不把“箱子启用 transfer”直接当成已交货。D.5 箱数上界不代替这些机制义务。\n\n第 1 批的只读/恢复 API 与这条输入路径一起验收。')
replace('先查 Cargo/include/import/fixture 和历史负例引用。', '先查 Cargo/include/import/fixture 和历史负例引用。`revision_r3_cli.py` 的两个 r3 历史输入须先按 §3.2 固定为必需只读依赖；迁移后核两组负例仍执行，缺失必须失败。')
replace('每批交付：改动路径和目的、所属工作线、A/B 来源与原始输出、执行命令和退出码、实际测试清单、字段白名单/行为变更契约、调用方或测试迁移表、读写/首错/失败点对照、资源结果及文件保护结果。', '''每批交付：改动路径和目的、所属工作线、A/B 来源与原始输出索引、执行命令和退出码、实际测试清单、字段白名单/行为变更契约、调用方或测试迁移表、读写/首错/失败点对照、资源结果及文件保护结果。

入库范围为运行根的报告、脚本、源码探针、cases/映射/来源清单、journal、保护差异和小型文本日志；所有文件逐个核大小。`cargo-test-evidence/`、共享 target 的 `health-capture/`、封存产物和 `health-perf/`、/tmp 源码树及编译产物不入库，保留位置和完整哈希用于复核。历史 b/c 的 `cargo-test-outputs/` 属显式列出的七项归档例外，须先核每项大小、版本与来源再入库，不继承测试输出的可丢弃身份。不使用整目录无审查添加，也不强制添加大型运行产物。''')

P.write_text(s)
print('rewritten_lines', len(s.splitlines()))
