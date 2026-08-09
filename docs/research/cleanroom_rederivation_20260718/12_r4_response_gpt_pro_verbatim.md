## 1. Next certificate

The new upper ledger is

[
\boxed{U=(1188,22)}
]

which is strictly below ((1190,34)).

The certificate uses a new marked-terminal capacity argument, followed by an exact boundary-port packing observation. It remains an upper-bound certificate only. It does not establish attainability of ((1188,22)), provide a layout, or create a lower ledger.

### The marked terminals

Call an active terminal an **interior-side terminal** when its body cell is not a corner of its rectangular facility body.

A port-bearing side has at most two body-corner positions. Therefore a side with (a) active terminals necessarily contains at least

[
\max(0,a-2)
]

active interior-side terminals.

Applying this to all manufacturing instances gives 58 mandatory interior-side terminals. The 46 boundary-port outputs and all six protocol-core outputs must also be active, because those 52 available output slots jointly provide the exact 52 raw outputs. All 52 lie at non-corner body cells. Thus every layout contains a selectable set of

[
58+52=\boxed{110}
]

marked interior-side active terminals.

### Local access-cell lemma

For an access cell (z), let:

* (t(z)) be the number of active terminal incidences using (z);
* (m(z)) be the number of those incidences that are marked interior-side terminals.

Then

[
\boxed{t(z)+m(z)\le 4}.
]

The reason is geometric. Two facility bodies occupying perpendicular neighbors of (z) overlap in their diagonal quadrant unless at least one of the two terminals is at the appropriate body corner. A corner terminal can clear at most one such diagonal quadrant; an interior-side terminal clears none.

With four terminal incidences around (z), four diagonal quadrants must be cleared, so all four terminals must be body-corner terminals and (m=0). With three incidences, two quadrants must be cleared, so at most one terminal can be marked. The cases (t\le2) satisfy the inequality directly.

This improves the usual four-terminal-per-access-cell count by charging marked terminals a second time.

### Two membrane bounds

Let the empty rectangle have normalized dimensions (w\le h), and put (S=w+h).

The inherited ordinary membrane calculation, independently reconstructed by the checker, has full-contact excess 63 and endpoint increment at most 3. It gives

[
K_{\rm in}\le S+48,
]

where (K_{\rm in}) is the number of all active terminal incidences whose access cell lies inside the rectangle.

For marked terminals, every marked side class has (2r\le s), where (r) is the number of marks on a port-bearing side of length (s). The maximum (r) is 3, and the maximum relevant side length is 9. Consequently, whenever (w\ge9), full contacts expose marks at density at most one-half and the eight possible endpoint-crossing contacts add at most (8\cdot3) in doubled units. Hence

[
J_{\rm in}\le S+12,
]

where (J_{\rm in}) counts marked terminals accessing the rectangle.

If (N) is the number of distinct access cells outside the rectangle, summing (t(z)+m(z)\le4) yields

[
\begin{aligned}
4N
&\ge (628-K_{\rm in})+(110-J_{\rm in})\
&\ge (628-(S+48))+(110-(S+12)).
\end{aligned}
]

For all dimensions relevant near the previous upper bound,

[
\boxed{N\ge\left\lceil\frac{678-2S}{4}\right\rceil}.
]

Required bodies occupy 3,544 cells. The checked local halo certificate gives at least nine poles, adding 36 cells, so at least 3,580 body cells must lie outside the empty rectangle. Therefore

[
\boxed{wh+N\le1320}
]

is necessary.

This immediately removes both the (34\times35) candidate and the only area-1189 dimension:

[
34\cdot35+\left\lceil\frac{678-2(69)}4\right\rceil
=1190+135=1325>1320,
]

[
29\cdot41+\left\lceil\frac{678-2(70)}4\right\rceil
=1189+135=1324>1320.
]

The marked-terminal scan leaves only the lower-secondary-objective area-1190 case (17\times70).

### Eliminating the full-span case

Each boundary-port body occupies a length-3 interval on either the left boundary or the bottom boundary. At most

[
\left\lfloor70/3\right\rfloor=23
]

such bodies fit on either supported boundary.

There are exactly 46 required boundary ports, so every feasible layout must use exactly 23 left-boundary modes and 23 bottom-boundary modes. Each supported boundary is consequently occupied in 69 of its 70 cells.

Any admissible (17\times70) empty rectangle spans either every row or every column. It would contain at least six cells of the bottom boundary or the left boundary, respectively. Since only one cell on that boundary is not occupied by a boundary-port body, the rectangle is impossible.

The remaining relaxation scan has lexicographic maximum (22\times54):

[
22\cdot54=1188,\qquad S=76,\qquad
N\ge\left\lceil\frac{526}{4}\right\rceil=132,
]

and (1188+132=1320). Thus the relaxation permits ((1188,22)), so that is the certified upper ledger rather than an attainability claim.

The checker is 160 physical lines, uses only the Python standard library, byte-locks the supplied instance, rechecks the 840 halo inequalities, reconstructs the old bound, and performs the final dimension scan:

```bash
python3 r4_next_certificate.py problem_instance.json
```

Its terminal result is:

```text
old relaxation (1190, 34) [(34, 35)]
marked-terminal step (1190, 17) [(17, 70)]
new certificate (1188, 22) [(22, 54)]
```

[Download the 160-line standalone checker](sandbox:/mnt/data/r4_next_certificate.py)

[Download the complete certificate note](sandbox:/mnt/data/r4_next_certificate.md)

## 2. Most promising construction unblocking move

The best single move is a **core-guided minimum-repair of the 17-component partition, targeted at x67-c5**, while retaining the protected (6\times7) rectangle and the current pole placement.

Turn every current component-membership pin into an assumption literal or soft equality. Reinstantiate the 7,168 sound cuts, guarding any cut whose validity depends on a particular pin. Then solve for an exact count-closure manifest that feeds x67-c5 while minimizing Hamming distance from the current 17-component partition. Equivalently, extract a minimum correction set over the partition pins and mutate only that set.

This is the earliest structural layer capable of escaping the demonstrated common bottleneck. Both complete manifests under the present partition collapse to the same c3 target ((12,4,3)), and the sound-cut relaxation for that conjunction is infeasible. More c3 candidates, candidate no-goods, or downstream assembly attempts cannot repair it. Moving directly to unrelated c0, c1, or c2 campaigns would discard substantially more of the x67 work, while merely moving poles would leave the exact-closure funnel into c3 untouched.

The acceptance gate for the repair should be narrow: a new exact manifest outside c3, preferably x67-c5, that is already feasible in the guarded sound-cut model. Only after that gate passes should assembly and routing resume.
