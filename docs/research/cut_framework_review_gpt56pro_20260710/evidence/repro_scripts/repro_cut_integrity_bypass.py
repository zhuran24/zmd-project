from __future__ import annotations
import hashlib, json, os, sys
from dataclasses import replace
from unittest import mock
sys.path.insert(0, '/mnt/data/project_pkg')

from src.tests.test_cut_framework_attach_wiring import (
    _SpyMaster, _controller, _boundary_overflow_state, _mock_ghost_context,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts

state = _boundary_overflow_state()
cut = generate_region_capacity_cuts(state, state.canonical_rules or {}, iter_index=1)[0]
assert cut.cert is not None and cut.geometric_payload is not None
safe = json.loads(cut.cert.cert_payload)
malicious = dict(safe)
malicious['cap_R'] = 0
malicious['gap'] = int(malicious['demand_R'])
malicious_bytes = json.dumps(malicious, sort_keys=True, ensure_ascii=False).encode('utf-8')
malicious_hash = hashlib.sha256(malicious_bytes).hexdigest()
tampered = replace(
    cut,
    cert=replace(cut.cert, cert_payload=malicious_bytes, cert_hash=malicious_hash),
    oracle_cert_hash=malicious_hash,
)

spy = _SpyMaster()
controller = _controller(spy)
with mock.patch.dict(os.environ, {'EXACT_CUT_FRAMEWORK_ATTACH': '1'}):
    with mock.patch.object(type(controller), '_build_cut_framework_state', return_value=state), \
         mock.patch.object(type(controller), '_selected_ghost_context', return_value=_mock_ghost_context()), \
         mock.patch('src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts', return_value=[tampered]), \
         mock.patch('src.cuts.oracles.shape_packing_hall_oracle.compute_sot_region_demand_overrides', return_value={}):
        attached = controller._maybe_attach_framework_cuts(trigger='binding_infeasible', iteration=1)
print({'integrity_error_expected': cut.geometric_payload != tampered.cert.cert_payload, 'attached': attached, 'master_calls': spy.region_capacity_calls})
