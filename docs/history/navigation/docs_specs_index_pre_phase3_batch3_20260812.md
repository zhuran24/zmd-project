# `specs/` index

The numbered specifications describe contracts and design boundaries. Current runtime behavior is
code-first, but any divergence is a defect to repair in the same change. “Code changed, spec later”
is not an accepted steady state for proof, schema or publication semantics.

## Core groups

| Specs | Scope |
|---|---|
| `01`–`05` | Problem, notation, canonical rules, demand expansion and exact instance domain |
| `06`–`07` | Candidate placement and placement masters |
| `08` | Continuous topology-flow diagnostic only; not a certified gate/cut oracle |
| `09` | Exact discrete grid routing and connectivity acceptance |
| `10` | Benders/cut design, including historical and future cut-family boundaries |
| `11` | Current producer → supervisor → central publisher orchestration |
| `12` | Blueprint schema plus canonical publication authority |
| `13`–`20` | Ecosystem, interchange and preprocess contracts |
| `21` | Probe/telemetry scheduling, non-authoritative |
| `22`–`23` | IndustrialPlanner export/validation and outer-base decision-support |

`ecosystem_notes/` contains informal compatibility notes, not certification authority.

## Reading rules

1. Start with `PROJECT_LOCK.md` and `specs/11_pipeline_orchestration.md` for certification/release
   semantics.
2. A schema-valid, adapter-valid or telemetry-valid artifact is not automatically proof-bearing.
3. `specs/08` must never be cited as a flow gate or Farkas certificate implementation.
4. `specs/12` must be read together with `src/search/certified_surface.py`; generic writers cannot
   publish canonical certified files.
5. Historical phase names and test numbers describe their dated bytes only.

When code and a spec disagree, do not silently “trust code and leave the spec”. Treat the text drift
as a release defect, determine the actual current behavior with tests/call sites, and update lock,
spec, comments and obligations together where required.
