from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AB16_BOOTSTRAP_RELATIVE = Path(
    "docs/research/noncert_cuts_ab16_20260724/ab16_campaign_bootstrap_v1.py"
)
SELECTED_EXECUTION_ROLE = "gate1_campaign_execution_v4"
SELECTED_CHECKER_ROLE = "independent_arithmetic_v4"
PACKAGE_EXECUTION_MEMBER = "payload/tool.gate1_campaign_execution_v4.py"
PACKAGE_CHECKER_MEMBER = "payload/tool.independent_arithmetic_v4.py"
HISTORICAL_FROZEN_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
R13_BASE_HEAD = "3c4ff6b135ec8297cc7af1d642c609e352b29879"
T0 = "2026-08-03T07:00:00Z"
T1 = "2026-08-03T07:01:00Z"
UNIT_SLOTS = {
    "forced-control",
    "forced-treatment",
    "q-postseal-fail",
    "q-success",
}


def _subprocess_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        list(arguments),
        cwd=cwd,
        check=False,
        env=_subprocess_environment(),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    assert completed.returncode == 0, (
        f"command failed: {arguments!r}\n"
        f"stdout={completed.stdout.decode(errors='replace')}\n"
        f"stderr={completed.stderr.decode(errors='replace')}"
    )
    return completed


def _run_json(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float,
) -> dict[str, Any]:
    completed = _run(arguments, cwd=cwd, timeout=timeout)
    assert completed.stderr == b""
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not emit one JSON value: {arguments!r}") from exc
    assert type(value) is dict
    return value


def _hash_size(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _assert_identity(identity: Mapping[str, object]) -> Path:
    assert set(identity) == {"path", "sha256", "size_bytes"}
    path = Path(str(identity["path"]))
    assert path.is_absolute()
    assert _hash_size(path) == (identity["size_bytes"], identity["sha256"])
    return path


def _load_identity_json(identity: Mapping[str, object]) -> dict[str, Any]:
    path = _assert_identity(identity)
    value = json.loads(path.read_bytes())
    assert type(value) is dict
    return value


def _git_head(checkout: Path) -> str:
    completed = _run(("/usr/bin/git", "rev-parse", "--verify", "HEAD"), cwd=checkout)
    assert completed.stderr == b""
    assert len(completed.stdout) == 41 and completed.stdout.endswith(b"\n")
    head = completed.stdout[:-1].decode("ascii")
    assert len(head) == 40 and all(character in "0123456789abcdef" for character in head)
    return head


def _clean_checkout(tmp_path: Path) -> Path:
    """Materialize the reviewed bytes as one clean, ordinary fresh-HEAD checkout."""

    checkout = tmp_path / "checkout"
    _run(("/usr/bin/git", "clone", "--no-local", "--quiet", str(ROOT), str(checkout)))
    patch = _run(("/usr/bin/git", "diff", "--binary", "HEAD", "--"), cwd=ROOT).stdout
    if patch:
        _run(
            ("/usr/bin/git", "apply", "--binary", "--whitespace=nowarn", "-"),
            cwd=checkout,
            input_bytes=patch,
        )

    # The 54 MB candidate set is deliberately absent from lightweight clones.
    # Restore only that ignored file, and only after replaying its tracked pin.
    manifest = json.loads((checkout / "data/external_artifacts.json").read_bytes())
    entries = [entry for entry in manifest["artifacts"] if entry.get("id") == "candidate_placements"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["path"] == "data/preprocessed/candidate_placements.json"
    expected = (
        54_467_709,
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    )
    assert (entry["size_bytes"], entry["sha256"]) == expected
    candidate_source = ROOT / entry["path"]
    candidate_target = checkout / entry["path"]
    assert _hash_size(candidate_source) == expected
    candidate_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_source, candidate_target)
    assert _hash_size(candidate_target) == expected

    _run(("/usr/bin/git", "add", "-A"), cwd=checkout)
    staged = subprocess.run(
        ("/usr/bin/git", "diff", "--cached", "--quiet"),
        cwd=checkout,
        check=False,
        env=_subprocess_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert staged.returncode in {0, 1} and staged.stderr == b""
    if staged.returncode == 1:
        _run(
            (
                "/usr/bin/git",
                "-c",
                "user.name=AB16 R13 Sentinel",
                "-c",
                "user.email=ab16-r13-sentinel.invalid",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "--quiet",
                "-m",
                "test(ab16): materialize r13 fresh-head sentinel checkout",
            ),
            cwd=checkout,
        )

    tracked_candidate = subprocess.run(
        ("/usr/bin/git", "ls-files", "--error-unmatch", entry["path"]),
        cwd=checkout,
        check=False,
        env=_subprocess_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert tracked_candidate.returncode == 1
    _run(("/usr/bin/git", "check-ignore", "--quiet", entry["path"]), cwd=checkout)
    assert _run(("/usr/bin/git", "status", "--porcelain=v1"), cwd=checkout).stdout == b""
    return checkout


def _system_tools() -> dict[str, Path]:
    tools = {
        "attestor_python": Path("/usr/bin/python3.14"),
        "busctl": Path("/usr/bin/busctl"),
        "git": Path("/usr/bin/git"),
        "python3_13": (ROOT / ".venv-uvbolt-backup/bin/python").absolute(),
        "sudo": Path("/usr/bin/sudo"),
        "systemctl": Path("/usr/bin/systemctl"),
        "systemd_run": Path("/usr/bin/systemd-run"),
    }
    assert all(path.is_file() for path in tools.values())
    return tools


def _bootstrap_arguments(
    *,
    command: str,
    checkout: Path,
    campaign_dir: Path,
    created_at_utc: str,
    tools: Mapping[str, Path],
) -> list[str]:
    return [
        str(tools["python3_13"]),
        str(checkout / AB16_BOOTSTRAP_RELATIVE),
        command,
        "--campaign-dir",
        str(campaign_dir),
        "--repository-root",
        str(checkout),
        "--created-at-utc",
        created_at_utc,
        "--python3-13",
        str(tools["python3_13"]),
        "--attestor-python",
        str(tools["attestor_python"]),
        "--busctl",
        str(tools["busctl"]),
        "--git",
        str(tools["git"]),
        "--sudo",
        str(tools["sudo"]),
        "--systemctl",
        str(tools["systemctl"]),
        "--systemd-run",
        str(tools["systemd_run"]),
    ]


def _authority_arguments(
    *,
    command: str,
    python: Path,
    execution: Path,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> list[str]:
    return [
        str(python),
        str(execution),
        command,
        "--formal-authorized",
        "--campaign-root",
        str(campaign_root_identity["path"]),
        "--campaign-root-size",
        str(campaign_root_identity["size_bytes"]),
        "--campaign-root-sha256",
        str(campaign_root_identity["sha256"]),
        "--selection",
        str(selection_identity["path"]),
        "--selection-size",
        str(selection_identity["size_bytes"]),
        "--selection-sha256",
        str(selection_identity["sha256"]),
    ]


def _parse_seal(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    entries: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        digest, separator, relative = line.partition("  ")
        assert separator == "  "
        assert len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)
        assert relative and relative not in entries
        entries[relative] = digest
    return entries


def _assert_package_member_join(
    *,
    manifest: Mapping[str, object],
    seal: Mapping[str, str],
    relative_path: str,
    selected_identity: Mapping[str, object],
) -> None:
    path = _assert_identity(selected_identity)
    assert path.as_posix().endswith(f"/{relative_path}")
    assert seal[relative_path] == selected_identity["sha256"]
    members = [member for member in manifest["package_members"] if member.get("path") == relative_path]
    assert members == [
        {
            "path": relative_path,
            "sha256": selected_identity["sha256"],
            "size_bytes": selected_identity["size_bytes"],
        }
    ]
    sources = [source for source in manifest["external_sources"] if source.get("package_path") == relative_path]
    assert len(sources) == 1
    assert sources[0]["source_identity"]["sha256"] == selected_identity["sha256"]
    assert sources[0]["source_identity"]["size_bytes"] == selected_identity["size_bytes"]


def _cleanup_test_units(systemctl: Path, unit_names: Sequence[str]) -> None:
    for unit_name in unit_names:
        for action in ("stop", "reset-failed"):
            subprocess.run(
                (str(systemctl), "--user", action, unit_name),
                check=False,
                env=_subprocess_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )


def test_fresh_clean_head_reaches_real_package_pinned_assemble_formal(tmp_path: Path) -> None:
    """Run candidate -> bootstrap -> all three production Gate-1 execution stages."""

    checkout = _clean_checkout(tmp_path)
    fresh_head = _git_head(checkout)
    assert fresh_head not in {HISTORICAL_FROZEN_HEAD, R13_BASE_HEAD}
    tools = _system_tools()
    candidate_path = tmp_path / "offline-candidate.json"
    campaign_dir = tmp_path / "run-r13-gate1-freshhead-production-sentinel"
    unit_names: list[str] = []
    try:
        candidate = _run_json(
            [
                *_bootstrap_arguments(
                    command="candidate",
                    checkout=checkout,
                    campaign_dir=campaign_dir,
                    created_at_utc=T0,
                    tools=tools,
                ),
                "--candidate-output",
                str(candidate_path),
            ],
            cwd=checkout,
            timeout=180,
        )
        assert candidate["formal_campaign_created"] is False
        assert candidate["candidate"]["candidate_only"] is True
        assert candidate["candidate"]["repository_head"] == fresh_head
        assert not campaign_dir.exists()

        bootstrap = _run_json(
            [
                *_bootstrap_arguments(
                    command="bootstrap",
                    checkout=checkout,
                    campaign_dir=campaign_dir,
                    created_at_utc=T1,
                    tools=tools,
                ),
                "--offline-candidate",
                str(candidate_path),
            ],
            cwd=checkout,
            timeout=240,
        )
        assert bootstrap["status"] == "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
        assert bootstrap["repository_head"] == fresh_head
        assert bootstrap["formal_arm_launch_authorized"] is False
        assert bootstrap["organic_ab16_authorized"] is False

        root_identity = bootstrap["campaign_root_identity"]
        selection_identity = bootstrap["gate1_selection_identity"]
        root = _load_identity_json(root_identity)
        selection = _load_identity_json(selection_identity)
        assert root["repository_head"] == selection["repository_head"] == fresh_head
        assert selection["campaign_root_identity"] == root_identity
        assert selection["package_id"] == root["package"]["package_id"] == bootstrap["package_id"]
        assert set(selection["units"]) == UNIT_SLOTS
        unit_names = [selection["units"][slot]["unit_name"] for slot in sorted(UNIT_SLOTS)]

        package_dir = Path(root["package"]["package_dir"])
        manifest_identity = root["package"]["manifest_identity"]
        manifest = _load_identity_json(manifest_identity)
        seal_path = _assert_identity(root["package"]["seal_identity"])
        seal = _parse_seal(seal_path)
        assert hashlib.sha256(seal_path.read_bytes()).hexdigest() == bootstrap["package_id"]
        assert manifest["repository_head"] == fresh_head
        assert seal["package-manifest.json"] == manifest_identity["sha256"]

        execution_identity = selection["tools"][SELECTED_EXECUTION_ROLE]
        checker_identity = selection["tools"][SELECTED_CHECKER_ROLE]
        execution_path = _assert_identity(execution_identity)
        assert execution_path == package_dir / PACKAGE_EXECUTION_MEMBER
        _assert_package_member_join(
            manifest=manifest,
            seal=seal,
            relative_path=PACKAGE_EXECUTION_MEMBER,
            selected_identity=execution_identity,
        )
        _assert_package_member_join(
            manifest=manifest,
            seal=seal,
            relative_path=PACKAGE_CHECKER_MEMBER,
            selected_identity=checker_identity,
        )

        common = {
            "python": Path(selection["tools"]["python3_13"]["path"]),
            "execution": execution_path,
            "campaign_root_identity": root_identity,
            "selection_identity": selection_identity,
        }
        prepared = _run_json(
            _authority_arguments(command="prepare-formal", **common),
            cwd=checkout,
            timeout=180,
        )
        assert prepared["mode"] == "formal"
        assert prepared["both_bindings_sealed_before_arms"] is True
        assert prepared["formal_publication_authorized"] is True

        orchestrated = _run_json(
            _authority_arguments(command="orchestrate-formal", **common),
            cwd=checkout,
            timeout=360,
        )
        assert set(orchestrated) == UNIT_SLOTS

        assembled = _run_json(
            _authority_arguments(command="assemble-formal", **common),
            cwd=checkout,
            timeout=180,
        )
        assert assembled["mode"] == "formal"
        assert assembled["gate_written"] is True
        assert assembled["continuation_written"] is True
        assert assembled["campaign_closed"] is False
        assert assembled["organic_arm_launch_authorized"] is False

        gate = _load_identity_json(assembled["gate_identity"])
        continuation = _load_identity_json(assembled["continuation_identity"])
        assert gate["status"] == "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS"
        assert gate["repository_head"] == fresh_head
        assert gate["repository_identity_join"] == {
            "checker_package_birth_head": fresh_head,
            "checker_receipt_package_birth_joined": True,
            "checker_selected_package_member_joined": True,
            "gate1_selection_execution_head": fresh_head,
            "selection_live_execution_joined": True,
            "tracked_checkout_clean": True,
        }
        assert gate["prospective_ab16_slots_absent"] is True
        assert continuation["continuation_authorized"] is True
        assert continuation["campaign_closed"] is False
        assert continuation["organic_arm_launch_authorized"] is False
        assert continuation["gate1_result_identity"] == assembled["gate_identity"]

        # First close the checker's package-birth join, then the selection's
        # live-execution join.  Neither HEAD is accepted as a caller echo.
        arithmetic = _load_identity_json(gate["positive_control"]["arithmetic"])
        pair_selection = _load_identity_json(gate["positive_control"]["pair_selection"])
        assert arithmetic["repository_head"] == manifest["repository_head"] == fresh_head
        assert pair_selection["repository_head"] == selection["repository_head"] == _git_head(checkout)

        # Gate 1 qualification must not create or impersonate any AB16 attempt.
        assert not (campaign_dir / "prospective-ab16").exists()
        assert _run(("/usr/bin/git", "status", "--porcelain=v1"), cwd=checkout).stdout == b""
    finally:
        _cleanup_test_units(tools["systemctl"], unit_names)
