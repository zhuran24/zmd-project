# P1.2 V61 master-domain and candidate-frontier contract

V61 is a reset-grade sibling of the V57-V60 certified cut replay/domain-contract family.  It does not reopen the retired V47-V50 receipt/counter authority.  The live issue is that terminal certified evidence must describe the actual constructed certified lifecycle: the master domain that was built, the candidate frontier that was explored, and the strictness of the campaign evidence that is later resumed or exported.

The V61 review found three reachable reset-grade surfaces:

- `EXACT_USE_POSE_BOOL_MASTER=1` could enter `certified_exact` through a sibling master representation that does not construct the full ghost-anchor domain while the persisted contract still looked full-domain.
- `EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE` could tighten the power-pole slot family and make a smaller actual master domain look like full-domain certified evidence.
- `EXACT_OUTER_SKIP_UNKNOWN=1` could turn a candidate-subset or best-effort outer campaign into a `CERTIFIED` final result, especially because production wrappers had defaulted that env on.

The applied V61 contract is:

- certified master-domain-changing env/debug overrides must fail closed before `ExactSearchSession` construction;
- certified outer search must not skip `UNKNOWN` candidates unless a future partition/coverage proof exists and is machine-gated;
- `ExactCampaign` resume and final-result inheritance must require strict `declare_mode`;
- delivery manifests must reject non-strict final-result evidence;
- proof obligations and regression tests must anchor these behaviors.

The phase gate remains owner-manual and fail-closed.  V61 changes the review anchor for future review packages, not the P1.3B entry authority.
