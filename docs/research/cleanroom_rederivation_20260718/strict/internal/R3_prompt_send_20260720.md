# R3 Prompt — Methodology-Transfer Round (send version, 2026-07-20)

Attached are four files:

- `problem.md` — the complete problem specification;
- `problem_instance.json` — the authoritative instance data;
- `instance_schema.json` — the JSON schema for the instance;
- `methodology_brief.md` — a set of engineering principles (M1–M6) distilled from extended practice on problems of this class. It intentionally contains no concrete models, encodings, or results — only meta-level methodology.

Treat the benchmark as a new problem. The specification and instance are the sole authority on the rules; the brief carries no authority over the problem itself.

Your task:

1. **Critique the methodology first.** Where do M1–M6 seem incomplete, suboptimal, or wrong for this specific problem? If you would replace or extend any principle, say how and why. Do not defer to the brief — it is input, not doctrine.

2. **Design the attack you would actually run.** Applying, adapting, or overriding the methodology as you judge best, produce a concrete end-to-end plan for solving the benchmark to its stated evidentiary standard (certified lexicographic optimality). Be specific enough to execute:
   - what decomposition (if any) you would use, and which rule lives where — with the reasoning, not just the assignment;
   - which necessary-condition lifts or bound certificates you would chase first, and what each one would prove if it succeeds;
   - concrete encodings for the pieces you consider hardest, with size arithmetic;
   - your probe sequence: what you would build/measure before committing to any long solve, and the abort criteria at each stage;
   - how the final certified claim is assembled and independently checked.

3. **State your assumptions.** Where the specification is ambiguous, resolve it explicitly and list every such resolution, as material assumptions, in a dedicated section.

4. **Prioritize novelty of method over completeness of survey.** If you see an approach that the methodology does not obviously suggest — an unusual encoding, an unconventional decomposition, a certificate the brief's framing would miss — develop that in depth rather than enumerating standard options. We value one sharp, non-obvious method more than a balanced review.

Depth over breadth throughout. Estimated compute assumptions: a modern 24-core x86-64 Linux machine, 48 GB RAM, generous disk.
