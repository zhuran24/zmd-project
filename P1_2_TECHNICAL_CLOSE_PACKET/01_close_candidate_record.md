# 01. P1.2 close candidate record

## 冻结对象

- final candidate directory: `zmd_pj/`
- review anchor: `v99_p1_2_close_kernel_sealing`
- proof obligation gate: `scripts/check_p1_2_proof_obligations.py`
- phase gate: `scripts/check_phase_review_gate.py`
- phase gate status: `blocked_manual_review_count`
- phase gate next allowed: `False`
- date_utc: `2026-06-17T12:04:02Z`
- python: `Python 3.13.5`

## Incoming artifacts

| artifact | sha256 |
|---|---|
| `/mnt/data/zmd_pj_20260617_1.7z` | `ecbe35b88a3dec1f476ea0a5b1c8956f0c49d2488ca221b287f9b81042c007a3` |
| `/mnt/data/zmd_py313_linux_x86_64.zip` | `84f2bdf40edc4c7f5d6bb947e4fbb5f3ffd8c244c839095236ad1548ad0dee54` |
| `/mnt/data/p1.2闭合证明工作流程.md` | `2d42896911f3e61e9322a663b842bafd86fee3bdfb9e5826c5148f02a2cea7a0` |

## Candidate modification during close proof

M8 negative control initially survived against the incoming tree: removing the call to `_check_close_kernel_contract(manifest)` from `scripts/check_p1_2_proof_obligations.py` left the gate/tests green. The final candidate therefore adds a checker self-binding guard and a regression test, and updates the proof-obligation manifest source hash for the checker.

Changed source/control files:

- `scripts/check_p1_2_proof_obligations.py`
- `src/tests/test_p1_2_proof_obligations.py`
- `data/proof_obligations/p1_2_proof_obligations.json`

## Delivered patch artifact

- patch bundle: `zmd_p1_2_close_kernel_self_binding_patch_20260617.zip`
- patch bundle SHA256: `2543750eab9012a6435ad88d3614aa256c9925fe545d6caa0723fad54df9bbd4`

## Freeze rule

This packet proves only the final candidate generated from this directory. Any later change to certified surface, delivery manifest, exact campaign, frontier, outer search, benders loop, proof obligation manifest, scope/phase gate, or close-kernel checker reopens the claim.

Final archive SHA256 is recorded outside the archive in the delivered artifact hash file, because embedding an archive hash inside the archive would be self-referential.
