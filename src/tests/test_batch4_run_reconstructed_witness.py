from __future__ import annotations

import json
from pathlib import Path

import pytest

from docs.research.front_offset_incident_20260718.batch4_harness import (
    run_reconstructed_witness as _RUNNER,
)


def test_greedy_mapping_is_explicit_and_skips_binding_by_default(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    argv, seed = _RUNNER._build_historical_argv(
        arm="greedy",
        result_path=result_path,
        ghost_x=9,
        ghost_y=10,
        ghost_w=5,
        ghost_h=4,
        seed=17,
    )

    assert argv == [
        "--ghost-x",
        "9",
        "--ghost-y",
        "10",
        "--ghost-w",
        "5",
        "--ghost-h",
        "4",
        "--seed",
        "17",
        "--skip-binding",
        "--out",
        str(result_path),
    ]
    assert seed == 17


def test_comb_mapping_omits_unsupported_seed_and_allows_binding_opt_in(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    argv, seed = _RUNNER._build_historical_argv(
        arm="comb",
        result_path=result_path,
        with_binding=True,
    )

    assert argv == [
        "--ghost-x",
        "1",
        "--ghost-y",
        "1",
        "--ghost-w",
        "6",
        "--ghost-h",
        "7",
        "--out",
        str(result_path),
    ]
    assert seed is None
    with pytest.raises(ValueError, match="does not accept --seed"):
        _RUNNER._build_historical_argv(
            arm="comb",
            result_path=result_path,
            seed=1,
        )


def test_skyline_defaults_pin_historical_seed_zero(tmp_path: Path) -> None:
    argv, seed = _RUNNER._build_historical_argv(
        arm="skyline",
        result_path=tmp_path / "result.json",
    )

    assert argv[:8] == [
        "--ghost-x",
        "62",
        "--ghost-y",
        "2",
        "--ghost-w",
        "6",
        "--ghost-h",
        "7",
    ]
    assert argv[8:10] == ["--seed", "0"]
    assert seed == 0


def test_existing_output_directory_is_always_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError, match="refusing to reuse"):
        _RUNNER._validate_new_output_dir(tmp_path)

    new_path = tmp_path / "new-run"
    _RUNNER._validate_new_output_dir(new_path)


def test_manifest_helper_records_reconstructed_provenance_and_serializes_stably(
    tmp_path: Path,
) -> None:
    record = _RUNNER._build_run_record(
        arm="greedy",
        revision={"commit": "a" * 40, "dirty": True},
        command=["/python", "/runner", "_child"],
        historical_argv=["--seed", "0", "--out", "/run/result.json"],
        source_sha256s={"old.py": {"sha256": "1" * 64, "size_bytes": 1}},
        input_sha256s={"input.json": {"sha256": "2" * 64, "size_bytes": 2}},
        seed=0,
        hash_seed=0,
        with_binding=False,
        wall_seconds=1.23456789,
        exit_code=0,
        outputs={
            "result": {
                "filename": "result.json",
                "exists": True,
                "sha256": "3" * 64,
                "size_bytes": 3,
            }
        },
    )

    assert record["schema"] == "batch4.reconstructed_witness_run_record.v1"
    assert record["source"] == "reconstructed_new_baseline"
    assert record["binding_enabled"] is False
    assert record["front_semantics"]["construction"].endswith("runtime_zero_delta")
    assert record["execution"]["command"] == ["/python", "/runner", "_child"]
    assert record["execution"]["historical_argv"] == [
        "--seed",
        "0",
        "--out",
        "/run/result.json",
    ]
    assert record["execution"]["stdout_filename"] == "stdout.txt"
    assert record["execution"]["stderr_filename"] == "stderr.txt"
    assert record["execution"]["wall_seconds"] == 1.234568

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _RUNNER._write_canonical_json(first, record)
    _RUNNER._write_canonical_json(second, record)
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8")) == record
