---
name: cleanup-preserve-clarify
description: "项目整理原则: 不丢东西 + 清晰. 历史 PoC / experiment / archive 都保留, 但要让物理结构 + 命名 + 文档帮人一眼看懂核心 vs 实验"
metadata:
  type: feedback
  originSessionId: f961efc3-93a4-4068-a05d-b7f8f4592d35
---

**项目整理原则 (2026-05-16 用户原话)**: "不要丢东西, 其他的以清晰为最终目标".

**Why**: 2026-05-16 session 跑完 L1-L9 一堆 lever 都没破 0 FEASIBLE, trial7 (L10 加长 master_seconds) 也在跑. 用户预期如果 trial7 也 fail, 就转去整理项目. 但**整理不等于删**.

具体边界:

**不丢的范围**:
- HiGHS / SCIP PoC 文件 (`src/models/highs_master_model.py` 等) — 验证过死路, 但留作历史 PoC
- Codex-era 遗留测试 (那些用 conftest fixture guard 永远 skip 的) — 留着, fixture guard 已优雅处理
- `_codex_archive/` 139 个 historical 文件 — read-only reference, 不动
- Phase 3B audit/probe 模块 (154 src + 264 tests + 252 scripts) — 全部保留, 只能**搬位置 + 改组织**, 不删
- 13 GB `.artifacts/` 历史 spike 数据 — 留, 是 baseline 对比的真实数据

**清晰的方向** (允许的动作):
- 物理分目录 (例: `src/search/audits/` 收 phase3b_*_audit.py, `src/search/probes/` 收 *_probe.py)
- 集中文档 (例: ENV 变量总表, 列 30+ `EXACT_*` 的 name / default / 用在哪)
- 命名一致性 (但**不重命名 import-heavy 文件**, 太多 ripple)
- README / FILE_STATUS / CLAUDE.md 增加 "活跃 vs 实验" 标记
- 把已知"永不再用" 但又不能删的东西明确隔离 (例: `src/_experimental/`)

**禁止的动作**:
- `rm` 任何 .py / .md / .json 文件 (即使 conftest 显示 skip)
- 删 `_codex_archive/` 子树
- force-clean `.artifacts/`
- 撤回历史 commit (即使是 negative result session)
- 简化"对运行多余但对历史有意义"的 metadata 字段

**How to apply**:
- 用户要整理时, 默认动作是**重组 / 加文档 / 加索引**, 不是**删**
- 如果觉得某文件真的"占地方", 写 deprecation note 在文件头, 不删
- 整理时每动一个文件 commit 一次, 方便回滚
- 重组后跑全套 pytest 验证 import 路径都对, 不能 break 现有测试

**链**:
- 2026-05-15-ram-session-misdirected — 这次 session 跑偏的反思
- [[clarity-over-brevity]] — 沟通清晰原则的姐妹条目
