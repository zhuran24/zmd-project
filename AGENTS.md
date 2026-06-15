# AGENTS.md — Codex working notes for this repo (zmd_pj)

You (Codex) are working in the **Arknights: Endfield IndustrialPlanner exact maximum-empty-rectangle solver**.
This file is read **in addition to** your global `~/.codex/AGENTS.md` (it does not replace it).

Before doing real work in this repo, **read the two project knowledge surfaces below**, then obey the hard rules.

## Read these first (project knowledge)

1. **`CLAUDE.md`** (repo root) — the authoritative project conventions: the **Exactness Constitution**,
   **Forbidden Changes**, architecture map, source-of-truth files, build/test commands, and the AI Safety Contract.
   Treat its *Forbidden Changes* and *Exactness Constitution* sections as hard constraints, not suggestions.

2. **`cc_context/memory/MEMORY.md`** — the **project memory index**. It maps project-relevant knowledge and
   history: the current phase (**P1.2 close**), past **false-CERTIFIED soundness bugs and their fixes**, the
   verification-hardening ladder, dead-end approaches that were already tried and rejected, and environment facts.
   It is an index of one-line pointers — **read the specific linked nodes relevant to your task** before you
   change related code. (Don't dismiss it as "Claude-only": a large part of it is this project's technical memory.)

## Hard rules (not all spelled out in the docs above)

- **Do NOT `git commit` or `git push` unless the task explicitly tells you to.** This repo has a **post-commit
  hook that auto-pushes to GitHub** — an unrequested commit publishes to the remote. Leave your changes
  uncommitted for the human / orchestrator to review.
- **Run the tests before claiming a change is done:** `python -m pytest src/tests/ -q` (full suite is slow;
  see CLAUDE.md "Commands" for the faster xdist form). Full pytest must use an **isolated basetemp** —
  parallel pytest runs in the repo root clobber `.pytest_tmp`.
- **Python:** there is **no `.venv`** here. Use `python` (python.org 3.13 at `C:\Program Files\Python313\`).
  If you must install a dependency, use `--no-deps` (see CLAUDE.md env notes).
- **Never widen proof / exactness semantics**, edit certified proof sources, the campaign hash, or final
  preflight semantics. `certified_exact` and `exploratory` are **strictly separate paths** — never mix them.
- If your task is read-only investigation, **don't modify files or run state-changing commands.**

## Orientation

- Active scope: single base `valley4_protocol_core` 70x70 only; other bases are `future_scope`.
- Entry point `main.py`; architecture and module map are in CLAUDE.md "Architecture".
