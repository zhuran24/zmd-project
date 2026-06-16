# F9 Morphological Erosion Caution

Morphological erosion is useful, but it is not automatically a density theorem.

## Safe uses

- Compute legal anchor domain for "facility entirely inside region W".
- Prove a corridor/sliver cannot contain a given rectangle shape.
- Feed F6 shape packing / Hall-style upper bounds.
- Help an `AreaCapacityOverflow` oracle find a tighter witness window.

## Unsafe leap

Do not say:

```text
capacity(W, 3x3) = number_of_eroded_anchors(W)
```

as if that were the true number of packable facilities.

The number of legal anchors is usually only an upper bound. It ignores overlap between facilities. Also, F9's current area-based evaluator counts `pose_cells ∩ W`, so a pose anchored outside W can still contribute area inside W. Erosion over anchors inside W is not the same semantics.

## Required rule

If morphology is used to produce a cut, the cert must state exactly which semantic is proven:

- all-in-window placement capacity
- overlap-window area capacity
- anchor-domain empty proof
- shape packing / matching capacity

The validator must recompute the same semantic independently.
