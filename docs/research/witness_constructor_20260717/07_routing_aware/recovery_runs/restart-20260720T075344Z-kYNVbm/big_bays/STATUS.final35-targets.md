# Final35 mixed-target query status

Scope: one periodic large bay under the simultaneous pole-column move
`17/29/41 -> 18/30/42`. These local results do not establish a global layout
or commodity-routing conclusion.

The following targets were each queried under both connectivity models and
returned exact `INFEASIBLE`, never `UNKNOWN`:

| target | all residual connected | selected active terminals connected |
| --- | ---: | ---: |
| `(10,5,5)` | 135.727925178 s | 73.449555754 s |
| `(8,5,6)` | 18.108116151 s | 8.737257718 s |
| `(8,6,5)` | 5.865035802 s | 4.926183659 s |

Because each proposed pair required its first target, their paired second
targets were not run. The positive periodic `(10,5,4)` selection remains in
`periodic_big_bay_selection.json`; nothing in this status changes that result.
