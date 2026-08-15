# Repository governance ledger

This directory contains fail-closed governance sources and generated compatibility projections. None of them can authorize an edit, close a phase, or certify a mathematical result.

The document framework bootstraps from [`.docsystem/manifest.json`](../../.docsystem/manifest.json). Effective rules come from inherited `DOC_POLICY.json` files plus schemas and registries under `document_system/`. Query a target before changing it:

```bash
.venv/bin/python devtools/docctl.py context <path> --intent edit
.venv/bin/python devtools/docctl.py check --changed
```

## Document sections and convergence

The [front-door registry](document_system/entrypoints.json) declares bounded entry surfaces, guarded guides and generated compatibility redirects. The [section registry](document_system/sections.json) assigns stable section IDs through effective policies and generates [`docs/SECTION_INDEX.md`](../../docs/SECTION_INDEX.md). The same graph generates [`docs/CONVERGENCE_REPORT.md`](../../docs/CONVERGENCE_REPORT.md), which checks local reachability, unique current responsibilities, volatile-state discipline and retired-entrypoint isolation.

```bash
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-convergence --write
.venv/bin/python devtools/docctl.py doctor
```

## Non-mutating document governance gate

The manifest points to [`document_system/governance_gate.json`](document_system/governance_gate.json), its adjacent schema, `devtools/document_governance_gate.py`, and the shared CI workflow. Local agents, pull requests, pushes and scheduled audits select a profile from this one registry; the workflow does not maintain a parallel lane list.

```bash
.venv/bin/python devtools/document_governance_gate.py list --json
.venv/bin/python devtools/docctl.py gate --profile changed
.venv/bin/python devtools/docctl.py gate --profile full
```

Every lane runs in its own process with an external temporary root. The runner fingerprints HEAD, the index, Git-visible paths, status and changed or non-ignored untracked bytes before and after execution. A lane failure, timeout or repository-state change blocks the gate. Render and repair actions are deliberately excluded; write projections first, then run the gate against the resulting tree.

The `changed` profile uses `check-current` for code-assets governance and explicitly does not claim frozen historical replay. The `full` and `weekly` profiles retain the historical checker and require the supplier Git objects named by the ledger.


## Periodic semantic maintenance audit

[`maintenance_audit.json`](document_system/maintenance_audit.json) declares read-only weekly, deep and phase-close profiles over existing truth sources; [`docs/MAINTENANCE_QUEUE.md`](../../docs/MAINTENANCE_QUEUE.md) is their generated phase-close projection. Run `.venv/bin/python devtools/docctl.py audit --profile weekly`; at a boundary use `--profile phase_close --as-of YYYY-MM-DD`, then repair the original ledger or policy and run `docctl.py render-maintenance --write`. Do not hand-edit the queue or treat Git last-touch dates as semantic review.

## `doc_classes.json` - legacy compatibility projection

`devtools/docs_reference_scan.py` still consumes `doc_classes.json` at this fixed path, but the file is generated rather than maintained as a second classification source:

```text
document_system/legacy_doc_scan_base.json
  + legacy_projection fragments in distributed DOC_POLICY.json files
  -> devtools/docctl.py render-legacy
  -> doc_classes.json
```

Change the nearest policy, then run:

```bash
.venv/bin/python devtools/docctl.py render-legacy --write
.venv/bin/python devtools/docs_reference_scan.py validate-registry
.venv/bin/python devtools/docctl.py doctor
```

The scanner's `locked`, `historical` and `living` classes serve only its cleanup contract. They do not grant mutation rights and do not replace `docctl context`. Every in-scope Markdown path must be covered or explicitly excluded with a reason; incompatible rule overlap remains an error.

Its self-check assumes a cooperative operator. `truth_sources_clean` covers only the object classes named in the report, not arbitrary adversarial repository construction. The exact threat boundary and the standing owner decision are documented in the `devtools/docs_reference_scan.py` module docstring.

## `document_system/entrypoints.json` - fixed front-door registry

The registry contains roles and contracts, not live gate values, hashes, bounds or test counts. Change it together with the exact-path policy, then rebuild:

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py doctor
```

Do not hand-edit generated redirects. Framework rationale and safe-change requirements live in `docs/governance/document-system/ARCHITECTURE.md` and `MAINTAINING.md`.

## `artifact_boundaries.json` - generated tracked-evidence projection

The semantic inputs are deliberately small:

- top-level `.artifacts/<dossier>/` roots come from `data/knowledge/dossiers.json`;
- direct files below `.artifacts/` and ignored runtime prefixes live in `artifact_evidence_inputs.json`;
- the adjacent input and projection schemas define both shapes.

`data/artifact_boundaries.json` is a generated schema-v1 compatibility surface for the frozen certified checker. The generator emits quote-prefixed records for Git's human-readable C-quoted path form. Semantic consumers ignore those compatibility-only strings and use exact dossier roots plus direct files.

```bash
.venv/bin/python devtools/artifact_evidence.py render --write
.venv/bin/python scripts/check_artifact_boundaries.py
.venv/bin/python devtools/artifact_evidence.py check
```

A new tracked package first needs a dossier record. A new direct root file belongs in `artifact_evidence_inputs.json`. Runtime prefixes cannot overlap evidence or contain tracked files. Do not hand-edit the projection or modify the frozen checker merely to accommodate its generated input.

## `code_assets.json` - code asset ledger

`code_assets.json` and its schema classify Git-visible code assets and define search, lint, pytest and capability projections. Its `artifact_evidence_boundary` descriptor points to the semantic inputs, schemas and compatibility projection above.

For the current worktree, registered artifact evidence is excluded before content inspection. An unregistered `.artifacts/**` code file remains a code asset and trips the count gate. Historical commit inventory is measured raw, without today's dossier exemption, so a complete Git history can replay its recorded baseline under the original tree.

Registration does not make evidence current, executable, certified or production-authoritative, and it does not prove byte immutability.

```bash
.venv/bin/python devtools/artifact_evidence.py check
.venv/bin/python devtools/check_repository_code_assets.py inventory --format json
.venv/bin/python devtools/check_repository_code_assets.py check-current
.venv/bin/python devtools/check_repository_code_assets.py check
```

Do not use `inventory --commit HEAD` as a substitute for the live boundary. Current inventory intentionally excludes registered evidence before reading it, while commit inventory retains those paths for historical semantics and may need to read a multi-gigabyte tree. Historical replay belongs to the pinned baseline commit in the ledger.

Production imports from `devtools` remain forbidden. The only admissible literal exception is an exact `literal_only / dormant_advisory_pointer` record bound to one production file, assigned symbol and path string. Broad matches, dynamic calls, imports and stale exception records fail closed.

`check-current` validates the current projection and prints the historical receipts it did not check. Only `check` performs those comparisons.

Historical replay requires the Git objects named by the ledger. A supplier snapshot that omits them must remain fail-closed rather than rewriting the frozen receipt to fit the available checkout.
