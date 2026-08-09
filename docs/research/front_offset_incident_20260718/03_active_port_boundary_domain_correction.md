# Active-Port Boundary-Domain Correction

**Status:** implemented and resealed on 2026-07-18

**Supersedes:** the generation-time wall-starvation conclusion in the earlier incident/rules-audit snapshots

## Correct Rule

A candidate records every physical port's outside-adjacent routing access cell. A recorded access cell may be outside the grid when that physical port is inactive.

Only a port selected by the operation or generic binding must have an in-grid, body-free, direction-compatible access cell. Every canonical manufacturing operation requires at least one input and one output, and each class occupies an entire opposite side, so a manufacturing pose with either required side wholly out of grid remains safely prunable. Core and box generic ports may be `__unused__`; their active subset is unknown during generation, so their poses require only an in-grid body.

This follows the v2.2 ownership test: the exact rule depends on a lower-layer decision. No demand-specific shortcut was added to the generator; the frozen candidate domain remains independent of current operation counts.

## Change and Reseal

`src/placement/placement_generator.py` now enumerates the complete body-in-grid domain for the protocol core and protocol storage boxes while retaining the sound one-input/one-output side filter for manufacturing facilities. The serialized shape and deterministic order are unchanged.

| Artifact | Poses | Bytes | SHA256 |
| --- | ---: | ---: | --- |
| current | 82,829 | 54,467,709 | `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3` |
| superseded activation-pruned pool | 81,797 | 53,595,501 | `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef` |

The correction adds 1,032 poses: 488 core poses and 544 box poses. Frozen artifact manifests, preflight/runtime pins, and the P1.2/V99 source-hash closure were resealed together. Regression coverage proves both directions: core/box edge poses can leave out-of-grid ports unused, while a genuinely required out-of-grid port is rejected.

## Certified Blueprint Closure

The terminal fixed-witness success verdict now carries its normalized `port_specs` in `details`, bound by the existing `port_specs_digest`. Before minting `CERTIFIED`, the isolated capsule validates the carrier schema, count, digest, duplicate freedom, and instance ownership; malformed carriers demote the candidate to `UNPROVEN`. After project-bound terminal seal/replay validation, the certified publisher extracts that carrier and passes it explicitly to the serializer. The serializer rejects missing carriers, unknown or duplicate endpoints, active out-of-grid cells, endpoints absent from the selected pose, and concrete-commodity relabeling.

Consequently, an edge pose may retain inactive physical slots at `-1` or `70` in the candidate pool without leaking them into public `active_ports`. Only selected, in-grid binding ports are exported. Delivery-manifest currentness reconstructs the blueprint from the same digest-bound carrier, so validation cannot silently fall back to all pose slots.
