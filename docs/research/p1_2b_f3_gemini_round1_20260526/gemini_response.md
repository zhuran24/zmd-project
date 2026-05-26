### F3 Port Exposure Generator Review & Cross-Check

**Overall Verdict:** **PASS (with completeness warnings)**. The mathematical soundness strictly holds under the v1.0 spec assumption (all ports active), and the literal asymmetry strictly follows state machine rules without over-cutting. Implementation deviations (source derivation, `witness=None`) are mathematically safe and structurally equivalent, though fail-closed mechanisms risk silent completeness degradation.

---

### Detailed Findings

#### 1. Mathematical Soundness & Witness Deferral (Points 1, 4)
*   **Severity:** **PASS (Sound)**
*   **Analysis:** 
    *   *Front Cell Blocking:* The mathematical implication `cell_owner 占 front ⇒ INFEASIBLE` is strictly sound. By Endfield 2D grid rules, a port requires an adjacent orthogonally-aligned free cell to route a belt. `cell_owner` represents collision footprints. The intersection of a routing path and a collision footprint yields an infeasible state. Skipping ghost/exterior/out-of-bounds does not threaten soundness; it merely delegates those constraints to their respective Phase 1.1 unaries (e.g., bounding box constraints) rather than dual-encoding them in F3.
    *   *Witness Deferral (`active_port_witness_b64=None`):* Because F3 spec v1.0 explicitly operates under "Open Q 1: 假设 all ports active" (Assume all ports active), the infeasibility is established purely by spatial intersection $\mathbb{Z}^2 \times \text{Dir} \to \text{Blocked}$. The flow LP dual witness is mathematically redundant for proving infeasibility under this strict v1.0 assumption. Deferring the witness to Phase 1.5+ is logically equivalent to the F2 Cutset deferral and introduces zero soundness risk for Phase 1.2.
*   **Action:** Defer witness implementation to Phase 1.5+ as planned.

#### 2. Literal Asymmetry & State Machine Evaluator (Point 2)
*   **Severity:** **PASS (Sound & Spec-Compliant)**
*   **Analysis:**
    *   The cut literal formulation `(A.0=pA) ∧ (B.blocking_slot=pB) ⇒ ⊥` is sound. 
    *   `A.0=pA` (anonymous slot) asserts: $\exists i \in \text{Slots}(A), \text{pose}(A_i) = pA$. If *any* instance of group A takes pose `pA`, its physical port coordinates are absolute and deterministically blocked by `pB`.
    *   `B.blocking_slot=pB` (specific slot) asserts the causative blocking agent. 
    *   **Is it over-cutting?** No. Under State Machine v2 §5, multiset evaluation evaluates anonymous slots via existential quantification over the group. The cut logically reads: "If *any* A is at pA, and *this specific* B is at pB, the state is invalid." This is mathematically valid. It is slightly weaker (more specific) than `(A.0=pA) ∧ (B.0=pB)`, but weaker cuts are intrinsically sound (no false pruning of optimal branches).

#### 3. Source of Truth: `cell_owner` vs `master_solution` (Points 3, 6)
*   **Severity:** **MINOR (Completeness Risk, strictly Sound)**
*   **Analysis:** 
    *   Deriving targets from `state.cell_owner` instead of `master_solution.placed_facility_poses` means pending (unrasterized) mandatory facilities will be bypassed.
    *   **Soundness:** Missing a cut (NOT-CUT) does not prune feasible optimal solutions, hence mathematical soundness is maintained. 
    *   **LBBD Complexity:** If a blocked mandatory facility is missed because it hasn't populated `cell_owner`, the Master CP-SAT might accept a structurally invalid configuration for one extra iteration. However, once rasterized in the subsequent iteration, F3 will catch it. This is a finite delay in convergence, bounded by the number of unrasterized facilities.
*   **Action:** Accept for Phase 1.2. The trade-off is sound, but note that the number of F3 certs generated in fixture runs might be artificially lower than expected due to unrasterized bypasses.

#### 4. Ports Source Equivalence (Point 5)
*   **Severity:** **PASS (Implementation Hygiene)**
*   **Analysis:**
    *   `state.candidate_placements` represents the application of an affine transformation (rotation + translation) $T_{pA}$ to the `canonical_rules`. 
    *   Using the pre-baked ports from `candidate_placements` is mathematically equivalent to looking up `canonical_rules` and applying $T_{pA}$ dynamically, but removes the risk of floating-point/rounding errors in re-computation. It is strictly superior.
*   **Action:** Keep current implementation.

#### 5. Dedup Signature & U-Shaped Geometry (Point 8)
*   **Severity:** **PASS**
*   **Analysis:** 
    *   Can two distinct ports share a front cell? Yes. Consider a $\subset \mathbb{Z}^2$ grid where port $P_1 = (0,0)$ faces East (front= $(1,0)$) and port $P_2 = (2,0)$ faces West (front= $(1,0)$). This implies $\|c_1 - c_2\|_1 = 2$.
    *   If a facility geometry allows this, injecting the `port_dir` into the signature differentiates the violations. 
    *   If both cuts are emitted, adding idempotent logical clauses $C \land C$ to a SAT solver has no mathematical consequence (does not over-cut).
*   **Action:** Keep `port_dir` in the dedup signature.

#### 6. Fail-Closed Silent Skips (Point 7)
*   **Severity:** **WARNING (Generator Completeness Target Risk)**
*   **Analysis:** 
    *   Silently bypassing missing lookups (`ports lookup miss`, `blocking_gstate None`) acts as a sink for cert generation. Since your stated goal for the F3 special-case phase is $\geq 45$ certs to prove coverage, silent misses violate observability. 
*   **Action:** It is highly recommended to inject `logging.warning` or `logging.debug` on these `return []` / `continue` paths before merging. If A3 real-emit fails to reach 45 certs, without logs, proving whether the cause was geometry (no actual blockages) vs. generator bug (silent misses) becomes a mathematically undecidable state observation problem without recompilation.
