# 07. Reviewer attack report

This review attacked the close-kernel and certified proof chain in the sandbox using static source inspection plus the Step 6 mutation probes. No owner governance decision or external human signature is claimed here.

| finding_id | attack_class | p1_2_in_scope | proof_chain_entry | can_produce_false_CERTIFIED | can_produce_proof_bearing_false_INFEASIBLE | affected_files | reproduction | expected_fix | status |
|---|---|---|---|---|---|---|---|---|---|
| F-CK-M8 | gate mutation | yes | yes | yes | yes | `scripts/check_p1_2_proof_obligations.py`, `src/tests/test_p1_2_proof_obligations.py`, `data/proof_obligations/p1_2_proof_obligations.json` | Remove `_check_close_kernel_contract(manifest)` from checker main. Incoming tree did not kill this mutation. | Add checker self-binding AST guard and regression test; update manifest required test and checker source hash. | fixed and killed by M8 |
| A1 | direct writer bypass | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. Delivery/export sinks are registered and hash/guard bound; M4/M5 drift red. |
| A2 | status synonym bypass | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path in current close-kernel tokens; public exact status normalizers and release tests reject fake certified language. |
| A3 | stale authority | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. delivery_manifest and certified_surface guards/tests bind disk/current campaign authority. |
| A4 | symlink / shadow authority | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. Required tests include v96/v97 symlink and shadow-campaign rejections. |
| A5 | malformed JSON / weak typing | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. Strict JSON duplicate-key/NaN and bool-as-int regressions are anchored. |
| A6 | env/config semantics | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. master-domain and EXACT_* unsafe env blockers are anchored. |
| A7 | parallel/resume partial authority | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | No unresolved path. frontier and parallel identity/failure discard guards are sealed. |
| A8 | gate mutation | yes | reviewed | no unresolved | no unresolved | close-kernel surface | see Step 6 matrix | none open | Initial bypass fixed as F-CK-M8; final M8 fails in proof gate. |

Conclusion: after fixing F-CK-M8, no unresolved in-scope bypass was found. The report does not assert owner clean-review count or P1.3B entry.
