from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_strong_status_write_allowlist.py"


def _run_checker(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _empty_allowlist(path: Path) -> None:
    _write_json(path, {"schema_version": 1, "allowlist": []})


def test_current_tree_strong_status_allowlist_passes() -> None:
    result = _run_checker()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "strong-status write allowlist check passed" in result.stdout


def test_unregistered_final_result_write_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_final_result.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(state):\n'
        '    state["final_result"] = {"search_status": "CERTIFIED"}\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        '(src/search/rogue_final_result.py,2,state_key_write,forge,'
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_last_stop_reason_status_write_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_last_stop_reason.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(state):\n'
        '    state["last_stop_reason"] = {"status": "CERTIFIED"}\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        '(src/search/rogue_last_stop_reason.py,2,state_key_write,forge,'
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_mark_campaign_stopped_certified_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_stop.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def stop(campaign):\n'
        '    campaign.mark_campaign_stopped("bad", status="CERTIFIED")\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        '(src/search/rogue_stop.py,2,mark_campaign_stopped,stop,'
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_getattr_verified_producer_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_getattr_producer.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(campaign):\n'
        '    writer = getattr(campaign, "_mark_candidate_result_from_verified_producer")\n'
        '    writer(1, 2, "CERTIFIED")\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_getattr_producer.py,2,verified_producer_reference,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout
    assert (
        "(src/search/rogue_getattr_producer.py,3,verified_producer_reference,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_alias_verified_producer_call_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_alias_producer.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(campaign):\n'
        '    writer = campaign._mark_candidate_result_from_verified_producer\n'
        '    writer(1, 2, "CERTIFIED")\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_alias_producer.py,2,verified_producer_reference,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout
    assert (
        "(src/search/rogue_alias_producer.py,3,verified_producer_reference,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_dynamic_state_key_write_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_dynamic_state_key.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(state):\n'
        '    key = "final_result"\n'
        '    state[key] = {"search_status": "CERTIFIED"}\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_dynamic_state_key.py,3,state_key_write_dynamic,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_final_status_variable_value_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_final_status_value.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(state, status):\n'
        '    state["final_status"] = status\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_final_status_value.py,2,state_key_write,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_record_update_status_certified_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_record_update.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(record):\n'
        '    record.update({"status": "CERTIFIED"})\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_record_update.py,2,candidate_status,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_state_update_unpack_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_state_update_unpack.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(state, payload):\n'
        '    state.update(**payload)\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_state_update_unpack.py,2,state_key_write_dynamic,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_dict_final_status_constructor_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_dict_constructor.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(status):\n'
        '    return dict(final_status=status)\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_dict_constructor.py,2,state_key_write,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_setattr_final_status_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_setattr.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(obj, status):\n'
        '    setattr(obj, "final_status", status)\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_setattr.py,2,state_key_write,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_unregistered_export_certified_blueprint_call_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "rogue_export.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def forge(project_root):\n'
        '    export_certified_blueprint(project_root=project_root, result={}, facility_pools={})\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _empty_allowlist(allowlist)

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert (
        "(src/search/rogue_export.py,2,artifact_write,forge,"
        '"unregistered strong-status write")'
    ) in result.stdout


def test_allowlist_source_sha256_drift_fails(tmp_path: Path) -> None:
    src_file = tmp_path / "src" / "search" / "allowed.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        'def ok(state):\n'
        '    state["final_result"] = {"search_status": "CERTIFIED"}\n',
        encoding="utf-8",
    )
    allowlist = tmp_path / "allowlist.json"
    _write_json(
        allowlist,
        {
            "schema_version": 1,
            "allowlist": [
                {
                    "pattern": "state_key_write",
                    "module": "src/search/allowed.py",
                    "qualname": "ok",
                    "line": 2,
                    "keys": ["final_result"],
                    "source_sha256": "0" * 64,
                }
            ],
        },
    )

    result = _run_checker("--root", str(tmp_path), "--allowlist", str(allowlist))

    assert result.returncode != 0
    assert "allowlist source_sha256 mismatch" in result.stdout
