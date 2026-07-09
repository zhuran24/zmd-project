from __future__ import annotations
import sys
from unittest import mock
sys.path.insert(0, '/mnt/data/project_pkg')
from src.tests.test_cut_framework_attach_wiring import _build_miner_master, _controller

master = _build_miner_master()
master.ghost_rect = (2, 1)  # authoritative convention: (width, height)
controller = _controller(master)
context = (0, object(), {'x': 1, 'y': 0}, {(1, 0), (2, 0)})
with mock.patch.object(type(controller), '_selected_ghost_context', return_value=context):
    state = controller._build_cut_framework_state()
print({'master_ghost_wh': master.ghost_rect, 'state_ghost_rect': state.ghost_rect if state else None})
