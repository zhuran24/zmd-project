# Recomputed threshold tables

## Synthetic duals

| dual | bucket weights (in bucket order) | Σdμ | Σmπ | λ | anchor bound |
|---|---:|---:|---:|---:|---:|
| D0_AREA | 9/9/9/25/25/24/24/24 | 0 | 3392 | 0 | 3392 |
| D1_SCARCITY_PRICES | 8/8/8/23/23/22/22/22 | 629 | 3137 | 15 | 3781 |
| D2_SLACK_EDGE_SELECTIVE | -3/-3/9/-5/25/-6/-6/24 | 3462 | 3805 | -20 | 7247 |

Bucket order: M3_1i1o, M3_1i2o+2i1o, M3_1i3o+2i1o, M5_1i1o, M5_1i2o, M6_3i1o, M6_4i1o, M6_5i1o.

## CLEAN multiplicity

| local CLEAN no-hole drop | pure 3392 baseline | current hole-aware 3388 baseline | remaining to 3324 |
|---:|---:|---:|---:|
| 0 | 3392 | 3388 | 64 |
| 1 | 3376 | 3372 | 48 |
| 2 | 3360 | 3356 | 32 |
| 3 | 3344 | 3340 | 16 |
| 4 | 3328 | 3324 | 0 |
| 5 | 3312 | 3308 | 0 |

## Exact branch inequalities

- `hole_at_CLEAN`: `15*dC0 + dC1 + sum(dj0) + dR0 >= 51`
- `hole_at_boundary_H129`: `16*dC0 + sum_{j!=k}(dj0) + dj1[k] + dR0 >= 63`
- `hole_at_boundary_H130`: `16*dC0 + sum_{j!=k}(dj0) + dj1[k] + dR0 >= 64`
- `hole_at_CORNER`: `16*dC0 + sum(dj0) + dR1 >= 35`
