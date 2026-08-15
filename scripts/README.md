# `scripts/` operator map

This page maps stable script roles. It does not copy the current artifact digests, gate state, test
counts, retirement inventory, or frozen input sizes. Use the machine governance ledgers and
[`docs/CURRENT.md`](../docs/CURRENT.md) for those values.

## Campaign operations

| Entry | Stable role |
|---|---|
| campaign launch wrappers | Start or resume runtime work without redefining proof semantics |
| `campaign_watchdog.sh`, `stop_campaign.sh`, `temp_logger.sh` | Process and telemetry operations |
| `inspect_exact_campaign_state.py` | Read-only inspection or informational report generation |
| `run_supervisor_seal.py` | Explicit supervisor invocation through the production sealing path |

A wrapper must not convert candidate success into terminal or public certification. The producer,
supervisor, and publisher remain separate implementation roles; see
[`docs/exact_campaign_operations.md`](../docs/exact_campaign_operations.md).

## Gates and audits

The active preflight and focused checkers are discovered from their current command-line interfaces
and the repository governance sources. Common entrypoints include:

- `scripts/preflight_gate.py` for the registered repository lanes;
- `scripts/check_phase_review_gate.py` for the owner gate structure;
- `scripts/check_p1_2_proof_obligations.py` for registered close-kernel obligations;
- `scripts/check_strong_status_write_allowlist.py` for strong-status write sites;
- `scripts/check_external_artifacts.py` for external artifact presence and byte identity;
- `devtools/artifact_evidence.py` for rebuilding and validating the dossier-derived artifact boundary projection;
- `scripts/check_artifact_boundaries.py` as the frozen certified consumer of that projection;
- `devtools/check_repository_code_assets.py` for code-asset classification and workflow projections.

Each checker proves only its declared contract. A green checker is not an owner decision, a global
soundness proof, or a publication verdict.

## Review packaging

`package_review_snapshot.py` creates a review convenience package. It must pin one immutable source
revision for provenance and materialization, and its manifest must preserve the limitations of the
selected checks. A review package is not certification authority.

## Export, viewer, and preprocess tools

IndustrialPlanner builders, validators, viewers, and report generators emit consumer or review
derivatives. They may use familiar filenames inside their own output roots, but cannot write the
canonical certified surface or preserve proof-bearing labels without the central verdict.

Vendor refresh and preprocess scripts are mechanical transformations. Changing canonical or
hash-bound inputs still requires the governing owner, identity, reset, and replay procedures. Obtain
current identities from the registered manifests and checkers rather than this README.

## Spikes, profiles, and historical executables

PoC, spike, profiling, phase-specific builders, and replay wrappers may be active tools, retirement
candidates, or historical evidence. A tracked path is not automatically part of the developer default
surface. Consult `data/repository_governance/code_assets.json` and use the explicit evidence or replay
workflow when required.

The Pumpkin PoC has its own bounded guide: [`pumpkin_poc/README.md`](pumpkin_poc/README.md).

## Finding and validating a script

```bash
rg -n '<keyword>' scripts devtools

git grep -n -I -e '<keyword>' -- scripts devtools

python <script> --help
```

The first search follows the developer projection; the second searches tracked paths. Before using a
command copied from a historical report, verify that the path still exists, inspect its current
classification, read its help, and follow [`docs/AGENT_OPERATIONS.md`](../docs/AGENT_OPERATIONS.md).

Before editing a script guide, query its local document contract:

```bash
.venv/bin/python devtools/docctl.py context scripts/README.md --intent edit
```
