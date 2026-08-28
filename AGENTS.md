# ZMD RESEARCH WORKTREE

Mode: `RESEARCH`. Branch: `research/main`.

This worktree owns the full ZMD research program. The zero-condition whole-layout campaign is the current point of attack, not the final mission.

## Cold start

Run:

`/home/zhuran24/zmd-pj/.venv/bin/python research_lab/tools/research_tree.py enter`

First active read: `/home/zhuran24/zmd-research/research_lab/STATE.txt`.
It must contain one current endpoint, one live question, and any inflight recovery handle.
For cross-tree handoff, owner matters, or cross-session external work only, read `/home/zhuran24/.claude/ops/zmd-pj/membrane/NOW.md`.
Ordinary R0 work remains local and does not enter O.

Read `research_lab/PROGRAM.txt` on first entry or when the goal hierarchy changes. Read the active campaign named by `.zmd-worktree-mode` after STATE or when the current question needs it. Load old governance and history only on demand.

Must-read on every new session and again after every context compaction: load the `/zmd-method` and `/research-charter` skills (the latter is the charter's authoritative text; current bets stay in `/home/zhuran24/zmd-pj/docs/项目说明/30_research_charter.md`). On conflicts the owner-quotation anchors win (`research_lab/METHOD_ORIGIN.txt` for method, `research_lab/STANCE_ORIGIN.txt` for stance).

Claude Code auto-memory is bound to the research-only directory recorded in `research_lab/CC_MEMORY.txt`. It carries stable research habits, not current campaign state; `STATE.txt` and the active campaign remain authoritative for what is happening now.

## Default attention

Start from the problem: rules, resource accounts, death shapes, constructive structure, representations, layer boundaries, and the cheapest discriminating experiment. Existing modules, F1-F9 names, current layer count, and current cut forms are historical candidates, not axioms.

Do not preload `PROJECT_LOCK.md`, `docs/CURRENT.md`, the ledgers, or the full operations manual for ordinary discovery. Read them on demand for exact current authority, certified semantics, promotion, publication, shared-Git repair, or a specific operational contract.

## CodeGraph first

For indexed code, use the CodeGraph MCP as the default first and recurring instrument, not as a ceremonial one-time lookup. Whenever CodeGraph can serve the question, use it. Before understanding a code path or editing code, call `tools.codegraph.org.default.codegraph_explore` with `projectPath=/home/zhuran24/zmd-research`; name concrete files and symbols, inspect the returned call paths and blast radius, and call it again when the question moves to another code surface. Treat returned source as already read. Fall back to direct file reads only for unindexed material, a detail the graph did not return, or a file explicitly marked stale. After edits, respect the MCP staleness banner or wait for its auto-sync. CodeGraph supplies structural context; compilation, tests, checkers, and runtime evidence still decide correctness.

This applies to dispatched seats as well as the main session: every Agent / Workflow / peer-session task brief that touches code in this tree must state CodeGraph-first explicitly and pass `projectPath=/home/zhuran24/zmd-research`.

## Research freedom and truth discipline

Conjectures, heuristic search, temporary sufficient restrictions, alternative models, throwaway prototypes, and small counterexamples are allowed. Label their status and cost. Do not silently convert them into necessary conditions.

`UNKNOWN` is not infeasibility. A failed constructor does not prove nonexistence. A local theorem does not ban an outer object without a transport proof. Preserve premises and scope without wrapping routine idea generation in approval rituals.

This tree may create candidate theorems, algorithms, representations, cut forms, witnesses, and promotion packets. It never grants production, certification, U/L updates, durable strong status, release authority, or owner authority.

## Repository roles

`/home/zhuran24/zmd-pj` is the history/material tree and remains read-only. The independent certification tree is `/home/zhuran24/zmd-certification` on `certification/main`.

Do not merge this branch wholesale into the certification tree. Mature work crosses by a compact promotion packet containing the exact claim, premises, selected commits or diff, reproduction commands, controls, known unknowns, and requested effect. Certification is a fresh-session cold review.

## Work rhythm

Let each result change the next question. Choose the lightest honest R0/R1/R2 check level from `research_lab/CHECKS.txt` according to the effect being claimed, not according to the file path. Keep durable research changes in small coherent commits with exact pathspecs. Put logs, caches, solver dumps, temporary models, and regenerable artifacts under `research_lab/local/`.

Use `/home/zhuran24/zmd-pj/.venv/bin/python` for project Python commands; this lightweight worktree intentionally has no copied virtual environment.
