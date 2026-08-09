# Phase 1.2 audit artifact

Contents:

- `AUDIT_REPORT.md` — finding list in the requested format.
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — appliable patch script.
- `repro/` — copy-paste repro scripts for the BLOCKER/HIGH findings.

Apply patch:

```bash
cd _phase1_2_pkg_v12/project
python /path/to/patches/0001-bind-power-family-pose-cells-and-digest.py
python -m pytest \
  src/tests/cuts/test_family_power_hitting_set.py::test_validator_unsound_when_facility_cells_do_not_match_pose_registry \
  src/tests/cuts/test_family_power_grid_reach.py::test_validator_unsound_when_facility_cells_do_not_match_pose_registry \
  src/tests/cuts/test_oracle_scope_digest.py -q
```
