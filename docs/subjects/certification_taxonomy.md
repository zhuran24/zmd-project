# Certification Taxonomy: Verification, Acceptance, Sealing, Publication

This document is a navigation aid only. It maps four human-facing concepts to
existing project names so readers do not mistake one reused status string for one
proof authority. It does not change code semantics, status-machine behavior, guard
tokens, or artifact authority. `PROJECT_LOCK.md` plus source code remain the
authoritative contract.

## Mapping

| Concept | Existing names | Meaning |
|---|---|---|
| 核验 | master placement checks, binding checks, routing checks, empty-rectangle geometry checks | Check whether a local mathematical or geometric claim is true under the current inputs. |
| 采信 | `candidate_proof_replay` sink replay, isolated replay acceptance, `UNPROVEN` downgrade on rejection | Decide whether a strong candidate-level claim can be trusted after the sink independently replays it. A candidate record saying `CERTIFIED` is an untrusted claim until this acceptance step succeeds. |
| 封存 | `ExactCampaign.supervisor_seal()` | The sole durable terminal `CERTIFIED` mint. It rereads the committed proposal from disk, validates bindings, runs sink replay and fixed-witness verification, then writes the sealed terminal state. |
| 发布 | `certified_surface`, `resolve_p1_2_publish_open_gate`, owner phase gate | Public files are publishable only when they come from the same sealed disk-current result and the phase gate allows publication. |

## Axes

`CERTIFIED` appears at multiple layers, but the trust axis is separate from the
string. At the candidate layer it can mean "the producer reported a strong claim."
That claim is not authoritative until sink replay accepts it. At the campaign
terminal layer, durable `CERTIFIED` can only be minted by `supervisor_seal`. At the
public layer, publication still requires `certified_surface` currentness and the
P1.2 open-gate/owner phase gate.

In short:

- 核验 answers "is this local proposition true?"
- 采信 answers "can this candidate-level strong claim be trusted?"
- 封存 answers "has the supervisor minted the durable terminal state from disk?"
- 发布 answers "may the sealed result be exposed as public certified output?"

Do not rename status literals, remove guard tokens, or treat this taxonomy as a
new state machine. It is documentation/provenance only.
