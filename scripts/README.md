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

The producer/supervisor/publication boundary lives in Python source. No current launcher invokes
`ExactCampaign.supervisor_seal()`; `main.py` and campaign wrappers stop at `CANDIDATE_PROPOSED`.
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

The current `candidate_placements.json` is present at the expected 45,774,305 bytes, SHA256
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`. The superseded
45,773,799-byte / SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` artifact predates the
boundary `(0,0)` corner-pose fix and is hash-incompatible. Scripts must still fail closed on byte
drift.

## Review snapshot packaging

`package_review_snapshot.py` is a review convenience, not certification authority. The current
implementation resolves a commit for metadata but still materializes the caller-supplied `treeish`;
there is therefore an open immutable-materialization gap if a mutable ref moves between those
steps. Its default targeted test list is not the full P1.2 or repository test suite. Package output
must retain these limitations in its manifest and release notes.

## IndustrialPlanner and viewer scripts

IndustrialPlanner builders, validators, viewer bundles and report builders emit consumer or
review derivatives. They may use familiar filenames inside their own output directories, but may
not write canonical certified paths or preserve proof-bearing labels without the central public
verdict.

## Vendor refresh and preprocess tools

Vendor refresh is mechanical ingestion. It does not automatically authorize canonical-rule or
frozen-artifact changes. Such changes require the normal owner, hash and campaign reset discipline.

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
