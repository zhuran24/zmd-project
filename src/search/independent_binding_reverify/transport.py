"""Parent-side process isolation for the independent binding capsule."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict

from .protocol import ProtocolError


_BOOTSTRAP = r"""
import sys
from pathlib import Path
source_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source_root))
from src.search.independent_binding_reverify.capsule import isolated_capsule_main
raise SystemExit(isolated_capsule_main())
"""


class CapsuleTransportError(RuntimeError):
    pass


class CapsuleTimeout(CapsuleTransportError):
    pass


def invoke_capsule(
    request: Mapping[str, Any],
    *,
    source_root: Path,
    timeout_seconds: float,
) -> Dict[str, Any]:
    request_bytes = json.dumps(
        dict(request),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="zmd_binding_reverify_") as temp_dir:
        temp_root = Path(temp_dir)
        pycache_root = temp_root / "pycache"
        command = [
            sys.executable,
            "-I",
            "-B",
            "-X",
            f"pycache_prefix={pycache_root}",
            "-c",
            _BOOTSTRAP,
            str(Path(source_root).resolve()),
        ]
        try:
            completed = subprocess.run(
                command,
                input=request_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temp_root,
                check=False,
                timeout=float(timeout_seconds),
            )
        except subprocess.TimeoutExpired as exc:
            raise CapsuleTimeout(
                f"binding reverify capsule exceeded {timeout_seconds:g}s"
            ) from exc
        except OSError as exc:
            raise CapsuleTransportError(
                f"binding reverify capsule launch failed: {type(exc).__name__}: {exc}"
            ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")[:2000]
        raise CapsuleTransportError(
            f"binding reverify capsule exit={completed.returncode}: {stderr}"
        )
    try:
        response = _loads_strict_json(
            completed.stdout.decode("utf-8", errors="strict")
        )
    except (UnicodeDecodeError, ValueError, ProtocolError) as exc:
        raise CapsuleTransportError(
            f"binding reverify capsule returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(response, Mapping):
        raise CapsuleTransportError("binding reverify capsule response is not an object")
    return dict(response)


def _loads_strict_json(text: str) -> Any:
    def _pairs(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def _constant(value: str) -> None:
        raise ProtocolError(f"non-finite JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=_pairs,
        parse_constant=_constant,
    )
