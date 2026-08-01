from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(name: str, *, alias: str | None = None) -> Any:
    spec = importlib.util.spec_from_file_location(alias or f"_ab16_remaining_{name}", RESEARCH / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


baseline_admission = _load("baseline_admission_v1", alias="baseline_admission_v1")
baseline_rebuild = _load("baseline_rebuild_v1")
controller = _load("ab16_formal_controller_v1")
_load("ab16_authority_v2", alias="ab16_authority_v2")
_load("ab16_outer_closeout_state_v1", alias="ab16_outer_closeout_state_v1")
_load("ab16_resource_admission_v1", alias="ab16_resource_admission_v1")
closeout = _load("ab16_outer_refunit_closeout_v1")
cut_free = _load("cut_free_incumbent_replay_v1")
arm_replay = _load("organic_arm_replay_v1")
lifecycle = _load("organic_resource_lifecycle_v2")
runner = _load("organic_arm_runner_v1")
verifier = _load("organic_resource_verifier_v2")


class _BudgetPublisher:
    def __init__(self, maxima: Mapping[str, tuple[str, int]]) -> None:
        self.maxima = dict(maxima)
        self.calls: list[dict[str, object]] = []

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        expected_class, maximum = self.maxima[label]
        assert artifact_class == expected_class
        return maximum

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]:
        assert maximum_bytes == self.maximum_bytes(label, artifact_class=artifact_class)
        assert len(raw) <= maximum_bytes
        absolute = Path(os.path.abspath(path))
        descriptor = os.open(
            absolute,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            assert os.write(descriptor, raw) == len(raw)
            os.fsync(descriptor)
            os.fchmod(descriptor, 0o444)
        finally:
            os.close(descriptor)
        identity = {
            "mode": 0o444,
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        self.calls.append(
            {
                "artifact_class": artifact_class,
                "identity": identity,
                "label": label,
                "maximum_bytes": maximum_bytes,
            }
        )
        return identity


class _BaselineBudget(_BudgetPublisher):
    def __init__(self, maxima: Mapping[str, tuple[str, int]]) -> None:
        super().__init__(maxima)
        self.directory_calls: list[dict[str, object]] = []
        self.confinement_calls: list[tuple[int, ...]] = []
        self.model_calls: list[dict[str, object]] = []

    @property
    def authority_binding(self) -> Mapping[str, object]:
        return {
            "filesystem_write_confinement": "landlock-read-only-worker-v1",
            "fixture": "formal-root",
        }

    def register_directory(
        self,
        path: Path,
        *,
        label: str,
        mode_octal: str,
    ) -> Mapping[str, object]:
        assert mode_octal in {"0500", "0700"}
        absolute = Path(os.path.abspath(path))
        if not absolute.exists():
            absolute.mkdir(mode=0o700)
        absolute.chmod(int(mode_octal, 8))
        metadata = absolute.stat()
        result = {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "mode_octal": mode_octal,
            "path": str(absolute),
        }
        self.directory_calls.append({"label": label, **result})
        return result

    def install_worker_confinement(
        self,
        retained_read_only_fds: Sequence[int],
    ) -> Mapping[str, object]:
        retained = tuple(sorted(retained_read_only_fds))
        self.confinement_calls.append(retained)
        return {
            "filesystem_write_confinement": "landlock-read-only-worker-v1",
            "retained_read_only_fds": list(retained),
            "root_or_staging_writable_fd_count": 0,
        }

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]:
        assert arm_slot is None
        assert sequence == 0
        assert maximum_bytes == self.maximum_bytes(
            "AB16 baseline cut segment",
            artifact_class=artifact_class,
        )
        return {
            "channel": channel,
            "sequence": sequence,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        assert model is _MODEL_SENTINEL
        expected_class, expected_maximum = self.maxima[label]
        assert expected_class == "model"
        assert maximum_bytes == expected_maximum
        raw = b"canonical-model"
        identity = {
            "path": str(Path(os.path.abspath(path))),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        self.model_calls.append({"label": label, **identity})
        return identity


_MODEL_SENTINEL = object()


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "mode": path.stat().st_mode & 0o777,
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _runner_snapshot(path: Path) -> Any:
    identity = _identity(path)
    identity.pop("mode")
    return runner.Snapshot(data=path.read_bytes(), identity=identity)


def _handoff(tmp_path: Path) -> dict[str, object]:
    helper = tmp_path / "native-helper.py"
    helper.write_bytes(b"helper\n")
    helper.chmod(0o400)
    formal = tmp_path / "campaign" / "formal-ab16" / "artifacts"
    attempt = formal / "arms" / "region-capacity-ab-control"
    socket_path = formal.parent / "control" / "budget-broker.sock"
    manager_credential = "c" * 64
    return {
        "arm_allocation_id": "a" * 64,
        "broker_actor_identity": {
            "pid": 1234,
            "pid_starttime": 5678,
            "uid": os.getuid(),
        },
        "broker_nonce": "b" * 64,
        "broker_socket_path": str(socket_path),
        "calibration_tool_content_identities": {
            role: {
                "sha256": f"{index:x}" * 64,
                "size_bytes": index,
            }
            for index, role in enumerate(
                sorted(lifecycle.CALIBRATION_TOOL_ROLES),
                start=1,
            )
        },
        "fixed_directory_layout": {
            "attempt_root": str(attempt),
            "channel_directories": {
                "arm-region-capacity-ab-control-cut-ledger": (
                    "arms/region-capacity-ab-control/ledger/cut-ledger"
                )
            },
            "directories": [
                {"mode": 0o700, "path": "arms"},
                {
                    "mode": 0o700,
                    "path": "arms/region-capacity-ab-control",
                },
                {
                    "mode": 0o700,
                    "path": "arms/region-capacity-ab-control/ledger",
                },
                {
                    "mode": 0o700,
                    "path": "arms/region-capacity-ab-control/ledger/cut-ledger",
                },
            ],
            "formal_root": str(formal),
        },
        "fixed_maxima": {
            "cut ledger segment": {
                "artifact_class": "ledger",
                "maximum_bytes": 4096,
            },
            "supervisor module-origin receipt": {
                "artifact_class": "metadata",
                "maximum_bytes": 65536,
            },
        },
        "formal_budget_authority_identity": _identity(helper),
        "manager_openfile_arm_grant": {
            "credential": manager_credential,
            "preregistration": {
                "allocation_identity": {
                    "sha256": "a" * 64,
                    "size_bytes": 4096,
                },
                "arm_slot": "region-capacity-ab-control",
                "attempt_consumption_identity": {
                    "path": str(
                        (
                            formal.parent
                            / "formal-attempt-a001"
                            / "attempt-consumption.json"
                        ).absolute()
                    ),
                    "sha256": "d" * 64,
                    "size_bytes": 4096,
                },
                "credential_sha256": hashlib.sha256(
                    manager_credential.encode("ascii")
                ).hexdigest(),
                "manager_epoch_identity": {
                    "sha256": "e" * 64,
                    "size_bytes": 4096,
                },
                "schema_version": lifecycle.MANAGER_OPENFILE_ARM_GRANT_SCHEMA,
                "selection_identity": {
                    "path": str(
                        (
                            formal.parent
                            / "formal-attempt-a001"
                            / "formal-selection-a001.json"
                        ).absolute()
                    ),
                    "sha256": "f" * 64,
                    "size_bytes": 4096,
                },
                "state": "UNBOUND",
                "unit_name": "ab16-organic-region-capacity-ab-control.service",
            },
        },
        "native_helper_package_identity": _identity(helper),
    }


def test_formal_budget_handoff_is_exact_and_attempt_bound(tmp_path: Path) -> None:
    handoff = _handoff(tmp_path)
    attempt = Path(handoff["fixed_directory_layout"]["attempt_root"])  # type: ignore[index]
    validated = lifecycle.validate_formal_budget_handoff(
        handoff,
        expected_attempt_root=attempt,
        expected_arm_slot="region-capacity-ab-control",
    )
    assert validated["arm_allocation_id"] == "a" * 64

    forged = json.loads(json.dumps(handoff))
    forged["fixed_directory_layout"]["attempt_root"] = str(tmp_path / "elsewhere")
    with pytest.raises(lifecycle.LifecycleError, match="attempt"):
        lifecycle.validate_formal_budget_handoff(
            forged,
            expected_attempt_root=attempt,
            expected_arm_slot="region-capacity-ab-control",
        )


@pytest.mark.parametrize(
    ("module", "function_name", "label", "artifact_class"),
    [
        (lifecycle, "write_json_exclusive", "lifecycle terminal", "closeout"),
        (verifier, "write_exclusive", "resource replay receipt", "publication"),
        (arm_replay, "write_exclusive", "organic arm replay receipt", "publication"),
    ],
)
def test_remaining_json_writers_use_explicit_budget_publisher(
    tmp_path: Path,
    module: Any,
    function_name: str,
    label: str,
    artifact_class: str,
) -> None:
    backend = _BudgetPublisher({label: (artifact_class, 65536)})
    output = tmp_path / f"{function_name}.json"
    identity = getattr(module, function_name)(
        output,
        {"status": "PASS"},
        budget_backend=backend,
        budget_label=label,
        artifact_class=artifact_class,
    )
    assert identity["path"] == str(output.absolute())
    assert len(backend.calls) == 1
    assert output.stat().st_mode & 0o777 == 0o444


def test_prospective_receipt_store_uses_only_fixed_broker_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "arm-prelaunch-request.json"
    label = "arm prelaunch request"
    backend = _BudgetPublisher({label: ("metadata", 65536)})
    store = closeout.ReceiptStore(
        budget_backend=backend,
        budget_bindings={
            str(output.absolute()): {
                "artifact_class": "metadata",
                "label": label,
            }
        },
    )
    monkeypatch.setattr(
        closeout.authority,
        "_write_exclusive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("prospective receipt used the direct writer")
        ),
    )
    identity = store.publish(output, {"status": "PASS"}, "arm request")
    assert identity["path"] == str(output.absolute())
    assert len(backend.calls) == 1
    with pytest.raises(
        closeout.OuterCloseoutError,
        match="not package-bound",
    ):
        store.publish(
            tmp_path / "unregistered.json",
            {"status": "PASS"},
            "unregistered receipt",
        )


def test_cut_free_receipt_uses_explicit_budget_publisher(tmp_path: Path) -> None:
    label = "cut-free incumbent replay receipt"
    backend = _BudgetPublisher({label: ("publication", 65536)})
    output = tmp_path / "cut-free.json"
    identity = cut_free._write_exclusive(  # noqa: SLF001 - exact writer regression
        output,
        cut_free._authority_json({"status": "PASS"}),  # noqa: SLF001
        budget_backend=backend,
        budget_label=label,
        artifact_class="publication",
    )
    assert identity["path"] == str(output.absolute())
    assert len(backend.calls) == 1


def _prospective_root(tmp_path: Path) -> Path:
    return tmp_path / "campaign/formal-ab16/artifacts/prospective"


def test_prospective_baseline_writers_cannot_fall_back_to_paths(
    tmp_path: Path,
) -> None:
    prospective = _prospective_root(tmp_path)
    baseline = prospective / "baseline"
    rebuild_argv = [
        "--output-dir",
        str(baseline),
        "--run-nonce",
        "fixture",
        "--campaign-provenance",
        str(baseline / "campaign-provenance.json"),
        "--candidate-placements",
        str(tmp_path / "candidate.json"),
        "--canonical-rules",
        str(tmp_path / "rules.json"),
        "--mandatory-instances",
        str(tmp_path / "mandatory.json"),
    ]
    with pytest.raises(
        baseline_rebuild.BaselineRebuildError,
        match="lacks its formal-root budget broker",
    ):
        baseline_rebuild.main(rebuild_argv)
    assert not baseline.exists()

    admission_path = prospective / "baseline-admission-a001.json"
    with pytest.raises(
        baseline_admission.AdmissionError,
        match="lacks its formal-root budget broker",
    ):
        baseline_admission.write_exclusive(
            admission_path,
            {"status": "PASS"},
        )
    assert not admission_path.exists()

    replay_argv = [
        "--campaign-provenance",
        str(tmp_path / "campaign-provenance.json"),
        "--model",
        str(tmp_path / "model.bin"),
        "--metadata",
        str(tmp_path / "metadata.json"),
        "--incumbent",
        str(tmp_path / "incumbent.json"),
        "--output",
        str(baseline / "fixed-replay-a001.json"),
    ]
    with pytest.raises(
        cut_free.ReplayError,
        match="lacks its formal-root budget broker",
    ):
        cut_free.main(replay_argv, emit_summary=False)
    assert not (baseline / "fixed-replay-a001.json").exists()


def test_baseline_budget_workspace_and_model_use_fixed_broker_capabilities(
    tmp_path: Path,
) -> None:
    baseline = _prospective_root(tmp_path) / "baseline"
    baseline.mkdir(parents=True)
    backend = _BaselineBudget(
        {
            "AB16 baseline rebuilt model": ("model", 4096),
            "AB16 baseline cut segment": ("ledger", 4096),
        }
    )
    workspace = baseline_rebuild._prepare_budget_workspace(  # noqa: SLF001
        baseline,
        backend,
    )
    try:
        workspace.verify()
        assert [call["label"] for call in backend.directory_calls] == [
            "AB16 baseline tmp directory",
            "AB16 baseline checkpoint directory",
            "AB16 baseline cut channel directory",
            "AB16 baseline tmp directory",
            "AB16 baseline checkpoint directory",
        ]
        assert not list(workspace.tmp_path.iterdir())
        assert [member.name for member in workspace.checkpoint_path.iterdir()] == [
            "benders-cuts"
        ]
        assert workspace.tmp_path.stat().st_mode & 0o777 == 0o500
        assert workspace.checkpoint_path.stat().st_mode & 0o777 == 0o500
        for parent in (workspace.tmp_path, workspace.checkpoint_path):
            with pytest.raises(PermissionError):
                descriptor = os.open(
                    parent / "forbidden",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                    0o600,
                )
                os.close(descriptor)
        segment = backend.append_segment(
            baseline_rebuild.BASELINE_CUT_CHANNEL,
            0,
            b"immutable-cut-segment\n",
            maximum_bytes=backend.maximum_bytes(
                "AB16 baseline cut segment",
                artifact_class="ledger",
            ),
            artifact_class="ledger",
        )
        assert segment["size_bytes"] == len(b"immutable-cut-segment\n")
        identity = baseline_rebuild._publish_budgeted_model(  # noqa: SLF001
            backend,
            _MODEL_SENTINEL,
            baseline / "cut-free-model.bin",
            b"canonical-model",
        )
        assert identity["sha256"] == hashlib.sha256(b"canonical-model").hexdigest()
        assert backend.model_calls == [
            {
                "label": "AB16 baseline rebuilt model",
                **identity,
            }
        ]
        assert not (baseline / "cut-free-model.bin").exists()
    finally:
        workspace.close()


def test_prospective_baseline_main_installs_confinement_before_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _prospective_root(tmp_path) / "baseline"
    baseline.mkdir(parents=True)
    provenance = baseline / "campaign-provenance.json"
    provenance_record = {"snapshot_root": str(tmp_path)}
    provenance.write_bytes(
        baseline_rebuild.baseline_contract.canonical_json(provenance_record)
    )
    provenance.chmod(0o444)
    monkeypatch.setattr(
        baseline_rebuild,
        "_campaign_provenance",
        lambda path: (
            dict(provenance_record)
            if Path(path) == provenance
            else pytest.fail("unexpected provenance path")
        ),
    )
    backend = _BaselineBudget(
        {
            "AB16 baseline rebuilt model": ("model", 4096),
            "AB16 baseline cut segment": ("ledger", 4096),
        }
    )

    def no_solver(
        _args: object,
        _state: object,
        *,
        budget_backend: object,
        budget_workspace: object,
    ) -> int:
        assert budget_backend is backend
        assert budget_workspace is not None
        assert len(backend.confinement_calls) == 1
        for parent in (baseline / "tmp", baseline / "checkpoint"):
            assert parent.stat().st_mode & 0o777 == 0o500
            with pytest.raises(PermissionError):
                descriptor = os.open(
                    parent / "runner-write-forbidden",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                    0o600,
                )
                os.close(descriptor)
        return 0

    monkeypatch.setattr(baseline_rebuild, "_run_rebuild", no_solver)
    argv = [
        "--output-dir",
        str(baseline),
        "--run-nonce",
        "fixture",
        "--campaign-provenance",
        str(provenance),
        "--candidate-placements",
        str(tmp_path / "candidate.json"),
        "--canonical-rules",
        str(tmp_path / "rules.json"),
        "--mandatory-instances",
        str(tmp_path / "mandatory.json"),
    ]
    assert baseline_rebuild.main(argv, budget_backend=backend) == 0
    assert len(backend.confinement_calls[0]) == 4


def test_prospective_baseline_admission_uses_fixed_label_and_path(
    tmp_path: Path,
) -> None:
    prospective = _prospective_root(tmp_path)
    prospective.mkdir(parents=True)
    label = "AB16 baseline admission"
    backend = _BudgetPublisher({label: ("publication", 65536)})
    output = prospective / "baseline-admission-a001.json"
    identity = baseline_admission.write_exclusive(
        output,
        {"status": "PASS"},
        budget_backend=backend,
    )
    assert identity["path"] == str(output.absolute())
    assert [call["label"] for call in backend.calls] == [label]


def test_baseline_fixed_replay_uses_distinct_fixed_label(tmp_path: Path) -> None:
    baseline = _prospective_root(tmp_path) / "baseline"
    baseline.mkdir(parents=True)
    label = "AB16 baseline fixed replay"
    backend = _BudgetPublisher({label: ("publication", 65536)})
    output = baseline / "fixed-replay-a001.json"
    identity = cut_free._write_exclusive(  # noqa: SLF001
        output,
        cut_free._authority_json({"status": "PASS"}),  # noqa: SLF001
        budget_backend=backend,
        budget_label=label,
        artifact_class="publication",
    )
    assert identity["path"] == str(output.absolute())
    assert [call["label"] for call in backend.calls] == [label]


def test_runner_executes_package_pinned_cut_free_producer_with_arm_budget(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "formal" / "arms" / "region-capacity-ab-control"
    (attempt / "replays").mkdir(parents=True)
    incumbent = {"instance": {"pose_idx": 0}}
    incumbent_path = attempt / "raw-incumbent.json"
    incumbent_path.write_bytes(runner.canonical_json(incumbent))
    incumbent_identity = _identity(incumbent_path)
    incumbent_identity.pop("mode")

    baseline = tmp_path / "formal" / "baseline"
    baseline.mkdir()
    model = baseline / "cut-free-model.bin"
    metadata = baseline / "rebuilt-model-metadata.json"
    model.write_bytes(b"model")
    metadata.write_bytes(b"metadata")
    admission_tool = tmp_path / "package" / "baseline_admission_v1.py"
    admission_tool.parent.mkdir()
    admission_tool.write_bytes(b"PACKAGE_PIN = 'baseline-admission-fixture'\n")
    cut_free_tool = tmp_path / "package" / "cut_free_incumbent_replay_v1.py"
    cut_free_tool.write_text(
        "\n".join(
            (
                "import hashlib",
                "import json",
                "from pathlib import Path",
                "import baseline_admission_v1 as baseline_contract",
                "",
                "def main(argv, *, budget_backend, expected_incumbent_sha256, emit_summary):",
                "    del emit_summary",
                "    args = dict(zip(argv[::2], argv[1::2], strict=True))",
                "    incumbent_path = Path(args['--incumbent'])",
                "    value = json.loads(incumbent_path.read_bytes())",
                "    canonical = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()",
                "    assert hashlib.sha256(canonical).hexdigest() == expected_incumbent_sha256",
                "    tool_raw = Path(__file__).read_bytes()",
                "    receipt = {",
                "        'incumbent_identity': {",
                "            'path': str(incumbent_path.absolute()),",
                "            'sha256': hashlib.sha256(incumbent_path.read_bytes()).hexdigest(),",
                "            'size_bytes': len(incumbent_path.read_bytes()),",
                "        },",
                "        'incumbent_sha256': expected_incumbent_sha256,",
                "        'replay_tool_identity': {",
                "            'path': str(Path(__file__).absolute()),",
                "            'sha256': hashlib.sha256(tool_raw).hexdigest(),",
                "            'size_bytes': len(tool_raw),",
                "        },",
                "        'status': 'PASS',",
                "        'verdict': 'INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS',",
                "    }",
                "    raw = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode() + b'\\n'",
                "    maximum = budget_backend.maximum_bytes(",
                "        'cut-free incumbent replay receipt', artifact_class='publication'",
                "    )",
                "    budget_backend.publish_bytes(",
                "        Path(args['--output']), raw, maximum_bytes=maximum,",
                "        artifact_class='publication', label='cut-free incumbent replay receipt'",
                "    )",
                "    return 0",
                "",
            )
        ),
        encoding="utf-8",
    )
    inputs = runner.PinnedCutFreeReplayInputs(
        admission={
            "fixed_assignment_replay": {
                "incumbent_identity": incumbent_identity,
            },
            "rebuilt_model": {
                "identity": {
                    **_identity(model),
                    "mode": 0o600,
                },
                "metadata": {
                    "metadata_identity": {
                        **_identity(metadata),
                        "mode": 0o600,
                    },
                },
            },
        },
        admission_tool=_runner_snapshot(admission_tool),
        cut_free_tool=_runner_snapshot(cut_free_tool),
    )
    for nested in (
        inputs.admission["rebuilt_model"]["identity"],  # type: ignore[index]
        inputs.admission["rebuilt_model"]["metadata"]["metadata_identity"],  # type: ignore[index]
    ):
        nested.pop("mode")  # type: ignore[union-attr]
    backend = _BudgetPublisher(
        {"cut-free incumbent replay receipt": ("publication", 65536)}
    )
    previous_alias = sys.modules.pop("baseline_admission_v1", None)
    try:
        identity = runner._publish_cut_free_incumbent_replay(  # noqa: SLF001
            attempt_dir=attempt,
            incumbent_identity=incumbent_identity,
            incumbent_value=incumbent,
            inputs=inputs,
            budget_backend=backend,
        )
    finally:
        if previous_alias is not None:
            sys.modules["baseline_admission_v1"] = previous_alias
    assert identity["path"] == str(
        (attempt / "replays" / "cut-free-incumbent.json").absolute()
    )
    assert [call["label"] for call in backend.calls] == [
        "cut-free incumbent replay receipt"
    ]


def test_supervisor_module_origin_receipt_has_a_real_budgeted_producer(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    output = attempt / "supervisor-module-origin-receipt.json"
    label = "supervisor module-origin receipt"
    backend = _BudgetPublisher({label: ("metadata", 65536)})
    pre_run = {
        "attempt_dir": str(attempt),
        "execution_class": "FORMAL_AB16",
        "launch": {
            "execution_source": {
                "import_mode": "ordinary_pathfinder",
                "sealed_snapshot_execution_root": str(ROOT),
            }
        },
        "output_paths": {"supervisor_module_origin": str(output)},
        "package": {"package_id": "c" * 64},
        "slot": "region-capacity-ab-control",
    }
    receipt = lifecycle.publish_supervisor_module_origin_receipt(
        pre_run,
        budget_backend=backend,
        module_origins={"organic_resource_lifecycle_v2": str(Path(lifecycle.__file__).absolute())},
        output_path=output,
        supervisor_tool_identity=_identity(Path(lifecycle.__file__)),
    )
    assert receipt["schema_version"] == lifecycle.SUPERVISOR_MODULE_ORIGIN_RECEIPT_SCHEMA
    assert receipt["status"] == "PASS"
    assert len(backend.calls) == 1


def test_formal_controller_result_cannot_bypass_budget(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    formal.mkdir()
    label = "formal controller result"
    backend = _BudgetPublisher({label: ("publication", 1 << 20)})
    inputs = controller.FormalInputs(
        context={
            "campaign_root_identity": {
                "path": str(tmp_path / "root.json"),
                "sha256": "1" * 64,
                "size_bytes": 1,
            },
            "formal_attempt_dir": str(formal),
            "package_id": "2" * 64,
        },
        guardian_process_identity={"pid": 1, "pid_starttime": 1, "uid": os.getuid()},
        supervisor_process_identity={"pid": 2, "pid_starttime": 2, "uid": os.getuid()},
        selection={},
        selection_identity={
            "path": str(tmp_path / "selection.json"),
            "sha256": "3" * 64,
            "size_bytes": 1,
        },
    )
    arms: list[dict[str, object]] = [
        {"suite_terminal_identity": None}
        for _slot in controller.ARM_SEQUENCE
    ]
    arms[-1]["suite_terminal_identity"] = {
        "path": str(tmp_path / "terminal.json"),
        "sha256": "4" * 64,
        "size_bytes": 1,
    }
    _result, identity = controller._publish_controller_result(  # noqa: SLF001
        inputs,
        barrier_identity={"path": "barrier", "sha256": "5" * 64, "size_bytes": 1},
        gate1={},
        baseline={},
        manifest_identity={"path": "manifest", "sha256": "6" * 64, "size_bytes": 1},
        suite_selection_identity={
            "path": "suite",
            "sha256": "7" * 64,
            "size_bytes": 1,
        },
        arms=arms,
        budget_backend=backend,
    )
    assert identity["path"] == str((formal / controller.CONTROLLER_RESULT_NAME).absolute())
    assert len(backend.calls) == 1


def test_formal_orchestration_without_budget_fails_before_effects() -> None:
    with pytest.raises(Exception, match="budget"):
        controller.run_controller(
            campaign_dir="/nonexistent",
            formal_selection="/nonexistent",
            ports=None,
            budget_backend=None,
        )
