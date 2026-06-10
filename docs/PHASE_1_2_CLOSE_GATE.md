# Phase 1.2 close gate

Current gate state: BLOCKED by default.

Phase 1.2 spike close is deliberately not treated as complete yet.  V50 changed
the gate model: the **three clean full reviews** rule remains a project-owner
standard, but the repository no longer tries to prove or count those reviews
from receipts, Markdown reports, package metadata, source-tree manifests, or
package-internal Git authority.

The previous automatic counter became its own attack surface during V47-V50.
Those rounds found receipt/state-machine false-ready paths rather than new
cut-family algorithmic bugs.  The safer model is now:

- the owner keeps the clean-review count outside the repo;
- review receipts are optional/informational audit records;
- the repo stays fail-closed until an explicit owner manual decision opens
  P1.3B;
- `next_phase_entry.allowed` must remain false without that decision.

## Current review anchor

After V57-V84, lifecycle-evidence consolidation, certified-surface verifier
centralization, authority-boundary hardening, replayable terminal frontier
evidence sealing, project-bound terminal-evidence hardening, direct
manifest-writer disk-authority hardening, canonical certified-manifest
publication hardening, terminal candidate-domain axis sealing, deny-unknown
certified-surface hardening, partial-precheck/release-claim sealing, and
oriented-domain/persisted-cut-replay sealing, the current review anchor is:

```text
v84_layout_optimality_and_artifact_boundary_sealing
```

Those rounds did not reopen the old automatic receipt/counter gate.  They found
a real certified solver safety surface: certified lifecycle evidence must stay
faithful from exact-safe cut replay through master-domain construction, outer
frontier termination, and certified export surfaces.  V73 made the public
CERTIFIED decision a single central verifier shared by the inspector, delivery
manifest path, and B5A anchor publication.  V74 hardened that verifier so disk
artifacts, recomputed exact hashes, strict JSON, and regular-file boundaries are
authoritative over caller memory payloads.  V75 then closes the remaining
terminal-proof seam beneath the verifier: full-frontier exhaustion is now a
replayable, digest-sealed candidate-domain projection with an authoritative
safe-area bound, not just a stop-reason string plus an incumbent.  V76 then
confirmed the central public-verifier architecture and tightened the
pre-publication helper path: in-memory terminal evidence must replay against the
current project grid and authoritative safe-area bound before it may seed a
`best_certified_result` or delivery-manifest payload.  V77 leaves the central
public architecture intact and closes the direct manifest-writer seam: any
manifest payload that carries `best_certified_result` must now prove that the
caller-supplied campaign state matches the regular in-project disk checkpoint
selected by `campaign_path`.  V78 closes the remaining writer-publication seam:
`best_certified_result` can only be persisted by the canonical export writer to
the regular in-project `data/solutions/certified_delivery_manifest.json`; raw
writer calls and side output paths are not certified publication authority.
V79 seals the remaining candidate-domain slicing axes inside the V75 terminal
evidence contract: an exhausted `max_aspect_ratio`-sliced domain or an
above-admissibility `min_side` (>6) domain is rejected exactly like a
`start_area` slice, and the delivery-manifest deep validation fails closed on
non-instance-shaped terminal placement solutions instead of skipping the
blueprint reverse-lookup.  V80 closes the residual below that seal: the
canonical project schema now carries the empty-rectangle admissibility floor,
terminal-frontier evidence schema v2 rejects unknown `candidate_generation`
keys and sub-admissible terminal final results, and `certified_exact` env
handling is a closed allowlist where future/unclassified `EXACT_*` names fail
closed.  V81 (the first independent external review after the V80 flip) seals
two further seams: a mandatory-rectangle precheck group interrupted by the time
budget (`partial_due_to_time_budget`) is no longer consumed as a complete
all-anchors-infeasible candidate proof, and the single-base delivery release
path fails closed on a run summary that self-claims
`exact_full_scale_certified` CERTIFIED instead of propagating it into
release/pointer artifacts.  V82 seals two further soundness seams found by the
second independent review: the candidate domain is now fully oriented (the old
`h <= w` canonicalization let full-frontier proofs cover half the real domain
while master feasibility is orientation-sensitive; the domain authority is
bumped to `outer_search_static_area_bound_oriented_v2`), and persisted
`exact_safe_cuts` are telemetry only — `certified_exact` never replays
checkpoint/IPC cut payloads into the master, because shape-level validation
cannot rebuild the family-specific proof obligation.  V83 (third overnight
independent review) seals three further seams: terminal certified final
results now require project-bound geometric evidence (mandatory coverage,
pose reverse-lookup, occupancy, and a real empty-rectangle witness scan, with
the `ghost_pick` marker excluded from occupancy); whole-layout
binding/routing nogoods keep the LBBD loop running instead of escalating to
candidate INFEASIBLE; and the certified `mandatory_exact_instances` loader is
deny-unknown instead of silently filtering malformed records.  V84 (fourth
overnight independent review) seals three adversarial deepenings of that
geometric re-verification: the terminal witness must be the layout's lex-best
empty rectangle, not merely an existing one (scoped to projects with a
non-empty mandatory set); exact artifact hashing rejects symlinked and
non-regular files; and unknown extra placement instances fail closed instead
of polluting the occupancy witness.  The
obligations remain split into four compartments:

- `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS` for strict payloads, condition/domain
  replay, all-or-nothing member resolution, one-to-one master literal encoding,
  and apply-before-register atomicity;
- `PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS` for the full unfiltered
  master-domain and canonical power-witness representation contract, including
  unsafe env fail-closed behavior before session/precheck/project-load side
  effects;
- `PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE` for strict full-frontier exhaustion
  evidence, including replayable candidate generation, status digests, safe-area-bound authority, and canonical min-side admissibility, rather than
  candidate-level or best-effort incumbents;
- `PO-CERTIFIED-EXPORT-SURFACE` for `final_result`, `final_solution`, delivery
  manifest, inspector/report, and wrapper export surfaces.

See `docs/research/p1_2_v56_certified_cut_replay_consolidation.md`,
`docs/research/p1_2_v64_power_witness_representation_env_guard.md`,
`docs/research/p1_2_v66_certified_lifecycle_evidence_consolidation.md`,
`docs/research/p1_2_v73_certified_surface_verifier_consolidation.md`,
`docs/research/p1_2_v74_certified_surface_authority_hardening.md`,
`docs/research/p1_2_v75_terminal_frontier_evidence_sealing.md`,
`docs/research/p1_2_v76_project_bound_terminal_evidence.md`,
`docs/research/p1_2_v77_delivery_manifest_writer_authority.md`,
`docs/research/p1_2_v78_certified_manifest_writer_canonical_surface.md`,
`docs/research/p1_2_v79_terminal_domain_axis_sealing.md`,
`docs/research/p1_2_v80_deny_unknown_certified_surface.md`,
`docs/research/p1_2_v81_partial_precheck_and_release_claim_sealing.md`,
`docs/research/p1_2_v82_oriented_domain_and_cut_replay_sealing.md`,
`docs/research/p1_2_v83_geometry_witness_nogood_scope_and_loader_sealing.md`, and
`docs/research/p1_2_v84_layout_optimality_and_artifact_boundary_sealing.md`.

Daily consistency check:

```bash
python scripts/check_phase_review_gate.py
```

Entry check for P1.3B:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

At the current baseline this command is expected to fail because the owner has
not manually opened P1.3B.  That failure is correct: the script is no longer a
3-clean counter, and it cannot prove owner review judgment.

The gate also keeps `src/cuts/lifecycle.py::step_8_apply_to_master` fail-closed
while P1.3B is not manually allowed.  P1.3B master integration must not land
while this close gate is blocked.
