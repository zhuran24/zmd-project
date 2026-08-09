"""binding PB sidecar — 求解与检查链 runner（设计稿 v2 §4/§5 判定协议）.

Windows 侧调 WSL 的 roundingsat/veripb。判定 fail-closed：
- 结论行 anchored 唯一匹配（禁退出码判定——veripb 失败 exit 0、RoundingSat UNSAT exit 1）；
- proof 存在/非空/mtime 晚于 solver 启动/sha256 归档；
- 全量 argv/stdout/stderr/版本归档进 verdict record。
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

WSL = ["wsl", "-d", "Ubuntu-24.04", "--"]
ROUNDINGSAT = "/root/cert_toolchain/roundingsat/build/roundingsat"
VERIPB = "/root/.cargo/bin/veripb"
CAKEPB = "/root/cert_toolchain/CakePB/cake_pb"
WORK_WSL = "/root/cert_toolchain/sidecar_work"

_S_LINE = re.compile(r"^s (.+?)\s*$", re.MULTILINE)
ERROR_MARKS = ("Error:", "Checking error", "panic", "unsupported")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _to_wsl_path(win_path: Path) -> str:
    p = str(win_path.resolve()).replace("\\", "/")
    drive, rest = p.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


def _run(argv: List[str], timeout_s: float) -> Dict[str, Any]:
    t0 = time.time()
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout_s, check=False
        )
        return {
            "argv": argv, "exit_code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr,
            "wall_seconds": time.time() - t0, "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv, "exit_code": None,
            "stdout": exc.stdout or "", "stderr": exc.stderr or "",
            "wall_seconds": time.time() - t0, "timed_out": True,
        }


def _status_lines(stdout: str) -> List[str]:
    return _S_LINE.findall(stdout)


def run_sidecar_chain(
    opb_path: Path,
    work_dir: Path,
    *,
    solve_timeout_s: float = 60.0,
    check_timeout_s: float = 120.0,
    with_cakepb: bool = True,
) -> Dict[str, Any]:
    """OPB → RoundingSat(proof) → veripb。返回 verdict record（v2 §5 状态机）."""
    work_dir.mkdir(parents=True, exist_ok=True)
    record: Dict[str, Any] = {
        "schema": "binding_sidecar_verdict_v1",
        "opb_sha256": _sha256(opb_path),
        "status": None, "subcode": None,
        "solver": None, "checker": None,
    }
    opb_wsl = _to_wsl_path(opb_path)
    proof_path = work_dir / (opb_path.stem + ".pbp")
    proof_wsl = _to_wsl_path(proof_path)
    if proof_path.exists():
        proof_path.unlink()  # 防旧 proof（PROOF_NOT_CONSUMED_OR_STALE 的第一道防线）

    solver_t0 = time.time()
    solver = _run(
        WSL + [ROUNDINGSAT, opb_wsl, "--print-sol=1", f"--proof-log={proof_wsl}"],
        solve_timeout_s,
    )
    record["solver"] = solver
    if solver["timed_out"]:
        record.update(status="UNKNOWN", subcode="SOLVER_TIMEOUT")
        return record

    s_lines = _status_lines(solver["stdout"])
    if len(s_lines) != 1:
        record.update(status="UNKNOWN", subcode="SOLVER_STATUS_UNPARSEABLE",
                      detail=f"s-lines={s_lines}")
        return record
    s = s_lines[0]

    if s == "SATISFIABLE":
        record.update(status="SIDE_SAT_RAW", subcode=None)
        record["witness_values"] = _parse_witness(solver["stdout"])
        return record  # witness check 由 caller（acceptance）做二段升级

    if s != "UNSATISFIABLE":
        record.update(status="UNKNOWN", subcode="SOLVER_STATUS_UNPARSEABLE", detail=s)
        return record

    # UNSAT 路径：proof 四检
    if not proof_path.is_file() or proof_path.stat().st_size == 0:
        record.update(status="UNKNOWN", subcode="PROOF_NOT_CONSUMED", detail="missing/empty proof")
        return record
    if proof_path.stat().st_mtime < solver_t0 - 1.0:
        record.update(status="UNKNOWN", subcode="PROOF_NOT_CONSUMED_OR_STALE")
        return record
    record["proof_sha256"] = _sha256(proof_path)

    checker = _run(
        WSL + [VERIPB, "--force-checked-deletion", opb_wsl, proof_wsl], check_timeout_s
    )
    record["checker"] = checker
    if checker["timed_out"]:
        record.update(status="UNKNOWN", subcode="CHECKER_TIMEOUT")
        return record
    combined = checker["stdout"] + "\n" + checker["stderr"]
    if any(mark in combined for mark in ERROR_MARKS):
        record.update(status="UNKNOWN", subcode="PROOF_REJECTED")
        return record
    verified = _status_lines(checker["stdout"])
    if verified != ["VERIFIED UNSATISFIABLE"]:
        record.update(status="UNKNOWN", subcode="PROOF_REJECTED",
                      detail=f"checker s-lines={verified}")
        return record

    # 第四层（可选深度检查，默认开）：elaborate → kernel → CakePB（形式化验证 checker）。
    # fail-closed：启用后任一环节不出唯一 `s VERIFIED UNSATISFIABLE` → 降级 UNKNOWN。
    if with_cakepb:
        kernel_path = work_dir / (opb_path.stem + ".kernel.pbp")
        if kernel_path.exists():
            kernel_path.unlink()
        kernel_wsl = _to_wsl_path(kernel_path)
        elab = _run(
            WSL + [VERIPB, "--elaborate", kernel_wsl, opb_wsl, proof_wsl], check_timeout_s
        )
        record["elaborator"] = elab
        if elab["timed_out"] or not kernel_path.is_file() or kernel_path.stat().st_size == 0:
            record.update(status="UNKNOWN", subcode="ELABORATE_FAILED")
            return record
        record["kernel_sha256"] = _sha256(kernel_path)
        cake = _run(WSL + [CAKEPB, opb_wsl, kernel_wsl], check_timeout_s)
        record["cakepb"] = cake
        cake_combined = cake["stdout"] + "\n" + cake["stderr"]
        if (
            cake["timed_out"]
            or any(mark in cake_combined for mark in ERROR_MARKS)
            or "Checking failed" in cake_combined
            or _status_lines(cake["stdout"]) != ["VERIFIED UNSATISFIABLE"]
        ):
            record.update(status="UNKNOWN", subcode="CAKEPB_REJECTED")
            return record
        record["cakepb_verified"] = True

    record.update(status="CONFIRMED", subcode=None)
    return record


def _parse_witness(stdout: str) -> Optional[Dict[int, int]]:
    """RoundingSat SAT 输出的 v 行：`v x1 -x2 x3 ...` → {var: 0/1}."""
    values: Dict[int, int] = {}
    found = False
    for line in stdout.splitlines():
        if not line.startswith("v "):
            continue
        found = True
        for tok in line[2:].split():
            if tok.startswith("-x"):
                values[int(tok[2:])] = 0
            elif tok.startswith("x"):
                values[int(tok[1:])] = 1
    return values if found else None
