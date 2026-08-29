#!/usr/bin/env python3
"""Cold-start and structural checks for the ZMD research worktree.

This tool is intentionally standard-library-only. It checks attention-routing
invariants, not mathematical soundness, solver correctness, or certification.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
MODE_PATH = ROOT / ".zmd-worktree-mode"

REQUIRED_MODE_KEYS = frozenset(
    {
        "schema",
        "mode",
        "scope",
        "branch",
        "entry",
        "program",
        "architecture",
        "attention",
        "checks",
        "state",
        "active_campaign",
        "active_campaign_file",
        "history_tree",
        "history_branch",
        "certification_tree",
        "certification_branch",
        "certification_branch_prefix",
        "python",
        "local_root",
        "cc_memory_directory",
        "cc_memory_settings",
        "cc_memory_seed",
        "cc_memory_migration",
        "cc_memory_receipt",
        "promotion_policy",
    }
)


@dataclass
class CheckReport:
    info: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_git(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_mode_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected key=value")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"{path}:{line_number}: empty key or value")
        if key in values:
            raise ValueError(f"{path}:{line_number}: duplicate key {key!r}")
        values[key] = value
    return values


def path_from_mode(mode: dict[str, str], key: str) -> Path:
    value = mode[key]
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def is_tracked(relative_path: str) -> bool:
    result = run_git(["ls-files", "--error-unmatch", "--", relative_path], check=False)
    return result.returncode == 0


def is_ignored(relative_path: str) -> bool:
    result = run_git(["check-ignore", "--quiet", "--", relative_path], check=False)
    return result.returncode == 0


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def extract_section(path: Path, heading: str) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        start = index + 1
        if start < len(lines) and set(lines[start].strip()) == {"-"}:
            start += 1
        body: list[str] = []
        for candidate in lines[start:]:
            if body and candidate and set(candidate.strip()) == {"-"}:
                body.pop()
                break
            body.append(candidate)
        text = "\n".join(body).strip()
        return text or None
    return None


def collect_report() -> tuple[CheckReport, dict[str, str]]:
    report = CheckReport()
    mode: dict[str, str] = {}

    if not MODE_PATH.is_file():
        report.errors.append("missing .zmd-worktree-mode")
        return report, mode

    try:
        mode = parse_mode_file(MODE_PATH)
    except (OSError, ValueError) as exc:
        report.errors.append(str(exc))
        return report, mode

    missing_keys = sorted(REQUIRED_MODE_KEYS - mode.keys())
    if missing_keys:
        report.errors.append(f"mode file missing keys: {', '.join(missing_keys)}")
        return report, mode

    actual_root_result = run_git(["rev-parse", "--show-toplevel"], check=False)
    if actual_root_result.returncode != 0:
        report.errors.append(f"not inside a Git worktree: {actual_root_result.stderr.strip()}")
        return report, mode

    actual_root = Path(actual_root_result.stdout.strip()).resolve()
    if actual_root != ROOT.resolve():
        report.errors.append(f"tool root {ROOT} differs from Git root {actual_root}")

    branch_result = run_git(["branch", "--show-current"], check=False)
    branch = branch_result.stdout.strip()
    report.info["branch"] = branch or "DETACHED"
    if branch != mode["branch"]:
        report.errors.append(
            f"branch mismatch: mode expects {mode['branch']!r}, Git reports {branch or 'DETACHED'!r}"
        )

    if mode["schema"] != "zmd_research_worktree_v1":
        report.errors.append(f"unknown mode schema {mode['schema']!r}")
    if mode["mode"] != "research":
        report.errors.append(f"wrong mode {mode['mode']!r}; expected 'research'")
    if mode["scope"] != "all_zmd_research":
        report.errors.append(f"wrong research scope {mode['scope']!r}")

    required_paths = {
        "entry": path_from_mode(mode, "entry"),
        "program": path_from_mode(mode, "program"),
        "architecture": path_from_mode(mode, "architecture"),
        "attention": path_from_mode(mode, "attention"),
        "checks": path_from_mode(mode, "checks"),
        "state": path_from_mode(mode, "state"),
        "active campaign": path_from_mode(mode, "active_campaign_file"),
        "baseline": ROOT / "research_lab" / "BASELINE.txt",
        "campaign inputs": path_from_mode(mode, "active_campaign_file").parent / "INPUTS.txt",
        "campaign results": path_from_mode(mode, "active_campaign_file").parent / "RESULTS.txt",
        "promotion template": ROOT / "research_lab" / "promotion" / "PACKET_TEMPLATE.txt",
        "CC memory architecture": ROOT / "research_lab" / "CC_MEMORY.txt",
        "CC memory seed": path_from_mode(mode, "cc_memory_seed"),
        "CC memory migration map": path_from_mode(mode, "cc_memory_migration"),
        "CC memory migration receipt": path_from_mode(mode, "cc_memory_receipt"),
    }
    for label, path in required_paths.items():
        if not path.is_file():
            report.errors.append(f"missing {label}: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
            continue
        if path.is_relative_to(ROOT):
            relative = path.relative_to(ROOT).as_posix()
            if not is_tracked(relative):
                report.errors.append(f"research architecture file is not tracked: {relative}")

    history_tree = Path(mode["history_tree"]).resolve()
    report.info["history_tree"] = str(history_tree)
    if not history_tree.is_dir():
        report.errors.append(f"history/material tree does not exist: {history_tree}")
    elif history_tree == ROOT.resolve():
        report.errors.append("research tree and history/material tree resolve to the same path")
    else:
        history_branch_result = subprocess.run(
            ["git", "-C", str(history_tree), "branch", "--show-current"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        history_branch = history_branch_result.stdout.strip() or "DETACHED"
        report.info["history_branch"] = history_branch
        if history_branch_result.returncode != 0:
            report.errors.append(
                f"cannot inspect history/material branch: {history_branch_result.stderr.strip()}"
            )
        elif history_branch != mode["history_branch"]:
            report.errors.append(
                f"history branch mismatch: mode expects {mode['history_branch']!r}, "
                f"Git reports {history_branch!r}"
            )

    certification_tree = mode["certification_tree"]
    report.info["certification_tree"] = certification_tree
    cert_path = Path(certification_tree).resolve()
    if not cert_path.is_dir():
        report.errors.append(f"configured certification tree does not exist: {cert_path}")
    elif cert_path in {ROOT.resolve(), history_tree}:
        report.errors.append("certification tree must be distinct from research and history trees")
    else:
        cert_branch_result = subprocess.run(
            ["git", "-C", str(cert_path), "branch", "--show-current"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cert_branch = cert_branch_result.stdout.strip() or "DETACHED"
        report.info["certification_branch"] = cert_branch
        if cert_branch_result.returncode != 0:
            report.errors.append(
                f"cannot inspect certification branch: {cert_branch_result.stderr.strip()}"
            )
        elif cert_branch != mode["certification_branch"]:
            branch_prefix = mode["certification_branch_prefix"]
            if not cert_branch.startswith(branch_prefix):
                report.errors.append(
                    f"certification branch mismatch: expected integration branch "
                    f"{mode['certification_branch']!r} or prefix {branch_prefix!r}, "
                    f"Git reports {cert_branch!r}"
                )
            else:
                report.warnings.append(
                    f"certification tree is on temporary branch {cert_branch!r}, "
                    f"not integration branch {mode['certification_branch']!r}"
                )

    python_path = Path(mode["python"])
    report.info["python"] = str(python_path)
    if not python_path.exists():
        report.errors.append(f"configured project Python does not exist: {python_path}")

    if not (ROOT / ".git").is_file():
        report.errors.append("research root is not an isolated linked worktree (.git should be a file)")

    for overlay in ("AGENTS.md", "CLAUDE.md"):
        overlay_path = ROOT / overlay
        if not overlay_path.is_file():
            report.errors.append(f"missing research attention overlay: {overlay}")
        elif not is_tracked(overlay):
            report.errors.append(f"research attention overlay is not tracked: {overlay}")

    agents = ROOT / "AGENTS.md"
    claude = ROOT / "CLAUDE.md"
    if agents.is_file() and claude.is_file():
        if agents.read_bytes() != claude.read_bytes():
            report.errors.append("AGENTS.md and CLAUDE.md have drifted")

    readme = ROOT / "README.md"
    if not readme.is_file() or not readme.read_text(encoding="utf-8").startswith("# ZMD Research Tree"):
        report.errors.append("root README does not identify the research tree")

    local_root = path_from_mode(mode, "local_root")
    try:
        local_relative = local_root.relative_to(ROOT).as_posix()
    except ValueError:
        report.errors.append("local_root must be inside the research worktree")
    else:
        if not local_root.is_dir():
            report.errors.append(f"local runtime root does not exist: {local_relative}")
        probe = f"{local_relative}/__research_tree_ignore_probe__.tmp"
        if not is_ignored(probe):
            report.errors.append(f"local runtime root is not ignored by Git: {local_relative}")

    memory_dir = Path(mode["cc_memory_directory"]).expanduser().resolve()
    report.info["cc_memory_directory"] = str(memory_dir)
    settings_path = path_from_mode(mode, "cc_memory_settings")
    settings_relative = settings_path.relative_to(ROOT).as_posix()
    if not settings_path.is_file():
        report.errors.append(f"missing local CC memory setting: {settings_relative}")
    else:
        if is_tracked(settings_relative):
            report.errors.append(f"CC memory local setting must remain untracked: {settings_relative}")
        if not is_ignored(settings_relative):
            report.errors.append(f"CC memory local setting must be Git-ignored: {settings_relative}")
        try:
            settings_payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"invalid CC memory local setting: {exc}")
        else:
            if not isinstance(settings_payload, dict):
                report.errors.append("CC memory local setting must be a JSON object")
            else:
                if settings_payload.get("autoMemoryEnabled") is not True:
                    report.errors.append("CC memory local setting must enable autoMemoryEnabled")
                configured_raw = settings_payload.get("autoMemoryDirectory")
                if not isinstance(configured_raw, str) or not configured_raw:
                    report.errors.append("CC memory local setting must name autoMemoryDirectory")
                elif Path(configured_raw).expanduser().resolve() != memory_dir:
                    report.errors.append(
                        "CC memory directory mismatch between mode and local settings"
                    )

    seed_path = path_from_mode(mode, "cc_memory_seed")
    if memory_dir == ROOT.resolve():
        report.errors.append("CC memory directory must be outside the research worktree")
    if not memory_dir.is_dir():
        report.errors.append(f"CC memory directory does not exist: {memory_dir}")
    elif seed_path.is_file():
        try:
            seed_manifest = json.loads(seed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"invalid CC memory seed manifest: {exc}")
        else:
            if not isinstance(seed_manifest, dict) or seed_manifest.get("role") != "research":
                report.errors.append("CC memory seed manifest must declare role=research")
            else:
                marker = str(seed_manifest.get("role_marker", ""))
                files = seed_manifest.get("files")
                if not marker or not isinstance(files, list) or not files:
                    report.errors.append("CC memory seed manifest lacks marker or files")
                else:
                    drift_count = 0
                    for entry in files:
                        if not isinstance(entry, dict):
                            report.errors.append("CC memory seed file entry must be an object")
                            continue
                        seed_name = entry.get("seed")
                        target_name = entry.get("target")
                        if not isinstance(seed_name, str) or not isinstance(target_name, str):
                            report.errors.append("CC memory seed entry lacks seed/target strings")
                            continue
                        seed_file = seed_path.parent / seed_name
                        target_file = memory_dir / target_name
                        if not seed_file.is_file():
                            report.errors.append(f"missing CC memory seed file: {seed_file.relative_to(ROOT)}")
                            continue
                        seed_relative = seed_file.relative_to(ROOT).as_posix()
                        if not is_tracked(seed_relative):
                            report.errors.append(f"CC memory seed file is not tracked: {seed_relative}")
                        if not target_file.is_file():
                            report.errors.append(f"missing installed CC memory file: {target_file}")
                            continue
                        if seed_file.read_bytes() != target_file.read_bytes():
                            drift_count += 1
                    index_path = memory_dir / "MEMORY.md"
                    if index_path.is_file():
                        index_text = index_path.read_text(encoding="utf-8")
                        if marker not in index_text:
                            report.errors.append("installed CC memory index lacks research role marker")
                        if "ZMD_CERTIFICATION_MEMORY_V1" in index_text:
                            report.errors.append("research CC memory contains certification role marker")
                    report.info["cc_memory_seed_drift"] = str(drift_count)
                    if drift_count:
                        report.warnings.append(
                            f"{drift_count} CC memory core file(s) evolved from the tracked seed"
                        )

    state_path = path_from_mode(mode, "state")
    campaign_path = path_from_mode(mode, "active_campaign_file")
    if state_path.is_file():
        state_text = state_path.read_text(encoding="utf-8")
        if f"Branch: {mode['branch']}" not in state_text:
            report.errors.append("STATE.txt branch does not match mode file")
        if f"Active campaign: {mode['active_campaign']}" not in state_text:
            report.errors.append("STATE.txt active campaign does not match mode file")
        if extract_section(state_path, "Reflection checkpoint") is None:
            report.errors.append("STATE.txt lacks the required Reflection checkpoint section")
        if line_count(state_path) > 100:
            report.warnings.append("STATE.txt exceeds 100 lines; move history into campaign RESULTS/journals")

    if campaign_path.is_file():
        campaign_text = campaign_path.read_text(encoding="utf-8")
        if f"id: {mode['active_campaign']}" not in campaign_text:
            report.errors.append("active CAMPAIGN.txt id does not match mode file")

    start_path = path_from_mode(mode, "entry")
    if start_path.is_file() and line_count(start_path) > 110:
        report.warnings.append("START.txt exceeds 110 lines; cold-start attention may be diluting")

    head_result = run_git(["rev-parse", "--short=12", "HEAD"], check=False)
    report.info["head"] = head_result.stdout.strip() if head_result.returncode == 0 else "UNKNOWN"
    report.info["mode"] = mode.get("mode", "UNKNOWN")
    report.info["active_campaign"] = mode.get("active_campaign", "UNKNOWN")
    report.info["active_campaign_file"] = mode.get("active_campaign_file", "UNKNOWN")
    report.info["attention"] = mode.get("attention", "UNKNOWN")

    return report, mode


def print_human(report: CheckReport, mode: dict[str, str], *, enter: bool) -> None:
    banner = "ZMD RESEARCH TREE ENTRY" if enter else "ZMD RESEARCH TREE CHECK"
    print(banner)
    print("=" * len(banner))
    for key in (
        "mode",
        "branch",
        "head",
        "active_campaign",
        "active_campaign_file",
        "attention",
        "history_tree",
        "history_branch",
        "certification_tree",
        "certification_branch",
        "cc_memory_directory",
        "cc_memory_seed_drift",
        "python",
    ):
        if key in report.info:
            print(f"{key:24} {report.info[key]}")

    if report.warnings:
        print("\nWARNINGS")
        for warning in report.warnings:
            print(f"  - {warning}")

    if report.errors:
        print("\nERRORS")
        for error in report.errors:
            print(f"  - {error}")
        print("\nSTATUS: FAIL")
        return

    print("\nSTATUS: PASS")

    if enter:
        state_path = path_from_mode(mode, "state")
        reflection_checkpoint = extract_section(state_path, "Reflection checkpoint")
        live_question = extract_section(state_path, "Live question")
        print("\nREAD NOW")
        print(f"  1. {mode['state']}")
        print(f"  2. {mode['active_campaign_file']}")
        print("\nSESSION MODE")
        print(
            "  RESEARCH mode: produce candidate knowledge for "
            f"{mode['active_campaign']}; this session cannot grant certification or update U/L."
        )
        if reflection_checkpoint:
            print("\nREFLECTION CHECKPOINT")
            for line in reflection_checkpoint.splitlines():
                print(f"  {line}")
            print(f"  pause guide: {mode['attention']}")
        if live_question:
            print("\nLIVE QUESTION")
            for line in live_question.splitlines():
                print(f"  {line}")

        status_result = run_git(["status", "--short"], check=False)
        status = status_result.stdout.strip()
        print("\nWORKTREE")
        print("  clean" if not status else "  has Git-visible changes:\n" + "\n".join(f"    {line}" for line in status.splitlines()))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "enter"), nargs="?", default="check")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args(argv)

    report, mode = collect_report()
    if args.json:
        payload = {
            "status": "PASS" if report.ok else "FAIL",
            "info": report.info,
            "warnings": report.warnings,
            "errors": report.errors,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(report, mode, enter=args.command == "enter")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
