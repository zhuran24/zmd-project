"""P1.2-FIX-4 tests for independent whole-layout infeasibility reverify."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts import check_p1_2_proof_obligations
from src.search import benders_loop
from src.search import independent_infeasibility_reverifier as reverifier_module
from src.search.benders_loop import LBBDController
from src.search.independent_infeasibility_reverifier import (
    INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
    INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
    REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
    REVERIFY_STATUS_DIVERGED_FEASIBLE,
    REVERIFY_STATUS_TIMEOUT,
    REVERIFY_STATUS_UNKNOWN,
    IndependentInfeasibilityReverificationVerdict,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FakeMaster:
    def __init__(self) -> None:
        self.facility_pools = {"factory": [{"occupied_cells": [[0, 0]]}]}
        self.source_instances = [{"instance_id": "a", "facility_type": "factory"}]
        self.generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        self.rules = {"commodity_metadata": {}}
        self.cuts: list[dict[str, int]] = []

    def add_benders_cut(
        self,
        conflict_set: Mapping[str, int],
        *,
        condition_lits: tuple[Any, ...] = (),
    ) -> bool:
        del condition_lits
        self.cuts.append({str(key): int(value) for key, value in conflict_set.items()})
        return True


class _FakeCutManager:
    def __init__(self) -> None:
        self.registered: list[Any] = []

    def has_structured_cut(self, cut: Any) -> bool:
        del cut
        return False

    def register_structured_cut(self, cut: Any) -> bool:
        self.registered.append(cut)
        return True


def _controller() -> tuple[LBBDController, _FakeMaster, _FakeCutManager, list[dict[str, Any]]]:
    master = _FakeMaster()
    cut_manager = _FakeCutManager()
    heartbeats: list[dict[str, Any]] = []
    controller = LBBDController(
        master=master,  # type: ignore[arg-type]
        cut_manager=cut_manager,  # type: ignore[arg-type]
        project_root=PROJECT_ROOT,
        solve_mode="certified_exact",
        heartbeat_callback=heartbeats.append,
        artifact_hashes={"unit": "hash"},
    )
    return controller, master, cut_manager, heartbeats


def _verdict(
    *,
    confirmed: bool,
    status: str,
    reason: str,
    independent_status: str | None = None,
) -> IndependentInfeasibilityReverificationVerdict:
    return IndependentInfeasibilityReverificationVerdict(
        schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
        authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
        confirmed=confirmed,
        status=status,
        stage="binding",
        reason=reason,
        independent_status=independent_status,
        details={"unit": True},
    )


def _try_add_whole_layout_nogood(
    controller: LBBDController,
    proof_summary: dict[str, Any],
) -> bool:
    return controller._add_exact_whole_layout_nogood(
        solution={"a": {"facility_type": "factory", "pose_idx": 0}},
        iteration=7,
        cut_type="binding_infeasible_nogood",
        proof_stage="binding",
        binding_exhausted=True,
        routing_exhausted=False,
        proof_summary=proof_summary,
    )


def test_independent_infeasibility_reverify_confirms_binding_infeasible_allows_cut(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}

    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=True,
            status=REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
            reason="independent_binding_solver_confirmed_infeasible",
            independent_status="INFEASIBLE",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is True

    assert master.cuts == [{"a": 0}]
    assert len(cut_manager.registered) == 1
    assert (
        proof_summary["independent_infeasibility_reverifier"]["status"]
        == REVERIFY_STATUS_CONFIRMED_INFEASIBLE
    )
    assert heartbeats == []


def test_independent_infeasibility_reverify_divergent_feasible_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}

    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=False,
            status=REVERIFY_STATUS_DIVERGED_FEASIBLE,
            reason="independent_binding_solver_found_feasible",
            independent_status="FEASIBLE",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is False

    assert master.cuts == []
    assert cut_manager.registered == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert heartbeats[-1]["event"] == "whole_layout_nogood_independent_reverify_divergence"
    assert heartbeats[-1]["reverify_status"] == REVERIFY_STATUS_DIVERGED_FEASIBLE


def test_independent_infeasibility_reverify_timeout_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}

    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=False,
            status=REVERIFY_STATUS_TIMEOUT,
            reason="independent_binding_solver_uncertain",
            independent_status="UNKNOWN",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is False

    assert master.cuts == []
    assert cut_manager.registered == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert heartbeats[-1]["event"] == "whole_layout_nogood_independent_reverify_unknown"
    assert heartbeats[-1]["reverify_status"] == REVERIFY_STATUS_TIMEOUT


def test_independent_infeasibility_reverify_exception_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}

    def _boom(**_kwargs: Any) -> IndependentInfeasibilityReverificationVerdict:
        raise RuntimeError("unit divergence")

    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        _boom,
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is False

    assert master.cuts == []
    assert cut_manager.registered == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert (
        proof_summary["independent_infeasibility_reverifier"]["reason"]
        == "independent_infeasibility_reverify_uncaught_exception"
    )
    assert heartbeats[-1]["event"] == "whole_layout_nogood_independent_reverify_unknown"


def test_independent_infeasibility_reverify_routing_exhaustion_without_binding_confirmation_unknown(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        reverifier_module,
        "_reverify_binding_infeasible",
        lambda **_kwargs: _verdict(
            confirmed=False,
            status=REVERIFY_STATUS_DIVERGED_FEASIBLE,
            reason="independent_binding_solver_found_feasible",
            independent_status="FEASIBLE",
        ),
    )

    verdict = reverifier_module.reverify_whole_layout_infeasibility(
        solution={"a": {"facility_type": "factory", "pose_idx": 0}},
        facility_pools={"factory": [{"occupied_cells": [[0, 0]]}]},
        instances=[{"instance_id": "a", "facility_type": "factory"}],
        project_root=PROJECT_ROOT,
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
        binding_kwargs={},
        time_limit_seconds=0.001,
    )

    assert verdict.confirmed is False
    assert verdict.status == REVERIFY_STATUS_UNKNOWN
    assert verdict.reason == "routing_exhaustion_phase1_conservative_unknown"
    assert verdict.details["binding_reverification"]["independent_status"] == "FEASIBLE"


def test_p1_2_checker_rejects_whole_layout_reverify_gate_removal(tmp_path: Path) -> None:
    benders_path = tmp_path / "benders_loop.py"
    benders_source = check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(
        encoding="utf-8"
    )
    benders_path.write_text(
        benders_source.replace(
            "reverify_verdict = reverify_whole_layout_infeasibility(",
            "reverify_verdict = unchecked_whole_layout(",
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert (
        "whole-layout nogood funnel must call independent infeasibility reverifier"
        in errors
    )


def test_p1_2_checker_rejects_inflight_cache_read_in_infeasibility_reverifier(
    tmp_path: Path,
) -> None:
    reverifier_path = tmp_path / "independent_infeasibility_reverifier.py"
    reverifier_source = (
        check_p1_2_proof_obligations.INDEPENDENT_INFEASIBILITY_REVERIFIER_PATH.read_text(
            encoding="utf-8"
        )
    )
    reverifier_path.write_text(
        reverifier_source + "\n\ndef _unit_bad_cache_read(self):\n    return self._solver\n",
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        reverifier_path=reverifier_path,
    )

    assert (
        "independent infeasibility reverifier must not read in-flight cache authority: "
        "self._solver"
    ) in errors


def test_p1_2_checker_rejects_env_reader_in_infeasibility_reverifier(
    tmp_path: Path,
) -> None:
    reverifier_path = tmp_path / "independent_infeasibility_reverifier.py"
    reverifier_source = (
        check_p1_2_proof_obligations.INDEPENDENT_INFEASIBILITY_REVERIFIER_PATH.read_text(
            encoding="utf-8"
        )
    )
    reverifier_path.write_text(
        reverifier_source
        + '\n\nimport os\n\ndef _unit_bad_env_read():\n    return os.getenv("EXACT_FAKE")\n',
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        reverifier_path=reverifier_path,
    )

    assert any("must not import os" in error for error in errors)
    assert "independent infeasibility reverifier must not read EXACT_* env" in errors
