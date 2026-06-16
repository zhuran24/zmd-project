# P1.2 v30 candidate review reset evidence

Status: NOT CLEAN.

The v30 candidate review found a major/soundness issue in the evaluator hot path: ghost-bound cut evaluators could still fire after scope drift if a caller reached evaluation before replay/Step 6. The follow-up patch at commit `8e572e9` guarded the ghost-bound evaluator scope, but the review itself remains non-clean and does not increment the Phase 1.2 close counter.

Gate effect: consecutive clean full review counter remains `0/3`.
