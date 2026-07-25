# Non-certified cuts Gate 1 v4 authority completion

Document kind: research authority terminal summary  
Evidence cutoff date: 2026-07-24 (Asia/Tokyo)  
Status: `CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS / MECHANISM_CREDIBLE`  
Authority run: `run-20260723T231223Z-0067f7`  
Repository HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`

## Terminal judgment

Gate 1 v4 establishes that the selected non-certified-cuts injection mechanism
is reachable and that one concrete applied inequality excludes the same
frozen incumbent from which it was derived. The authority run passed the
synthetic lifecycle tests, the forced control/treatment comparison,
independent arithmetic replay, resource/terminal replay, manager-epoch replay,
and detached continuation publication.

The formal gate reports:

```text
status=CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS
verdict=MECHANISM_CREDIBLE
mechanism_credible=true
continuation_eligible=true
continuation_authorized=false
organic_arm_launch_authorized=false
global_claim_authorized=false
campaign_closed=false
```

The detached continuation reports:

```text
continuation_eligible=true
continuation_authorized=true
organic_arm_launch_authorized=false
campaign_closed=false
```

These records are deliberately asymmetric. The gate proves eligibility. The
separate continuation binds that result to the same campaign root, selected
manager/boot epoch, Gate 1 admission checkpoint, and pre-registered
prospective child slot. It does not authorize an organic arm. No prospective
manifest, AB16 selection, organic arm directory, or terminal classification
exists.

## Authority identities

The no-overwrite campaign is:

```text
.artifacts/noncert_cuts_ab_trust_gate1_v4_20260724/
  run-20260723T231223Z-0067f7/
```

Its principal identities are:

| Member | Size | SHA-256 |
| --- | ---: | --- |
| campaign package ID | — | `ec939ae4378b860a5ce637bbe039843f32595c8492954144fbad2f7eb8214384` |
| `campaign-root.json` | 32,464 B | `f81284b7e54d38661ecd4913700c64444f8001f3ef2addca914238761dbac506` |
| `gate1-v4/selection-a001.json` | 19,717 B | `78618026995c7000b1176d04862493bcb47dfd891390c1d08f1b7f066b6a98b0` |
| `gate1-v4/authority/manager-epoch-gate-admission.json` | 12,884 B | `d8792716a8e9cba0d140ffcc08676f8b6fe9c1f41fe9a313e73355de545bdd08` |
| `gate1-v4/gate-a001.json` | 20,936 B | `0b5d1c97f0d09cd3605e86d5861f300cbd2826bb393ae1d5461c4a0083a944ec` |
| `gate1-v4/continuation-authorization-a001.json` | 5,753 B | `eb9d569d88578827d46c8209ef5b69eab3c7762ae1edc1ba0ac90f2d8433132b` |

The pre-implementation legacy freeze remains:

```text
.artifacts/noncert_cuts_ab_trust_gate1_v4_20260724/
  history-freeze-a001/manifest.json
size_bytes=1397516
sha256=35e99c96482573976b70698f3422c9ab586afb1df3366e466ff93f901114de68
file_count=4076
```

It freezes the explicit allowlisted history that existed before the v4
closeout. New v4 campaign directories are outside that member set. The v1,
v2, and v3 tools, receipts, manifests, closeouts, and failed historical runs
were not rewritten.

## Manager and resource authority

The campaign fixes one user-manager/boot epoch:

| Field | Value |
| --- | --- |
| boot ID | `7af1ac9e-b552-412a-84e0-bf8bf2955835` |
| DBus unique owner | `:1.1` |
| manager PID/starttime | `2118 / 3154` |
| manager executable | `/usr/lib/systemd/systemd` |
| executable size | `172,056 B` |
| executable SHA-256 | `de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953` |
| manager version | `261.1-1-arch` |

The bootstrap captures this epoch twice around the read-only privileged
attestation. Each of the four selected units independently observes it at
`prelaunch`, `preterminal`, `terminal`, `cleanup`, and `detached-replay`.
After all four detached replays, the campaign captures a fresh
`gate-admission` observation. Every observation joins the same boot ID, DBus
owner, manager PID/starttime, executable device/inode/path/size/mode/hash,
version, and features. A manager or boot change fails closed.

Only the fixed manager attestor runs through `sudo -n`. Its audited operation
is limited to read-only same-FD `fstat` and hashing of the DBus-resolved
manager executable, joined to the surrounding unprivileged observations.
The bootstrap, supervisor, payloads, lifecycle observer, arithmetic checker,
gate, and solver callback run as the ordinary user.

All four transient units use:

```text
MemoryHigh=37580963840
MemoryMax=41875931136
MemorySwapMax=17179869184
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
```

The two-stage lifecycle keeps a selected supervisor/keeper alive after the
payload has been reaped. The external observer captures the still-existing
cgroup limits, current/peak memory and swap, event counters, process set, and
`cgroup.events`; only then does it issue the release token. It subsequently
captures the unit terminal result and proves cleanup after systemd has pruned
the transient cgroup. The terminal phase never treats an empty
`ControlGroup` value as cleanup evidence.

Detached resource replay identities are:

| Unit | Terminal class | SHA-256 |
| --- | --- | --- |
| `q-success` | success | `9a2e1479c1af43f3623f7f12fdbc49ccf9c800caafcacfd294aa91f6eeaca240` |
| `q-postseal-fail` | post-seal failure | `31c009a7481a16ecea2bb513e554325b78a7612e6b4b7c24ece5f152a1c29647` |
| `forced-control` | success | `990d488253cf711d0e30b64c13a63904f399957d89c0d1ddd99d76174ab7cdf7` |
| `forced-treatment` | success | `b6cea2af34ad2e8baef2c257fe22fb3cc1bfcfab91b5600ef689d1efeb989b06` |

The `q-postseal-fail` unit demonstrates that a payload failure after its inner
seal remains visible in the outer terminal result; the keeper does not turn
that failure into success. Cleanup leaves no selected unit, payload,
supervisor, or campaign cgroup.

## Forced positive-control result

The common pre-injection model is solved and sealed before either arm is
cloned. The response, full solution, incumbent, selector contract, mandatory
data, and candidate data share:

```text
common_prestate_id=03e90d629dbdd21ebde53da2ab5768f27f7fb05b0b1be4a63f4cf9d2b468036d
```

Both arm bindings are sealed before either post-injection model exists.
Control then performs an empty injection; treatment uses the selected forced
provider and the production typed attach chain. Neither arm solves the
post-injection model. The frozen incumbent is therefore the same pre-injection
solution for both arms and for the independent arithmetic check.

The formal independent receipt is:

```text
gate1-v4/positive-control-common/independent-arithmetic-receipt.json
size_bytes=2225
sha256=3ce0eb33a5bf604b85d9ef7ebad8df153746565c8e3945a0eb264593ffe86164
status=PASS_FORMAL_MECHANISM_POSITIVE_CONTROL
```

It independently reconstructs the active ghost selector from the frozen
binary model and complete solver response, then joins the assignment,
compiled cut, and `APPLIED` ledger event:

| Field | Control | Treatment |
| --- | ---: | ---: |
| generated | 0 | 1 |
| compiled | 0 | 1 |
| applied | 0 | 1 |

The selected treatment inequality is:

```text
family=region_capacity
cut_id=F1-region-left_or_bottom_union-1784848401954893-1001
condition_literal=(index=691,name=ghost__0_0_1_1)
active=true
lhs=46
rhs=45
violated=true
```

This establishes mechanism reachability and exclusion power for this one
concrete inequality on this one frozen incumbent.

## Claim boundary and next permitted stage

Gate 1 v4 does not establish:

- organic cut generation, compilation, or application;
- a runtime benefit, regression, or causal effect for any cut family;
- global soundness of `region_capacity`, `shape_packing_hall`, or
  `power_hitting_set`;
- a proof-sidecar, proof-ledger admission, PIC-4, PIC-5, B6, or Stage-B
  promotion;
- SAT, UNSAT, infeasibility, a feasible witness, a lower bound, or an upper
  bound;
- production `CERTIFIED`.

The next mandatory cuts task is the separately gated prospective AB16 suite
in this same campaign and manager/boot epoch. Before any arm exists, a
future task must publish the pre-registered immutable experiment manifest and
arm selection. The suite consists of two order-balanced matched pairs for
each single family and for the three-family bundle. The current continuation
is a prerequisite for that task, not an arm-launch authorization.

If the manager or boot epoch changes before or during that suite, this
campaign cannot be spliced with a replacement run. The incomplete campaign
must remain immutable and a new campaign must repeat Gate 1 in full.

Execution chronology and exact commands are in `01_execution_record.md`.
