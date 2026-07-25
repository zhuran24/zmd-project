# Gate 1 v3 authority closeout

Document kind: research authority-hardening terminal summary  
Evidence cutoff date (UTC): 2026-07-23  
Status:
`HARDENING_INCOMPLETE / LEGACY_A002_CREDIBILITY_INCOMPLETE`  
Authority run: `run-20260723T113911Z-SrJBE0`  
Repository HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`  
Current overlay:
`positive-control/closeout-a002/gate-a003.json`

## Terminal judgment

Gate 1 v3 preserves a correct fail-closed historical overlay but did not pass
final adversarial admission for future non-incomplete classifications. The
historical run still has no immutable post-termination resource authority,
prospectively selected paired arm launch, joined arm result, inner resource
ledger, terminal envelope, binary model, or binary solver response.
Consequently `gate-a003.json` reports:

- `status=CREDIBILITY_INCOMPLETE`;
- `reason=resource_authority_missing`;
- `classification_complete=false`;
- `experiment_verdict=false`;
- `advance_authorized=false`;
- `arm_launch_authorized=false`;
- `historical_overlay=true`.

Its process exit code is 2. That exit is the expected successful closeout
result: the gate replayed every available authority and refused to turn
missing evidence into either a positive or a negative cuts classification.

The complete missing-gate set is:

```text
resource_authority_missing
paired_arm_launch_authority_missing
arm_result_join_missing
resource_inner_raw_authority_missing
resource_terminal_authority_missing
selector_model_binary_authority_missing
selector_solver_response_binary_authority_missing
```

`resource_authority_missing` is the stable primary reason, but it does not
hide the other six gaps. The qualification package, selected receipt, tool
bytes, input bytes, and historical selection all replayed successfully.

Two independent-admission blockers remain:

1. The outer observer validates `ActiveState`, `SubState`, the final memory
   limits, `OOMPolicy`, `KillMode`, `SendSIGKILL`, and `RuntimeMaxUSec`, but
   omits those fields from its terminal envelope. The resource verifier
   therefore cannot independently derive the complete terminal state and
   resource contract from sealed evidence.
2. The gate snapshots the selection once, but resource replay passes its path
   to the verifier, which reopens it. The gate then compares the verifier
   result with another fresh path identity rather than the original detached
   identity. A same-path replacement between stages can splice resource
   evidence from different selection bytes.

No later tool generation, package, selection, or gate was created after this
finding. The branch therefore stops at an incomplete hardening admission.

## Implemented authority model

The v3 design has one forward-only authority chain:

1. A qualification package seals the exact tool and input bytes. Its
   `SHA256SUMS` digest is the package ID.
2. An independent verifier may issue a sibling PASS receipt. This receipt is
   derived byte-qualification evidence and cannot authorize a launch or an
   experiment classification.
3. A package-external launch selection is the direct authority root. A future
   paired selection must exist before either arm directory and must directly
   fix the package ID, purpose, run nonce, repository HEAD, resource contract,
   tool/input identities, arm paths, unit names, and outer observer.
4. The gate replays the selected receipt, every selected source byte, the
   selection's detached byte identity, and the evidence path manifest.

The selection created for this closeout is permanently
`purpose=historical_replay` and `arm_launch=false`. It cannot be flipped into a
future launch authority and does not authorize an experiment verdict.

### Resource terminal authority gap

A future arm can write an append-only inner raw resource chain, and the
selection-bound observer runs outside the target unit. It joins the run nonce,
unit name, and `InvocationID`, waits until the unit is inactive or failed,
checks final systemd properties, and waits for `cgroup.events` to report
`populated 0` or for the cgroup to disappear before creating a no-overwrite
terminal envelope.

That implementation is not sufficient for admission. Although the observer
checks the full state and contract, the envelope retains only a subset of the
terminal fields. The independent verifier can derive wall time, peak memory,
swap, `memory.events`, selected exit fields, and cgroup cleanup from the inner
chain plus envelope, but it cannot independently reconstruct all final
systemd state and configured limits. No future positive or negative
classification may use this v3 path.

### Selector and inequality authority

For a future positive treatment, the v3 checker reads an official binary
`CpModelProto` and complete binary `CpSolverResponse` with the installed
OR-Tools protobuf implementation. It rejects malformed, truncated,
non-canonical, unknown-field, or solution-length-drifted inputs. It derives
the unique active ghost selector's real proto index, name, Boolean domain, and
rectangle from those bytes before comparing any incumbent, prestate, sample,
ledger, or assignment assertion. No variable index is hard-coded and no
handwritten protobuf-text parser is used.

The checker then joins one concrete compiled cut to its actual `APPLIED`
ledger event and independently recomputes activation, `lhs`, `rhs`, and
`lhs > rhs` from the frozen assignment, strict mandatory/candidate inputs,
selector truth, plan parameters, and enforcement literals. This validates
only that specific applied inequality and join. It is not a proof-sidecar or
a global F1/F6/F7 soundness verifier.

Each individual replay snapshot is opened with `O_NOFOLLOW`; payload reading,
hashing, and parsing/copying use that file descriptor, with pre/post `fstat`
and a final path-to-inode check. This correctly rejects replacement during
one snapshot. It does not close the cross-stage selection gap: the gate and
resource verifier independently reopen the same pathname, and the verifier
result is not bound back to the gate's original detached selection identity.

## Immutable identities

The v1/v2 tools, two historical manifests, terminal v2 documents, and three
v2 closeout JSON files were frozen before any v3 implementation:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `closeout-a002/history-v2-freeze-a001.json` | 3,983 B | `83832408c13a7946a0b29279978123f0123c71d7aba3a2371ce9bab6811c8419` |
| `closeout-a001/control-replay-a002.json` | 3,028 B | `ea98ab9b959a8c22472db36b01b2f0444e7838ee603d6d065e3d81b99570d093` |
| `closeout-a001/treatment-replay-a002.json` | 3,038 B | `6acd631c67b6036a959cd442eb7b14bfb8e906661b07c74bc5aca736905741a7` |
| `closeout-a001/gate-a002.json` | 38,358 B | `de57589e0878f252785de69963dbb3483c02a55db55b8f58024bdb79de040068` |

The current qualification and overlay identities are:

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `closeout-a002/historical-evidence-a001.json` | 112 B | `90b80f5b1d33e12070526bcb0ac2f66489944b090dd03d777b96367b4ce110aa` |
| `qualification-package-a002/package/package-manifest.json` | 18,102 B | `98803846bedacde37addaf8e4e89e0e0ea377ad86a69efcf37cef621dca86adb` |
| `qualification-package-a002/package/SHA256SUMS` | 2,860 B | `25cacd0b376eb671ae76da467427651fd158e8a4e07c3617d7956e8913bd33a1` |
| `qualification-package-a002/verifications/independent-a001/receipt.json` | 21,341 B | `64ba1e75daefb97d2c52dae83174c1169364289772bf097a7ab3b2f4aad371b3` |
| `qualification-package-a002/launch-selections/historical-a001.json` | 10,618 B | `3af4dc0d4e5a295205a2fb1c5e833babbfcd4d0d15268f1de897376f4b7c9081` |
| `closeout-a002/gate-a003.json` | 11,023 B | `e8f2b3a37354f00eb0071105568e550734f2d49934dd8d7ac628dff99c634878` |

The package ID is
`25cacd0b376eb671ae76da467427651fd158e8a4e07c3617d7956e8913bd33a1`.
The PASS receipt is explicitly non-authorizing. The historical selection is
the direct root for this overlay only.

`qualification-package-a001` is immutable failed history. Its verifier
correctly rejected an erroneous object-only type declaration for the
array-rooted `mandatory_exact_instances.json`; no PASS receipt was created.
The no-overwrite replacement is `qualification-package-a002`.

The package directly pins the following v3 tool bytes:

| Tool | Size | SHA-256 |
| --- | ---: | --- |
| `build_qualification_package_v1.py` | 15,418 B | `1185b120e342a6e50a34f9592d19fc05fb54d46405a12f287729268ddf718a46` |
| `verify_qualification_package_v1.py` | 18,596 B | `b7c250ecf3a3acb5c8d409c452b0032034be535365dd46cd08c589b3e0d7f2f8` |
| `positive_control_gate_v3.py` | 55,362 B | `67c3f637542a43f2056b88e800c7530ffa8f09780cee79ea8178d73a3fbd98bc` |
| `independent_arithmetic_check_v3.py` | 37,119 B | `929e6038cd29008df3440168b5df763234d75fca7ba40b9c76fbba6056f4f627` |
| `independent_resource_verifier_v2.py` | 46,212 B | `f5da43b1f1c02c486250d66c51d5c4e0600e5247592d1e97366204def8491f7b` |
| `positive_control_resource_recorder_v2.py` | 33,853 B | `5fb1bd861ced6fcb7fa8e68dfb2204891a909cf22012f1cca09c612bf3f86b70` |
| `launch_selection_observer_v1.py` | 30,780 B | `a94594960629e9ef3fc09103a985dc2cf30d470deb8085fc2159ec2f37d63638` |
| `positive_control_runner_v2.py` | 19,935 B | `103c6da0972dab303e8801e0ea3cef7d8c7c7a32aac07cee5c297b71d849aa39` |

The receipt also pins the six historical v1/v2 tools, both historical
documents, both history manifests, all three a002 JSON files, the freeze,
strict mandatory/candidate data, the fixed Python 3.13 interpreter bytes, and
the empty historical evidence manifest.

## Claims and stop boundary

The v3 focused tests pass for their synthetic fixtures and mutation canaries,
but the final independent audit rejected the complete hardening design on the
two gaps above. The tests do not supply missing evidence for the historical
run or authorize future non-incomplete classification. In particular, this
closeout does not establish:

- a true positive or true negative cuts result;
- a complete resource-terminal authority or cross-stage selection identity
  closure;
- cut soundness, organic runtime usefulness, causal value, or single-family
  usefulness;
- a real `APPLIED` inequality in the historical treatment;
- the observed 35/39/16 GiB contract, 21.5 GB peak, or zero swap/OOM as
  immutable resource authority;
- PIC-4, PIC-5, B6 authorization, UNSAT, infeasibility, witness, or lower
  bound.

The live resource figures remain historical observation only and were not
backfilled. No arm, solver, systemd unit, proof, PIC task, B6 task, witness
search, or Track B task ran during this closeout.

This cuts branch stops here regardless of the hardening validation result.
The supervisory workflow decides whether and when the core Track B direction
resumes. Any future cuts experiment requires a new no-overwrite run and a new
prospective paired launch selection; the historical selection and run cannot
be reused.

Exact construction and validation commands are preserved in
`01_execution_record.md`. The v1/v2 historical chronology remains in the
byte-frozen `../noncert_cuts_ab_trust_20260723/03_execution_record.md`.
