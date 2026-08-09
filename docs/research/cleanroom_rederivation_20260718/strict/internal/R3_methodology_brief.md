# Methodology Brief — Solution Engineering Principles

This brief accompanies the benchmark specification (`problem.md`, `problem_instance.json`, `instance_schema.json`). It transfers the working methodology distilled from an extended engineering effort on problems of this class. It deliberately contains **no** concrete model, encoding, constraint-ownership decision, experimental result, or failure narrative from that effort — only the meta-level principles. You are expected to apply, adapt, or reject these principles as you see fit when designing your own attack.

## M1. Layered decomposition and the rule-ownership criterion

When a system is decomposed into layers (e.g., a coarse master problem and refined subproblems), every rule of the specification must have an explicit owner, and the assignment is a first-class design decision — not an accident of implementation order.

A rule belongs in the **earliest (most global) layer where it admits a workable representation**, judged by a three-legged test:

1. **Encoding-size arithmetic** — write down the variable/constraint counts of the candidate representation before building anything. If the arithmetic says millions where the layer's budget is thousands, the representation (not necessarily the rule) is disqualified.
2. **Propagation strength** — a representation that the layer's solver cannot propagate (one that sits inert until a full assignment exists) buys nothing; prefer forms that prune early.
3. **Machinery compatibility** — the representation must behave well with the layer's solver machinery in practice (presolve, memory profile, symmetry handling), which is an empirical property, not a syntactic one.

A rule may be lifted **partially**: a conservative *necessary-condition* version of it can live in an upper layer while the exact rule stays below. This is often the highest-value move available (see M3).

Cut interfaces between layers at **thin waists**: places where the information crossing the boundary is small and canonical (a candidate record with a hash, not a solver state).

## M2. The feedback-language principle and the treadmill alarm

When a lower layer rejects a candidate from an upper layer, the *language* of the rejection determines the system's convergence, and is more important than the speed of either layer.

- A rejection must carry a **checkable, generalizing explanation** — a reason that excludes a *family* of future candidates, not just the one candidate seen. A single-point nogood ("not this exact candidate") is the weakest legal currency and, used alone, treads water on large spaces.
- **Treadmill alarm**: if iteration telemetry shows rejection counts staying flat while candidates keep coming — the same *kind* of conflict recurring with different coordinates — treat this as an alarm, not as slow progress. It almost always means a **rule is being transported as exceptions**: some regularity the lower layer knows is being re-derived one candidate at a time. The correct response is to identify that regularity, prove a sound generalization of it, and lift it into the upper layer (M3). Adding compute to a treadmill does not fix it.
- Positive-only obstacle explanations ("these placed objects make it impossible") are **not automatically sound** in problems where adding or moving something can repair feasibility; the soundness of every rejection form must be argued, not assumed.

## M3. The lift loop and necessary-condition certificates

The core engineering cycle is the **lift loop**: observe a treadmill or a recurring rejection family → extract the underlying rule → prove a sound (conservative, necessary-condition) form of it at the upper layer → re-run → repeat.

Two properties make lifted rules more than a speedup:

- **Certificate-bearing**: if the upper layer's model is a *sound relaxation* of the true problem (every true solution satisfies it), then that model's INFEASIBLE / bound is a **legal impossibility or bound certificate** for the true problem, by contraposition. Lifting thus converts search-guidance into provable statements.
- **Direction of error is everything**: the upper-layer projection of any rule must *never* be stricter than the true rule. A single accidental strengthening silently voids every certificate the layer produces, and such errors are plausible-looking (they usually make the model "cleaner"). Guard this direction explicitly: adversarial tests whose expected outcome differs under the strengthened vs. true rule, mutation canaries, and independent re-derivation of the projection from the specification.

## M4. The funnel: never pay for what a cheaper stage can kill

Order all validation effort as a funnel, and never skip stages downward:

1. **Paper proof** of the idea's soundness (does the claimed certificate logic actually hold?);
2. **Size arithmetic** (M1 leg 1) — kill by counting before coding;
3. **Premise data checks** — verify on the actual instance data that the assumptions the idea rests on are true (an idea can be sound in general and vacuous on this instance);
4. **Build-only audit** — construct the model, do not solve; check counts, memory, and structural invariants against prediction;
5. **Cheap probes with telemetry** — short bounded runs whose purpose is to observe *how* the solver engages (does it propagate? does it search? conflict rates), not to get an answer;
6. **Bounded real solves** — only for survivors of 1–5.

Telemetry must distinguish "the solver never meaningfully searched" from "it searched and failed" — these have opposite implications, and conflating them produces false structural conclusions in both directions.

## M5. The proof trust boundary

- A solver's status output (OPTIMAL / INFEASIBLE / UNKNOWN) is **not evidence** by itself. UNKNOWN proves nothing at all — neither hardness nor structure. OPTIMAL/INFEASIBLE become evidence only when backed by something independently checkable.
- Verification layers, in increasing strength: independent recomputation of the claimed facts; **heterogeneous double implementation** (a second, separately written checker sharing no code with the producer — shared code shares bugs, and a bug in a shared helper poisons every downstream conclusion simultaneously); machine-checkable proof artifacts verified by an external checker.
- **Universal negatives require complete gates**: a claim of the form "no X exists" or "all X fail" is only as strong as the completeness of the enumeration/model behind it — an unproven completeness assumption converts the claim to folklore.
- **Semantic changes void inherited conclusions**: when any definition, input artifact, or projection semantics changes, every conclusion derived under the old semantics reverts to *unproven* until re-established. Re-run or retract; never let conclusions silently survive the change that undermined them.

## M6. Honest-boundary reporting

Every reported result carries its own scope: what was proved, under which assumptions, by which checker, and — explicitly — what it does *not* establish. Negative results (a probe that died at the size-arithmetic stage, a lift that turned out unsound) are recorded with the same care as positive ones; an unrecorded dead end will be re-entered. When a result's strength is between "nothing" and "certified," name the intermediate level precisely rather than rounding in either direction.

---

*End of brief. The benchmark specification remains the sole authority on the problem's rules; nothing here adds to or weakens it.*
