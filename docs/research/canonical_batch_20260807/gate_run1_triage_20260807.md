# gate 首轮红跑归因记录（2026-08-07，worktree 环境缺件，非本批内容）

首轮双 gate 在隔离 worktree 内双红（full exit 1 / slow exit 1），逐条归因后全部为
worktree 环境缺件，与 canonical 修正批的任何 tracked 改动无关。修复后第二轮双绿
（`gate_full_20260807.log` / `gate_slow_20260807.log` 即第二轮完整输出）。

## 红因三条与证据

1. **full lane pytest「6 failed + 18 errors」与 slow lane 2 failed 同根**：worktree 缺
   `.venv`。r4 external-brain verifier 硬断言
   `python.executable == <repo>/.venv/bin/python`
   （`docs/research/r4_external_brain_handoff_20260722/verify_r4_handoff_package_v1.py:27`
   定义 `EXPECTED_PYTHON_PATH = PROJECT_ROOT / ".venv/bin/python"`，`:595` 比较），
   PROJECT_ROOT 按模块文件 resolve 到 worktree；用主仓 venv 跑测试时身份不等 →
   `build_record_preseal_only=False` → receipt FAIL（`--showlocals` 坐实）。
   ab16 slow 双红是 `<repo>/.venv-uvbolt-backup` 缺失
   （`test_noncert_cuts_ab16_self_contained_chain_v1.py:220` `resolve(strict=True)`
   FileNotFoundError）。
2. **review-gate check BLOCK**：`data/review_gates/phase_1_2_spike_close.json` 的 4 个
   informational history evidence 路径（`.artifacts/ghost_strict_fix_20260805/
   {round3_verdicts_20260806,mutation_manifests_20260806}` 两目录 +
   `.artifacts/preflight_{full,slow}_sealbatch_20260806.log`）在 worktree 的
   `.artifacts` 部分副本中缺失，主仓全部存在。
3. 磁盘门槛（r4 要求 free ≥ 10 GiB）实测 23G，非红因。

## 修复（全部 untracked，不碰 tracked 树，不入提交）

- `ln -s /home/zhuran24/zmd-pj/.venv .venv`；`ln -s /home/zhuran24/zmd-pj/.venv-uvbolt-backup .venv-uvbolt-backup`；
- 从主仓拷 4 个 `.artifacts` 证据路径进 worktree `.artifacts/`；
- （更早）`scripts/restore_external_artifacts.py candidate_placements` 恢复 54MB 池子
  （f05b1291 verify）；`mkdir .pytest_tmp`（tmp_path fixture `mkdir(parents=False)`）。

## 修复后复验链

- r4 文件单跑：32 passed（原 9 errors）；
- ab16/gate1_v4 两条 slow 单跑：2 passed；
- fast lane 直跑全量：7232 passed, 126 skipped, 0 failed/errors（skip 数与红跑一致 =
  无新增静默 skip）；
- 第二轮双 gate（worktree 路径 venv 保身份一致）：full **PASSED 20 passed**、
  slow **PASSED 33 passed**（红跑 slow = 2 failed + 31 passed，总数 33 一致）。

红跑日志 forensic 留档（机器本地 scratchpad，不入库）：
`gate_full_20260807_red_envgap.log` / `gate_slow_20260807_red_envgap.log`。

## 沉淀

worktree 委托的环境预置四件套（已由主线程落记忆卡）：venv 双符号链 /
`.artifacts` 证据路径 / candidate_placements 恢复 / `.pytest_tmp` 父目录。
r4/track-b 系环境债的耐久修复既有欠账单（roadmap 08-02 行）不变。
