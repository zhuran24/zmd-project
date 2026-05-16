# 2026-05-16 Cleanup Session Summary

整个 session 完成的项目整理工作汇总. 记录每个动作的范围 + commit + 验证状态.

**原则** (per memory `feedback_cleanup_preserve_clarify`):
- 重组 / 加文档 / 加索引 OK
- 删任何文件 NOT OK
- 每动一个 commit 一次方便回滚
- 跑全套 pytest 验证

---

## 起因

session 后半段 trial7 confirm L10 (A 路径 - master_seconds=3600 + workers=8) 也 UNKNOWN 后, 项目主线"破 0 FEASIBLE" 已全 lever verify 死路. 转项目整理.

用户原话: "原则的话就是不要丢东西, 其他的以清晰为最终目标".

后续 `/goal 开始项目代码整理` + `/goal 懂了 1-8 全做完`.

---

## 动作清单 (1-8)

### 动作 1: lever_verdicts 总表 ✅

`docs/lever_verdicts.md` (252 行). 主线 master 加速 lever 路线 L1-L11 + 实测 verdict.

- L1 RAM 优化 ❌
- L2 HiGHS/LP-MIP 重写 ❌
- L3 Model size 局部优化 ❌
- L4 EXACT_POWER_PLACEMENT_SUBPROBLEM 重开 ❌
- L5 OR-Tools 9.16 等 ❌
- L6 AI sidecar 🟡 长期 option
- L7 Community blueprint hint ❌ (integration 完美但 master 解不动)
- L8 Search profile 切换 ❌
- L9 Objective relaxation ❌ (假设错了, master 本来就是 feasibility)
- L10 加长 master_seconds + workers=8 ❌
- L11 Hard constraint 🟡 唯一未试 + 大概率 FEASIBLE 路径

**Commit**: c5c57af

### 动作 2: env_variable_index 集中索引 ✅

`docs/env_variable_index.md` (230 行). 100+ `EXACT_*` / `PHASE3B_*` env 变量分 11 组:

- A 组 Worker / 并行
- B 组 时间 / 超时
- C 组 Master CP-SAT 调优
- D 组 Hint 注入
- E 组 路径开关
- F 组 守卫
- G 组 Precheck
- H 组 Subproblem
- I 组 Power coverage encoding
- J 组 Process priority
- K 组 Phase 3B specific

每条 name + type + default + reader file + 一句话作用. 含 strip list 注意事项 + 命名约定.

**Commit**: 1a280dd

### 动作 3: 巨型文件 docstring 索引 ✅

3 个 5000+ 行单文件顶部加 module docstring 索引段, 列主要 section 行号 + 公开 API + env 引用:

- `src/models/master_model.py` (11754 行) — ExactMasterCore / MasterPlacementModel / solve / warm_start 锚点
- `src/models/exact_coordinate_master.py` (6529 行) — delegate 类构造 + ghost constraints + apply_solution_hint 锚点
- `src/search/benders_loop.py` (5553 行) — _run_certified_exact 内 community hint 注入点 L3565 + master.solve 调用 L3844

**Commit**: 3bb3dbb

### 动作 4 (fix): .gitignore + 移除 accidental submodule ✅

3bb3dbb 上个 commit 用 `git add -A` 误把两个 `.claude/worktrees/agent-*` 当 embedded git repo 加进 index. 修:
- 从 index 移除两个 worktree ref (`git rm --cached`)
- `.gitignore` 加 `.claude/worktrees/`

**Commit**: 59496cc

### 动作 5: README 状态地图 ✅

README.md 顶部加:
- Phase 状态表 (3A done / 3B in progress / 3C planning)
- 6 个关键文档入口 (CLAUDE.md / PROJECT_LOCK / FILE_STATUS / lever_verdicts / env_variable_index / phase3b plan)

不动 Phase 3A 旧内容 (IP delivery surface 文档没过期).

**Commit**: eb8eef3

### 动作 6: 5 个 Codex-era 永远 skip 测试加文件头注释 ✅

5 个 `test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_*.py` 加文件头 docstring 说明:
- 为啥永远 skip (依赖 Codex-era artifact 不存在)
- conftest fixture guard 已优雅处理 (不报错)
- 保留原因 (历史 reference + 未来 artifact 复现时可 re-enable)
- 不删的 cleanup 原则

**Commit**: 239240f

### 动作 7: Phase 3B 670 文件物理分类索引 ✅ (文档版)

`docs/phase3b_module_index.md` (317 行). 670 个 phase3b 文件按 cluster 分类 + active 主线 vs 历史 spike 区分.

**Commit**: 0ad6250

### 整理 1-7 第二轮 ✅

`7b46367` 一个 commit land:

- **#1** test_master.py / test_exact_contract.py 顶部加目录索引 docstring (10440 行 / 5666 行)
- **#2** `src/adapters/README.md` — 4 个 adapter 子目录职责 + 数据流向
- **#3** HiGHS/SCIP PoC 3 文件加 STATUS 标 "实验 PoC 死路, 留 reference"
- **#4** `docs/specs_index.md` — 23 份编号 spec 索引 + 9 份 ecosystem_notes
- **#5** `scripts/README.md` — scripts/ 入口分类
- **#6** CHANGELOG.md 补 2026-05-16 完整记录
- **#7** memory MEMORY.md 更新 D step 2 hint integration 状态 + superseded 标记

**Commit**: 7b46367

### 动作 8: Phase 3B 670 文件物理重组 ✅

真正 `git mv` 670 文件到 cluster 子目录 + 改 import 路径 + 改 conftest guard.

实际重组结构 (agent 完成):
```
src/search/phase3b/<cluster>/<short_name>.py       (36 cluster dirs)
src/tests/phase3b/<cluster>/test_<short_name>.py
scripts/phase3b/<cluster>/build_<short_name>.py    (含 ai_sidecar 子目录, 因 src 没 runtime)
                  checkpoint_free/signature_bucket/<14 sub-cluster>/
3 顶层 + 177 cluster/sub-cluster 目录 = 180 个 __init__.py
```

实测改动量:
- **866 files changed, 5263 insertions, 5381 deletions**
- 670 git mv (R/RM) + 大量 import 改 + 跨 cluster runtime path 改

agent (ac8251f4dfdf08bca) 遇到 7 个真实 surprise + 全部解决:

1. `sed s@scripts.build_X@...@g` 里 `.` 匹配 `/`, code_context 中的字符串路径被误改 — 加 `fix_mangled_paths.py` 反向矫正
2. `runtime_patch_status.py` 用 `Path(__file__).parent / "sibling.py"` 跨 cluster, 改成 `parents[2] / cluster / file.py`
3. 252 个 scripts 的 `PROJECT_ROOT = parents[1]` bootstrap 因新位置深度变, 改为 `parents[N]`
4. conftest `_FIXTURE_GUARDS` substring 不再连续 (path 加了 `/` 分隔), 改用 path component (`signature_bucket/powered_support_coverer`), 25 个 skip 测试验证仍 work
5. `ruff.toml` per-file-ignores `scripts/build_*.py` 不再 match, 加 `scripts/phase3b/**/build_*.py`
6. 5 个 anchor119_row_domain 测试用 Path split string, sed 没覆盖, 手动 multi-line regex 改
7. 2 个 acceptance_authorization 源文件 hardcode split path string, 手动改

最终 pytest: **2207 passed, 60 skipped** in 245s — 跟 baseline 完全一致 ✓.

**Commit**: e4bad28 (1 大 commit, 而非分阶段 — 因 mv + import 耦合, 回滚单 revert 更简单)

agent 总跑 1h, 未超时.

---

## 全 session 数据

- **commits**: 11 (c5c57af → e4bad28)
- **文档增加**: ~1500 行 (8 个新 docs + 6 个 file-header docstring 索引)
- **代码改动 (动作 1-7)**: 0 行逻辑代码
- **代码改动 (动作 8)**: 866 files, 5263 ins / 5381 del — 全部 import 路径 + module rename + conftest guard + ruff config, 零业务逻辑
- **删除文件**: 0
- **pytest**: 2207 passed + 60 skipped (1-8 后最终验证) — 跟 baseline 完全一致

---

## 后续 (动作 8 完成后) ✅

全部完成:
1. ✅ Agent 报告 + 验收 (pytest 2207 pass, diff 866 files)
2. ✅ Agent 实际直接在主 tree commit (worktree 共享 .git, e4bad28 直接进 master)
3. ✅ pytest 最终验证 (2207 passed + 60 skipped, 一致 baseline)
4. ✅ 此 doc 更新动作 8 commit hash + 实测 stats
5. ✅ task #93 close
6. ✅ /goal 自动 clear

---

## Memory 链

- [[feedback_cleanup_preserve_clarify]] — 整理原则
- [[feedback_clarity_over_brevity]] — 沟通清晰原则
- [[project_d_step2_hint_landed]] — D step 2 hint integration 详情
- [[project_2026_05_15_ram_session_misdirected]] — 之前 RAM session 跑偏 lesson
