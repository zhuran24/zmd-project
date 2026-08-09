# Persistent big-bay recovery status

Scope: local research geometry for c0/c1/c2 only. These files do not establish a
global layout or commodity-routing result.

## Positive result used downstream

- `all_residual_attempts/c0/t10-5-4_x18_dyp0_s240.json`: `OPTIMAL` in
  41.699683164 seconds. Target `(10,5,4)`, internal pole column moved from 17
  to 18, 19 selected facilities, 311 body cells, and all 51 residual cells
  backbone-connected.
- `periodic_big_bay_selection.json`: translates the selected canonical local
  keys to c1 and c2 while simultaneously moving pole columns 17/29/41 to
  18/30/42. The combined result has 35 poles, aggregate target `(30,15,12)`,
  57 selected facilities, 933 body cells, and 138 selected weak active fronts.
- `independent_periodic_big_bay_replay.json`: pure-stdlib `PASS`. It rebuilds
  canonical candidate domains and strict body/port modes, proves all three
  1,858-key normalized local domain sets equal, and rechecks power,
  non-overlap, exact active-front counts, and complete residual BFS.

## Negative and timeout records

- Target `(10,6,4)` under the stronger all-residual-connected model was exactly
  `INFEASIBLE` for `x=18` and `dy=0,-1,+1,-2,+2`. This is local to those pole
  phases and the stronger condition.
- Target `(11,5,4)` under the optional-terminal model was `UNKNOWN` after full
  90-second runs for `x=18` and `dy=0,-1,+1`.
- Its `dy=-2,+2` checkpoints were stopped early at 38.898 and 18.603 seconds.
  They are retained for crash history only and must not be treated as full
  90-second attempts or infeasibility results.

All persistent inputs, scripts, checkpoints, selections, and replay reports are
under this directory; `/tmp` is not required to reproduce or audit this state.
