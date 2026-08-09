# P1.2 v30 candidate review reset evidence

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Status: NOT CLEAN.

The v30 candidate review found a major/soundness issue in the evaluator hot path: ghost-bound cut evaluators could still fire after scope drift if a caller reached evaluation before replay/Step 6. The follow-up patch at commit `8e572e9` guarded the ghost-bound evaluator scope, but the review itself remains non-clean and does not increment the Phase 1.2 close counter.

Gate effect: consecutive clean full review counter remains `0/3`.
