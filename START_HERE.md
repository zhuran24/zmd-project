# START_HERE.md

Current phase: Phase 1.2 spike close remains blocked. V50 simplified the close gate: the three-clean-review standard is still owner policy, but the clean-review count is owner-maintained outside the repo. The repo no longer opens P1.3B from receipts, reports, package metadata, source-tree manifests, or package-internal Git authority; it remains fail-closed until an explicit owner manual decision.
This repository is a lightweight GitHub source checkout plus recoverable
historical artifacts. It is meant to stay easy to clone and inspect while still
recording where the large certified-exact inputs came from.

## Current Development Surfaces

- `src/` is the active solver implementation. The core exact path lives mainly
  under `src/search/`, `src/models/`, and `src/cuts/`.
- `rules/` and `data/preprocessed/` hold certified input contracts. In current
  `main`, the large production placement pool is external; see "Large Artifact
  Policy" below.
- `specs/`, `PROJECT_LOCK.md`, and `docs/subjects/` carry the contract language
  for exactness and documentation projections.
- `scripts/` contains entrypoints, gates, artifact builders, audits, and many
  historical spike helpers. Start with `scripts/README.md` before running an
  unfamiliar script.
- `.github/` contains GitHub-side automation metadata.

## Phase Close Gate

Phase 1.2 is not formally closed. The current machine-readable gate is
`data/review_gates/phase_1_2_spike_close.json`; the human contract is
`docs/PHASE_1_2_CLOSE_GATE.md`. Before P1.3B master-integration work, run:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

That command is expected to fail at the current baseline because P1.3B is not
opened by an owner manual decision. The repo no longer computes the clean-review
counter; the owner maintains that count outside the repository.  The current
post-V92 review anchor is `v92_release_status_allowlist_sealing`,
which keeps certified lifecycle evidence split into cut replay (persisted
exact_safe_cuts are telemetry, never proof objects), master-domain
(time-budget-partial precheck groups never stand in for complete infeasibility
proofs), replayable frontier terminal evidence (fully oriented candidate
domain, candidate-domain slicing axes sealed, project-level admissibility
bound, and deny-unknown evidence keys), disk-authoritative delivery-manifest
writing, canonical certified manifest publication, export-surface proof
obligations (the single-base release path rejects self-claimed CERTIFIED run
summaries), and closed allowlist handling for certified `EXACT_*` env knobs
after V57-V92.

## Knowledge Surface Roles

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer START sha256:9dd6b559dd17a70fab730793a77d2e4a91c27eedcdfbf1bf81fdeba5f658592f -->
The project uses **one logical knowledge tree with two physical projections**. `docs/` is the stable documentation projection; `cc_context/memory/` is the collaboration-continuity projection. Neither tree is allowed to become a second independent truth source: volatile living claims should be promoted into a subject field and projected to every surface that needs them.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer END -->

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:docs_role START sha256:33a68fa34851c05416e51ad86e69e80c86595e6cf05b70a8d248bac6bb916c63 -->
The documentation tree is the stable project surface. It answers: what the project is, what the current contract is, how it is verified, how it is delivered, and where historical material lives. It should be publishable, reviewable, and low-noise.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:docs_role END -->

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role START sha256:29ad99c8cfd99eeb1c5b120f5028478ab5d2083ee1d4075293639ba3e6c66ea9 -->
The memory tree is the collaboration-continuity surface. It answers: what the previous working window knew, which mistakes were already corrected, what user preferences or process constraints matter, which old statements must not be trusted blindly, and what the next window should read first.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role END -->

## Large Artifact Policy

Current `main` intentionally does not track these large working-tree payloads:

- `data/preprocessed/candidate_placements.json`
- `cc_context/review/*.zip`

The production `candidate_placements.json` is still a certified-exact input. It
is not optional for full certified runs, but it is stored outside the current
GitHub working tree to keep the repository light.

Known recovery facts for `data/preprocessed/candidate_placements.json`:

- expected size: `53,594,995` bytes
- expected SHA256:
  `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`
- historical Git source: commit `f58f0e2`, path
  `data/preprocessed/candidate_placements.json`
- local archive source used for the GitHub backup:
  `C:\22957\download\zmd.7z`, nested under `zmd/data/preprocessed/`

Do not recommit that file to normal Git unless the repository policy changes to
Git LFS, release assets, or another explicit large-artifact store.

Repo-native checks and restore commands:

```bash
python scripts/check_external_artifacts.py
python scripts/check_external_artifacts.py --require candidate_placements
python scripts/restore_external_artifacts.py candidate_placements --source /path/to/source/file/or/root --force
```

`python scripts/check_external_artifacts.py` accepts the lightweight checkout where
`candidate_placements.json` is absent. Use `--require candidate_placements` before
certified exact runs that need the production placement pool.

## Historical And Context Surfaces

- `_cc_live_memory/` is recovered context memory. It is useful for archaeology,
  not a runtime entrypoint.
- `.artifacts/` is generated review/probe output. Treat it as evidence and
  history, not source code.
- `cc_context/` contains review bundles, prompts, handoffs, and previous
  external review context. `cc_context/HANDOFF.md` is a historical 2026-05-30
  handoff snapshot and is not the current entrypoint.
- `docs/research/` and `third_party_snapshots/` preserve research and upstream
  snapshots. Read them when needed, but do not treat every old note as current
  project state.

## First-Pass Cleanup Boundaries

- Do not split `src/models/master_model.py`, `src/models/exact_coordinate_master.py`,
  or `src/search/benders_loop.py` casually. They are large, but they also carry
  exactness assumptions.
- Do not weaken `PROJECT_LOCK.md` exactness rules to make a local test easier.
- Do not promote postprocess, viewer, adapter, or exploratory artifacts into
  certified proof inputs.
- When changing documentation projections, edit the subject in `docs/subjects/`
  and run `python scripts/sync_doc_subjects.py --sync`.


Phase close gate: docs/PHASE_1_2_CLOSE_GATE.md
