# 02. P1.2 technical close claim

## Claimed

Under the frozen final candidate, the current default `certified_exact` proof chain, the P1.2 2026-06-17 boundary, and the close-kernel TCB below:

1. every current proof-bearing source sink found by the close-kernel scan is registered;
2. every registered sink is bound to an `obligation_id`;
3. every registered sink is bound to required guard tokens;
4. every registered sink is bound to `source_sha256`;
5. adding an unregistered strong-status source path fails the proof-obligation gate;
6. mutating a registered sink without updating the close contract reopens the claim by hash drift;
7. weakening phase gate authority or owner/manual boundaries fails closed;
8. removing the proof-obligation checker call to the close-kernel now fails the checker self-binding gate;
9. no unregistered, unguarded, un-hashed, non-obligation proof-bearing `false-CERTIFIED` or proof-bearing `false-INFEASIBLE` path remains on the current default certified proof chain.

## Not claimed

This packet does not claim:

1. that all software bugs are impossible;
2. that future P1.3B production integration is safe;
3. that `step_8_apply_to_master` production integration is complete;
4. that reviewer, Python, OS, filesystem, or pytest are mathematically infallible;
5. that owner clean-review count is satisfied;
6. that P1.3B is opened automatically.

## Trusted computing base

The explicit close-kernel TCB is:

- Python runtime executing scripts/check_p1_2_proof_obligations.py
- current Git/source tree supplied to the checker
- filesystem path and regular-file semantics used by the checker
- pytest/CI exit status reporting faithfully when invoked
- human reviewer interpretation of the 2026-06-17 P1.2 boundary files

Additional packet-local TCB: the sandbox ran Python 3.13.5 and offline dependency bundle `zmd_py313_linux_x86_64.zip` with SHA256 listed in the candidate record.

## Reopen conditions

The claim reopens if any of the following changes occur:

- any registered sink source hash drifts;
- a new proof-bearing source sink appears under close-kernel scan roots;
- a registered sink loses its declared proof-bearing terms or guard tokens;
- proof-obligation checker, manifest, phase gate, certified surface, delivery manifest, exact campaign, frontier, outer search, parallel scheduler, benders loop, or release surface is weakened;
- phase gate `next_allowed` becomes true without explicit owner manual decision;
- required doc markers for owner manual authority disappear;
- dependency/runtime semantics change in a way that affects parsing, filesystem, subprocess, or pytest results.
