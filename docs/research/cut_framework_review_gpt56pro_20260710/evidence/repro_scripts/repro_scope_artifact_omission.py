from __future__ import annotations
import sys
from dataclasses import replace
sys.path.insert(0, '/mnt/data/project_pkg')
from src.tests.test_cut_framework_attach_wiring import _boundary_overflow_state
from src.cuts.lifecycle import step_6_attach_scope_check
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
state = _boundary_overflow_state()
cut = generate_region_capacity_cuts(state, state.canonical_rules or {}, iter_index=1)[0]
assert cut.scope is not None and cut.scope.artifact_hashes
omitted = replace(cut, scope=replace(cut.scope, artifact_hashes={}))
print({'state_artifacts': state.artifact_hashes, 'cut_artifacts': omitted.scope.artifact_hashes, 'decision': step_6_attach_scope_check(omitted, state)})
