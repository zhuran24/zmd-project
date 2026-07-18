# `scripts/` operator map

As of 2026-06-26 the tracked directory contains 434 Python files, 13 PowerShell files, 12 shell
files, 2 Markdown files, 1 FZN file and 1 MJS file. Counts are inventory only, not a gate or proof
claim. Most `build_*`, phase3b and PoC scripts are artifact generators or historical diagnostics,
not daily authority entrypoints.

## Certified campaign operations

| Script | Role |
|---|---|
| `run_campaign_p2_workers1.sh`, `run_campaign_workers2.sh`, `run_campaign_linux.sh` | Runtime wrappers; they do not redefine proof semantics |
| `campaign_watchdog.sh`, `stop_campaign.sh`, `temp_logger.sh` | Process/telemetry operations only |
| `inspect_exact_campaign_state.py` | Read-only or report-producing inspector; never a proof source |

The producer/supervisor/publication boundary lives in Python source. The production supervisor
launcher is `scripts/run_supervisor_seal.py` (independent marker-driven command, landed
2026-07-04); `main.py` and campaign wrappers still stop at `CANDIDATE_PROPOSED` and never seal
as a side effect.
A wrapper must not convert candidate success into terminal or public `CERTIFIED`, and method
existence must not be documented as an operational supervisor service.

## Gates and audit entrypoints

`preflight_gate.py` currently runs hash/external-artifact checks, forbidden-path and
exact/exploratory isolation checks, research coverage, line-ending/secret/artifact-boundary checks,
phase gate, P1.2 obligations, scoped cc_memory consistency, strong-status allowlist, mypy, ruff and
pytest lanes. It does not run the retired `sync_doc_subjects.py`, `check_doc_tree_completeness.py` or
`cc_context` projection workflow.

Important focused checks include:

- `check_phase_review_gate.py`: validates the fail-closed P1.2 owner gate. Passing it does not close
  the gate;
- `check_p1_2_proof_obligations.py`: validates the registered close-kernel structure and hashes. A
  pass is not a full-project soundness proof;
- `check_strong_status_write_allowlist.py`: deny-by-default inventory for strong-status/public-write
  sites, not a proof that unscanned code is harmless;
- `check_cc_memory_consistency.py`: runs only when cc_memory is in the selected change scope;
- `check_external_artifacts.py`: validates the artifact manifest and current presence/bytes.

Current frozen inputs include `canonical_rules.json` at 17,510 bytes / SHA256
`5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05`, `preprocess_plan.json`
at 1,383 bytes / SHA256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`,
and `candidate_placements.json` at 54,467,709 bytes / SHA256
`f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`. The 45,774,305-byte
`a914…`, 45,773,799-byte `adcc…`, 53,594,995-byte `d5e3…`, and 53,595,501-byte `78e2…`
candidate artifacts are a
superseded, hash-incompatible historical chain. Scripts must fail closed on any byte drift.

## Review snapshot packaging

`package_review_snapshot.py` is a review convenience, not certification authority. The current
implementation resolves the caller-supplied `treeish` to an immutable commit SHA once, then uses
that same resolved commit for provenance metadata, the manifest `treeish` field, and tree
materialization — so a mutable ref moving between those steps no longer opens a
manifest-vs-archive gap (pinned by the ref-move TOCTOU regression test in
`src/tests/test_package_review_snapshot.py`). Its default targeted
test list is not the full P1.2 or repository test suite. Package output must retain these
limitations in its manifest and release notes.

## IndustrialPlanner and viewer scripts

IndustrialPlanner builders, validators, viewer bundles and report builders emit consumer or
review derivatives. They may use familiar filenames inside their own output directories, but may
not write canonical certified paths or preserve proof-bearing labels without the central public
verdict.

## Vendor refresh and preprocess tools

Vendor refresh is mechanical ingestion. It does not automatically authorize canonical-rule or
frozen-artifact changes. Such changes require the normal owner, hash and campaign reset discipline.
Current preprocess/generation semantics give `box_sink` 3 physical inputs and 3 physical outputs,
and the mandatory core 14 inputs and 6 outputs. Generic-input finished goods are routed to provider
physical inputs. The provider-aware, instance-aware box lower bound is 0 for current demand 2, and
campaign tooling must carry and compare the full `generic_input_slots_by_operation` map from one
hash-bound plan snapshot.

## Spike, profile and phase3b generators

`*_poc.py`, `*_spike_*`, profiling scripts and most `build_phase3b_*` files are diagnostic or
future-scope tools. A green artifact test establishes only its declared contract. In particular,
`src/cuts`/Step 8 production master integration remains outside the current P1.2 certified path.

## Finding a script

```bash
ls scripts/ | grep <keyword>
rg -n "from scripts\.<name>|import scripts\.<name>" src scripts
```

Before using an old command from research logs, verify that the script still exists and check its
current `--help` plus the root `CLAUDE.md`/`PROJECT_LOCK.md` authority statements.
