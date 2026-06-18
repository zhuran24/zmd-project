# P1.2 V99 — close-kernel sealing

Date: 2026-06-17  
Anchor: `v99_p1_2_close_kernel_sealing`

## Purpose

P1.2 close is no longer treated as “keep looking until reviewers stop finding bugs.” V99 lands a small close kernel inside `scripts/check_p1_2_proof_obligations.py` so that the close proof has a machine-checked attack surface.

The kernel is not a theorem prover and does not certify geometry. It seals the authority surface around the current default `certified_exact` proof chain:

- source files that contain proof-bearing `CERTIFIED` / `INFEASIBLE` vocabulary in the configured scan roots must be registered;
- each registered sink is bound by `path`, `classification`, `obligation_id`, `terms`, `required_guard_tokens`, and `source_sha256`;
- source drift of a registered sink reopens the P1.2 close claim;
- a new unregistered proof-bearing sink fails the gate;
- guard-token removal fails the gate;
- the existing manual phase gate remains blocked until owner manual decision.

## Local reseal after F-CAM-R8-02 and no-close review

The local repository seal includes the follow-up F-CAM-R8-02 durable resume-sanitization fix and the 2026-06-18 no-close-kernel review follow-ups: public `ExactCampaign.mark_candidate_result()` cannot self-authorize proof-bearing strong-status freshness, the raw freshness sealer fails closed, verified strong producers are caller-bound to the `run_outer_search` controller path, the mutable freshness registry is not exposed as importable module state, and root entrypoint `main.py` is covered by the certified exact source digest. The original V99 package was generated before these local fixes; this repository keeps them and rebinds the close-kernel source hashes for `src/search/exact_campaign.py`, `src/search/outer_search.py`, and the checker manifest entry. The root close packet records the local merge in `P1_2_TECHNICAL_CLOSE_PACKET/10_local_merge_reseal.md`.

## Reviewer attack model

The close-kernel contract explicitly treats the “door guard” as an attack surface. The following attack categories are represented in `close_kernel_contract.attack_categories`:

1. `direct_writer_bypass`
2. `status_synonym_or_free_text_claim`
3. `stale_checkpoint_or_manifest_authority`
4. `path_symlink_or_shadow_authority`
5. `malformed_json_or_weak_typing`
6. `unsafe_env_or_config_semantics`
7. `parallel_resume_or_crash_partial_authority`
8. `gate_or_obligation_mutation`

## Trusted base and non-claims

The recursion stops at an explicit small TCB: Python runtime, current source tree, filesystem semantics, pytest/CI exit status, and human interpretation of the 2026-06-17 P1.2 boundary files.

This V99 close kernel does **not** claim:

- all software bugs are impossible;
- future P1.3B production master integration is safe;
- owner clean-review counting is automated inside the repo;
- Python, the OS, filesystem, CI, reviewers, or this checker are mathematically infallible.

## Commands

```bash
python3 scripts/check_p1_2_proof_obligations.py
python3 scripts/check_phase_review_gate.py
python3 -m pytest src/tests/test_p1_2_proof_obligations.py -q
```
