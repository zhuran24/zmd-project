# Gemini Math Review Bundle

This bundle contains an advisory review and a project-doc patch set.

## Files

- `GEMINI_MATH_REVIEW_ACTION_PLAN_20260523.md` — standalone full review and implementation plan.
- `checklists/ACCEPTANCE_CHECKLIST.md` — Phase 1.2 P0 acceptance checklist.
- `checklists/RED_FIXTURE_MATRIX.md` — red fixture matrix for the flagged math risks.
- `notes/CP_SAT_INTEGRATION_NOTES.md` — why CP-SAT should not use `AddLazyConstraint` here.
- `notes/F9_MORPHOLOGY_CAUTION.md` — safe vs unsafe morphology use.
- `patches/0001-add-gemini-math-triage-doc.patch` — patch adding the review into the project docs.
- `patches/0002-add-phase1-2-p0-acceptance-doc.patch` — patch adding the acceptance checklist into the project docs.

## How to apply docs patches

From the project root:

```bash
git apply patches/0001-add-gemini-math-triage-doc.patch
git apply patches/0002-add-phase1-2-p0-acceptance-doc.patch
```

These patches are documentation-only. They intentionally do not change solver semantics.
