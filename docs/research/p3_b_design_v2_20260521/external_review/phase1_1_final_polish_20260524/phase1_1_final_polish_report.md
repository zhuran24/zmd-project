# Phase 1.1 final polish report (2026-05-24, v12)

## Verdict

**Phase 1.1 remains GO** and the package is ready to enter **Phase 1.2 P1.2B-F5/F6/F7/F8/F9**.

This pass focused on small review blockers after the v11 recheck package: schema tightness, plan/README drift, and offline bootstrap reproducibility.

## Issues found and fixed

1. **F3 port_exposure cell bound gap**
   - Previous state: F3 cert cells were checked as length-2 strict ints, but unlike F2/F4 they were not bounded to the 70x70 board.
   - Fix: `src/cuts/families/port_exposure.py::_cell` now rejects out-of-grid cells with `schema_err`.
   - Regression: `test_validate_port_exposure_schema_err_out_of_grid_cell`.

2. **Front-cell mismatch test was using an out-of-grid coordinate**
   - Fix: changed that test to an in-grid wrong front cell `(8, 10)` so it still tests the intended math path.

3. **Plan/GO/count drift**
   - Fix: current docs now use `P1.2A` for entry hardening and `P1.2B-F5/F6/F7/F8/F9` for the five Phase 1.2 families. Current cut gate is now 189.
   - Historical archive rows remain historical on purpose.

4. **Offline bootstrap docs were misleading**
   - Fix: README now uses Python 3.13, `--find-links /tmp/zmd_deps_v3/deps_wheels`, and explicitly installs `ruff mypy vulture bandit radon` from the offline wheel bundle.

5. **Package hygiene**
   - Final package is cleaned before repack: no `.venv`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.pytest_tmp`, `__pycache__`, `.pyc`, or `.pyo` artifacts.
   - The recombined `zmd_deps_v3.zip` is included at package root, so the review package is self-contained.

## Verification

```bash
.venv/bin/python -m pytest src/tests/cuts/ -q
# 189 passed

.venv/bin/python -O -m pytest src/tests/cuts/ -q
# 189 passed, 1 warning (pytest assertion warning expected under -O)

.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
# All checks passed

.venv/bin/python -m mypy --strict --explicit-package-bases src/cuts/
# Success: no issues found in 22 source files

.venv/bin/python -m vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py --min-confidence 100
# pass

.venv/bin/python -m bandit -q -r src/cuts/
# pass / 0 issues

.venv/bin/python -m radon cc src/cuts/ -s -a
# Average complexity: A (4.273291925465839), max C(15), no D

.venv/bin/python scripts/b_design_v2_exit_criteria.py
# 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL
```

## Non-blocking note

A full `src/tests` run is larger and not the Phase 1.1 cut-framework gate. During spot execution it collected 2485 tests and had no failure before timeout; the formal Phase 1.1 gate is the cut framework gate above plus static checks and exit criteria.
