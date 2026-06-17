# 08. Fresh replay logs

Replay source: clean copy at `/mnt/data/fresh_replay_zmd/zmd_pj` made from the final candidate tree.

Python: `Python 3.13.5`

## Commands

```bash
python3 scripts/check_p1_2_proof_obligations.py
python3 scripts/check_phase_review_gate.py
python3 -m pytest --randomly-seed=0 src/tests/test_p1_2_proof_obligations.py -q
python3 -m pytest --randomly-seed=0 src/tests/test_phase_review_gate.py -q
python3 -m pytest --randomly-seed=0 src/tests/test_delivery_manifest.py -q
python3 -m pytest --randomly-seed=0 src/tests/test_exact_campaign_state_soundness.py -q
```

## Results

```text
$ python3 scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 9 obligations anchored; 50 proof-bearing sink files sealed
exit=0

$ python3 scripts/check_phase_review_gate.py
phase_1_2_spike_close: status=blocked_manual_review_count, anchor=v99_p1_2_close_kernel_sealing, next_allowed=False, counting_authority=owner_manual_count_outside_repo
exit=0

$ python3 -m pytest --randomly-seed=0 src/tests/test_p1_2_proof_obligations.py -q
..........                                                               [100%]
10 passed in 10.76s
exit=0

$ python3 -m pytest --randomly-seed=0 src/tests/test_phase_review_gate.py -q
...........                                                              [100%]
11 passed in 8.50s
exit=0

$ python3 -m pytest --randomly-seed=0 src/tests/test_delivery_manifest.py -q
.......................                                                  [100%]
23 passed in 10.32s
exit=0

$ python3 -m pytest --randomly-seed=0 src/tests/test_exact_campaign_state_soundness.py -q
........                                                                 [100%]
8 passed in 10.05s
exit=0
```

## Full pytest

Full repository pytest was not completed in this sandbox replay. The technical close claim is intentionally bounded to the P1.2 close-kernel, phase gate, delivery/export surface, and exact campaign state soundness suites listed above. The packet does not claim full-project bug absence.
