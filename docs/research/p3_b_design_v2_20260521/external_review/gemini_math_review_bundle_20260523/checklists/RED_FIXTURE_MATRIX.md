# Red Fixture Matrix for Gemini-Flagged Issues

| Fixture | Purpose | Expected owner |
|---|---|---|
| F5-timeout-last-verified-core | QX/deletion minimizer timeout must stay sound | F5 |
| F5-132-group-anonymous | Slot/index permutations must hit same cut | F5 generic multiset |
| F5-cardinality-unsound-routing | Routing failure must not auto-lift to cardinality | F5/F9 boundary |
| F9-reject-routing-overflow | F9 only accepts area capacity overflow | F9 |
| F9-any-overlap-overcount | Historical FP: any overlap counts whole facility | F9 |
| F9-origin-in-window | Historical FP: origin in W counts whole facility | F9 |
| F9-all-in-window-FN | Historical FN: edge partials ignored | F9 |
| F2-narrow-corridor-capacity | BFS connected but capacity < demand | F2 |
| F4-disconnected-zero-capacity | No path at all, F4 fires before F2 | F4 |
| CP-SAT-no-lazy | Step 8 uses normal constraints, not AddLazyConstraint | integration |
| DarkMatter-empty-families | INFEASIBLE but all families return empty must log JSONL | telemetry |
