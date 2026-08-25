"""Cold-start and structural checks for the ZMD certification worktree.

This standard-library-only tool verifies worktree role, attention overlays,
packet routing, and local-output isolation. It does not prove a candidate claim,
grant certification, satisfy an owner gate, mint a seal, or publish a result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
MODE_PATH = ROOT / "certification_lab" / "MODE.txt"

REQUIRED_MODE_KEYS = frozenset(
    {
        "schema",
        "mode",
        "branch",
        "entry",
        "charter",
        "architecture",
        "checks",
        "state",
        "baseline",
        "overlay_template",
        "intake_contract",
        "packet_template",
        "verdict_template",
        "active_packet",
        "active_packet_file",
        "history_tree",
        "history_branch",
        "research_tree",
        "research_branch",
        "python",
        "local_root",
        "inbox_root",
        "reviews_root",
        "intake_policy",
        "authority_policy",
        "publication_authority",
    }
)


@dataclass
class CheckReport:
    info: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_git(
    args: Sequence[str],
    *,
    cwd: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run_process(["git", *args], cwd=cwd, check=check)


def parse_mode_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
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
    path = Path(mode[key])
    return path if path.is_absolute() else ROOT / path


def relative_display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def is_tracked(relative_path: str) -> bool:
    result = run_git(
        ["ls-files", "--error-unmatch", "--", relative_path], check=False
    )
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
        if start < len(lines) and lines[start].strip() and set(
            lines[start].strip()
        ) == {"-"}:
            start += 1
        body: list[str] = []
        for candidate in lines[start:]:
            if body and candidate.strip() and set(candidate.strip()) == {"-"}:
                body.pop()
                break
            body.append(candidate)
        text = "\n".join(body).strip()
        return text or None
    return None


def external_branch(path: Path) -> tuple[str, str]:
    branch_result = run_git(["branch", "--show-current"], cwd=path, check=False)
    head_result = run_git(["rev-parse", "--short=12", "HEAD"], cwd=path, check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "ERROR"
    head = head_result.stdout.strip() if head_result.returncode == 0 else "ERROR"
    return branch or "DETACHED", head


def filtered_status() -> list[str]:
    result = run_git(["status", "--short", "--untracked-files=all"], check=False)
    lines = result.stdout.splitlines()
    local_overlays = {"?? AGENTS.md", "?? CLAUDE.md"}
    return [line for line in lines if line not in local_overlays]


def collect_report() -> tuple[CheckReport, dict[str, str]]:
    report = CheckReport()
    mode: dict[str, str] = {}

    if not MODE_PATH.is_file():
        report.errors.append("missing certification_lab/MODE.txt")
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

    root_result = run_git(["rev-parse", "--show-toplevel"], check=False)
    if root_result.returncode != 0:
        report.errors.append(f"not in a Git worktree: {root_result.stderr.strip()}")
        return report, mode

    actual_root = Path(root_result.stdout.strip()).resolve()
    if actual_root != ROOT.resolve():
        report.errors.append(f"tool root {ROOT} differs from Git root {actual_root}")

    branch_result = run_git(["branch", "--show-current"], check=False)
    branch = branch_result.stdout.strip()
    report.info["branch"] = branch or "DETACHED"
    if branch != mode["branch"]:
        report.errors.append(
            f"branch mismatch: mode expects {mode['branch']!r}, "
            f"Git reports {branch or 'DETACHED'!r}"
        )

    head_result = run_git(["rev-parse", "--short=12", "HEAD"], check=False)
    report.info["head"] = (
        head_result.stdout.strip() if head_result.returncode == 0 else "UNKNOWN"
    )

    if mode["schema"] != "zmd_certification_worktree_v1":
        report.errors.append(f"unknown mode schema {mode['schema']!r}")
    if mode["mode"] != "certification":
        report.errors.append(
            f"wrong mode {mode['mode']!r}; expected 'certification'"
        )
    if mode["intake_policy"] != "packet_only_cold_review":
        report.errors.append(f"unexpected intake policy {mode['intake_policy']!r}")
    if mode["authority_policy"] != "branch_name_grants_nothing":
        report.errors.append(
            f"unexpected authority policy {mode['authority_policy']!r}"
        )
    if mode["publication_authority"] != (
        "existing_project_seal_owner_and_publisher_chain_only"
    ):
        report.errors.append(
            f"unexpected publication authority {mode['publication_authority']!r}"
        )

    required_paths = {
        "mode": MODE_PATH,
        "entry": path_from_mode(mode, "entry"),
        "charter": path_from_mode(mode, "charter"),
        "architecture": path_from_mode(mode, "architecture"),
        "checks": path_from_mode(mode, "checks"),
        "state": path_from_mode(mode, "state"),
        "baseline": path_from_mode(mode, "baseline"),
        "overlay template": path_from_mode(mode, "overlay_template"),
        "intake contract": path_from_mode(mode, "intake_contract"),
        "packet template": path_from_mode(mode, "packet_template"),
        "verdict template": path_from_mode(mode, "verdict_template"),
        "inbox README": ROOT / "certification_lab" / "inbox" / "README.txt",
        "reviews README": ROOT / "certification_lab" / "reviews" / "README.txt",
        "local README": ROOT / "certification_lab" / "local" / "README.txt",
        "local ignore": ROOT / "certification_lab" / "local" / ".gitignore",
        "PROJECT_LOCK": ROOT / "PROJECT_LOCK.md",
        "certification navigation": ROOT / "docs" / "CERTIFICATION.md",
    }
    for label, path in required_paths.items():
        if not path.is_file():
            report.errors.append(f"missing {label}: {relative_display(path)}")
            continue
        if path.is_relative_to(ROOT) and not is_tracked(path.relative_to(ROOT).as_posix()):
            report.errors.append(f"required {label} is not tracked: {relative_display(path)}")

    if not (ROOT / ".git").is_file():
        report.errors.append(
            "certification root is not an isolated linked worktree (.git must be a file)"
        )

    history_tree = Path(mode["history_tree"]).resolve()
    research_tree = Path(mode["research_tree"]).resolve()
    report.info["history_tree"] = str(history_tree)
    report.info["research_tree"] = str(research_tree)

    roots = {ROOT.resolve(), history_tree, research_tree}
    if len(roots) != 3:
        report.errors.append(
            "certification, history/material, and research trees must be distinct"
        )

    for label, path, expected_branch in (
        ("history", history_tree, mode["history_branch"]),
        ("research", research_tree, mode["research_branch"]),
    ):
        if not path.is_dir():
            report.errors.append(f"{label} tree does not exist: {path}")
            continue
        actual_branch, head = external_branch(path)
        report.info[f"{label}_branch"] = actual_branch
        report.info[f"{label}_head"] = head
        if actual_branch != expected_branch:
            report.errors.append(
                f"{label} branch mismatch: expected {expected_branch!r}, "
                f"found {actual_branch!r}"
            )

    python_path = Path(mode["python"])
    report.info["python"] = str(python_path)
    if not python_path.is_file():
        report.errors.append(f"configured project Python does not exist: {python_path}")

    template_path = path_from_mode(mode, "overlay_template")
    if template_path.is_file():
        template_bytes = template_path.read_bytes()
        for overlay_name in ("AGENTS.md", "CLAUDE.md"):
            overlay_path = ROOT / overlay_name
            if not overlay_path.is_file():
                report.errors.append(
                    f"missing local certification attention overlay: {overlay_name}; "
                    "run install-overlay"
                )
                continue
            if is_tracked(overlay_name):
                report.errors.append(
                    f"certification attention overlay must remain untracked: {overlay_name}"
                )
            if overlay_path.read_bytes() != template_bytes:
                report.errors.append(
                    f"certification attention overlay differs from tracked template: "
                    f"{overlay_name}"
                )

    readme_path = ROOT / "README.md"
    if not readme_path.is_file() or not readme_path.read_text(
        encoding="utf-8"
    ).startswith("# ZMD certified-exact 最大空矩形求解器"):
        report.errors.append("root README is not the inherited stable project front door")
    elif line_count(readme_path) > 48:
        report.warnings.append(
            "root README exceeds the inherited 48-line attention budget"
        )

    local_root = path_from_mode(mode, "local_root")
    try:
        local_relative = local_root.relative_to(ROOT).as_posix()
    except ValueError:
        report.errors.append("local_root must be inside the certification tree")
    else:
        if not local_root.is_dir():
            report.errors.append(f"local runtime root does not exist: {local_relative}")
        probe = f"{local_relative}/__certification_ignore_probe__/raw.log"
        if not is_ignored(probe):
            report.errors.append(
                f"local runtime root is not ignored by Git: {local_relative}"
            )

    inbox_root = path_from_mode(mode, "inbox_root")
    reviews_root = path_from_mode(mode, "reviews_root")
    for label, path in (("inbox_root", inbox_root), ("reviews_root", reviews_root)):
        if not path.is_dir():
            report.errors.append(f"{label} does not exist: {relative_display(path)}")
        elif not path.is_relative_to(ROOT):
            report.errors.append(f"{label} must be inside the certification tree")

    active_packet = mode["active_packet"]
    active_packet_file = mode["active_packet_file"]
    report.info["active_packet"] = active_packet
    report.info["active_packet_file"] = active_packet_file
    if active_packet == "NONE":
        if active_packet_file != "NONE":
            report.errors.append(
                "active_packet=NONE requires active_packet_file=NONE"
            )
        report.warnings.append("no certification packet is active; tree is idle")
    else:
        if active_packet_file == "NONE":
            report.errors.append(
                "active packet requires a concrete active_packet_file"
            )
        else:
            packet_path = path_from_mode(mode, "active_packet_file")
            if not packet_path.is_file():
                report.errors.append(
                    f"active packet file does not exist: {relative_display(packet_path)}"
                )
            else:
                try:
                    packet_path.relative_to(inbox_root)
                except ValueError:
                    report.errors.append(
                        "active packet file must live under certification_lab/inbox"
                    )
                if active_packet not in packet_path.parts:
                    report.errors.append(
                        "active packet id is not represented in active packet path"
                    )

    state_path = path_from_mode(mode, "state")
    if state_path.is_file():
        state_text = state_path.read_text(encoding="utf-8")
        for expected in (
            f"Branch: {mode['branch']}",
            "Mode: CERTIFICATION",
            f"Active packet: {active_packet}",
        ):
            if expected not in state_text:
                report.errors.append(f"STATE.txt omits expected marker: {expected}")
        if line_count(state_path) > 140:
            report.warnings.append(
                "STATE.txt exceeds 140 lines; move packet detail into its review"
            )

    start_path = path_from_mode(mode, "entry")
    if start_path.is_file() and line_count(start_path) > 120:
        report.warnings.append(
            "START.txt exceeds 120 lines; cold-start attention may be diluting"
        )

    report.info["mode"] = mode.get("mode", "UNKNOWN")
    return report, mode


def install_overlays(mode: dict[str, str]) -> None:
    template = path_from_mode(mode, "overlay_template")
    if not template.is_file():
        raise FileNotFoundError(f"overlay template does not exist: {template}")
    payload = template.read_bytes()
    for overlay_name in ("AGENTS.md", "CLAUDE.md"):
        (ROOT / overlay_name).write_bytes(payload)


def print_human(report: CheckReport, mode: dict[str, str], *, enter: bool) -> None:
    banner = "ZMD CERTIFICATION TREE ENTRY" if enter else "ZMD CERTIFICATION TREE CHECK"
    print(banner)
    print("=" * len(banner))
    for key in (
        "mode",
        "branch",
        "head",
        "active_packet",
        "active_packet_file",
        "history_tree",
        "history_branch",
        "history_head",
        "research_tree",
        "research_branch",
        "research_head",
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

    if not enter:
        return

    print("\nREAD NOW")
    print(f"  1. {mode['state']}")
    if mode["active_packet"] != "NONE":
        print(f"  2. {mode['active_packet_file']}")
    else:
        print("  2. no active packet; remain idle")

    print("\nSESSION MODE")
    if mode["active_packet"] == "NONE":
        print(
            "  CERTIFICATION mode: no packet is active; this session must not "
            "select one by browsing research history."
        )
    else:
        print(
            "  CERTIFICATION mode: independently review "
            f"{mode['active_packet']}; this session cannot self-grant "
            "certification, U/L, owner approval, seal, or publication."
        )

    state_path = path_from_mode(mode, "state")
    live_question = extract_section(state_path, "Live question")
    if live_question:
        print("\nLIVE QUESTION")
        for line in live_question.splitlines():
            print(f"  {line}")

    status = filtered_status()
    print("\nWORKTREE")
    if status:
        print("  has Git-visible changes other than local overlays:")
        for line in status:
            print(f"    {line}")
    else:
        print("  clean apart from verified local overlays")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("check", "enter", "install-overlay"),
        nargs="?",
        default="check",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        mode = parse_mode_file(MODE_PATH)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "install-overlay":
        try:
            install_overlays(mode)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print("Installed AGENTS.md and CLAUDE.md from certification template.")
        return 0

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
