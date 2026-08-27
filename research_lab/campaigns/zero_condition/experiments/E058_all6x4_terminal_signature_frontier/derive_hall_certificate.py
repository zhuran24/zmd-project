#!/usr/bin/env python3
"""Derive a short Hall-style certificate from the frozen E058 signature census."""

from __future__ import annotations

from collections import defaultdict
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E058_all6x4_terminal_signature_frontier/run-004"
)
CENSUS = RUN / "SIGNATURE_CENSUS.json"
RESULT = RUN / "RESULT.json"
E060_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E060_generic_qiaoyu_sink_correction/"
    "run-001/RESULT.json"
)
OUTPUT = RUN / "HALL_CERTIFICATE_V2.json"

EXPECTED = {
    CENSUS: "2af0d107eaba7a638047b42b0aab58f83a52c37008221692bb4b8e8cadf27b5d",
    RESULT: "d1295cd0988e751512968d1ad248f3e6da53ce912f52f6f28820f491c6fe27b4",
    E060_RESULT: "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
}
FILLING = "filling_capsule"
FINE_GRINDER = "grinder_fine_buckwheat"
CORE_COMPONENT = 15
REQUIRED_FILLING_COUNT = 3


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()


def run() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED.items():
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual}")

    census = load(CENSUS)
    result = load(RESULT)
    corrected = load(E060_RESULT)
    if corrected.get("verdict") != (
        "GENERIC_QIAOYU_SINK_FREEDOM_REVALIDATES_TWO_ZERO_TARGET"
    ):
        raise RuntimeError("E060 corrected-successor verdict drift")
    if result.get("verdict") != "FIXED_GEOMETRY_6X4_TWO_ZERO_SIGNATURE_CONFLICT":
        raise RuntimeError("E058 trigger verdict drift")
    if result["arms"]["joint"]["status"] != "INFEASIBLE":
        raise RuntimeError("exact joint arm is not INFEASIBLE")
    if result["arms"]["joint_other_relaxation"]["status"] != "INFEASIBLE":
        raise RuntimeError("relaxed joint arm is not INFEASIBLE")

    bodies = {int(index): row for index, row in enumerate(census["bodies"])}
    q15_fill_by_body: dict[int, set[int]] = defaultdict(set)
    fine_support_by_component: dict[int, set[int]] = defaultdict(set)

    for destination_text, options in census["options_by_body"].items():
        destination = int(destination_text)
        for option in options:
            operation = str(option["operation"])
            fine_inputs = tuple(int(value) for value in option["fine_input_components"])
            fine_outputs = tuple(int(value) for value in option["fine_output_components"])
            qiaoyu_outputs = tuple(
                int(value) for value in option["qiaoyu_output_components"]
            )
            if operation == FILLING and qiaoyu_outputs == (CORE_COMPONENT,):
                if len(fine_inputs) != 1:
                    raise RuntimeError(
                        f"core-side filling signature is not singleton: {destination} {fine_inputs}"
                    )
                q15_fill_by_body[destination].add(fine_inputs[0])
            if operation == FINE_GRINDER:
                if len(fine_outputs) != 1:
                    raise RuntimeError(
                        f"fine-grinder signature is not singleton: {destination} {fine_outputs}"
                    )
                fine_support_by_component[fine_outputs[0]].add(destination)

    q15_rows: list[dict[str, Any]] = []
    nonself_body_ids: list[int] = []
    self_blocking_body_ids: list[int] = []
    for body_id in sorted(q15_fill_by_body):
        components = sorted(q15_fill_by_body[body_id])
        if len(components) != 1:
            raise RuntimeError(
                f"one core-side body exposes multiple fine-input components: {body_id}"
            )
        component = components[0]
        supporters = sorted(fine_support_by_component.get(component, set()))
        external_supporters = [value for value in supporters if value != body_id]
        self_blocking = not external_supporters
        if self_blocking:
            self_blocking_body_ids.append(body_id)
        else:
            nonself_body_ids.append(body_id)
        body = bodies[body_id]
        q15_rows.append(
            {
                "body_id": body_id,
                "source_instance_label": body["source_instance_id"],
                "current_pose_idx": body["current_pose_idx"],
                "fine_input_component": component,
                "fine_grinder_support_body_ids": supporters,
                "external_support_body_ids": external_supporters,
                "self_blocking": self_blocking,
            }
        )

    maximum_supported_core_fill_count = len(nonself_body_ids)
    deficit = REQUIRED_FILLING_COUNT - maximum_supported_core_fill_count
    if len(q15_rows) != 4:
        raise RuntimeError(f"core-side filling body count drift: {len(q15_rows)}")
    if maximum_supported_core_fill_count != 2 or deficit != 1:
        raise RuntimeError(
            "Hall deficit drift: "
            f"maximum={maximum_supported_core_fill_count} deficit={deficit}"
        )

    return {
        "schema": "zmd_zero_condition_e058_hall_certificate_v2",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": {
            "checked_hashes": checked,
            "runner_sha256": sha256_file(Path(__file__).resolve()),
        },
        "required_filling_capsule_count": REQUIRED_FILLING_COUNT,
        "core_component": CORE_COMPONENT,
        "core_side_filling_bodies": q15_rows,
        "nonself_supported_body_ids": nonself_body_ids,
        "self_blocking_body_ids": self_blocking_body_ids,
        "maximum_supported_core_fill_count": maximum_supported_core_fill_count,
        "bridge_body_deficit": deficit,
        "corrected_successor": {
            "result_path": str(E060_RESULT.relative_to(ROOT)),
            "result_sha256": checked[str(E060_RESULT)],
            "generic_sink_components": [15, 39],
            "optimum_selected_sink_component": 15,
        },
        "statement": (
            "E060 restores generic qiaoyu sink freedom and independently shows that "
            "every optimum still selects component 15. In that corrected optimum "
            "branch, only four fixed-geometry 6x4 bodies can emit qiaoyu_capsule into the "
            "core component. Their fine-input components are 6, 15, 21, and 54. "
            "The component-21 and component-54 fine-grinder signatures are "
            "supported only by the same body that would have to carry filling_capsule. "
            "Therefore only two core-side filling bodies have an external fine source, "
            "while three filling_capsule operations are mandatory. At least one new "
            "non-self-blocking core-side bridge body is required."
        ),
        "truth_boundary": (
            "Fixed E055 occupied geometry, E058 native same-body terminal-signature "
            "census, and the component-15 optimum branch revalidated by E060. This "
            "compact Hall synopsis does not replace E060's corrected variable-sink "
            "proof, cover component-39 alternatives outside that optimum branch, or "
            "identify a sufficient relocated body."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError("refusing to overwrite E058 Hall certificate")
    result = run()
    dump_exclusive(OUTPUT, result)
    print(
        json.dumps(
            {
                "maximum_supported_core_fill_count": result[
                    "maximum_supported_core_fill_count"
                ],
                "bridge_body_deficit": result["bridge_body_deficit"],
                "result_path": str(OUTPUT),
                "result_sha256": sha256_file(OUTPUT),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
