"""Runtime trust anchor for the frozen canonical ``certified_exact`` inputs.

Campaign hashes prove continuity only after a campaign has been created.  They
must not let a fresh campaign choose its own theorem by pinning whatever bytes
happen to be present on first launch.  The canonical project therefore has a
fixed input contract in source-controlled runtime code.

Toy projects remain supported for model-level regression tests.  The fixed
contract applies to the source checkout itself and to project roots that carry
``PROJECT_LOCK.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

LOCKED_EXACT_PROJECT_MARKER = "PROJECT_LOCK.md"

LOCKED_EXACT_ARTIFACT_PATHS = {
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "canonical_rules": "rules/canonical_rules.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "preprocess_plan": "rules/preprocess_plan.json",
}

LOCKED_EXACT_ARTIFACT_SHA256 = {
    "mandatory_exact_instances": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    "candidate_placements": "adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0",
    "canonical_rules": "36a461884fdd2451dfead8ad2c19c053f17d74f573a53a6f851a4e0b3ce6015d",
    "generic_io_requirements": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    "preprocess_plan": "1bcf0d13e1709cd7e04ddea439ee005e837584f2f66a1a921159d198019c9ed8",
}

LOCKED_EXACT_ARTIFACT_SIZE_BYTES = {
    "candidate_placements": 45_773_799,
}


class LockedExactArtifactContractError(ValueError):
    """Raised when a canonical project root does not match its frozen theorem."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = str(reason)
        super().__init__(f"{self.reason}: {detail}")


def certified_project_uses_locked_artifact_contract(project_root: Path) -> bool:
    """Return whether ``project_root`` represents the frozen canonical project.

    The source checkout is locked even if its marker is accidentally removed.
    A copied/installed project is locked when it carries ``PROJECT_LOCK.md``.
    A dangling or symlinked marker also selects the locked path, which is the
    fail-closed choice.
    """

    root = Path(project_root).resolve()
    source_root = Path(__file__).resolve().parents[2]
    if root == source_root:
        return True
    marker = root / LOCKED_EXACT_PROJECT_MARKER
    return marker.exists() or marker.is_symlink()


def locked_exact_artifact_contract_violation(
    *,
    project_root: Path,
    artifact_hashes: Mapping[str, str],
    artifact_sizes: Optional[Mapping[str, int]] = None,
) -> Optional[str]:
    """Return a stable fail-closed reason for a frozen-input mismatch."""

    if not certified_project_uses_locked_artifact_contract(project_root):
        return None

    for key, expected_hash in LOCKED_EXACT_ARTIFACT_SHA256.items():
        actual_hash = artifact_hashes.get(key)
        if actual_hash is None:
            return f"locked_exact_artifact_hash_missing:{key}"
        if str(actual_hash).lower() != str(expected_hash).lower():
            return f"locked_exact_artifact_hash_mismatch:{key}"

    actual_sizes = artifact_sizes
    if actual_sizes is None:
        root = Path(project_root)
        derived_sizes: dict[str, int] = {}
        for key in LOCKED_EXACT_ARTIFACT_SIZE_BYTES:
            try:
                derived_sizes[key] = int(
                    (root / LOCKED_EXACT_ARTIFACT_PATHS[key]).stat().st_size
                )
            except OSError:
                return f"locked_exact_artifact_size_unavailable:{key}"
        actual_sizes = derived_sizes

    for key, expected_size in LOCKED_EXACT_ARTIFACT_SIZE_BYTES.items():
        actual_size = actual_sizes.get(key)
        if actual_size is None:
            return f"locked_exact_artifact_size_missing:{key}"
        if int(actual_size) != int(expected_size):
            return f"locked_exact_artifact_size_mismatch:{key}"
    return None


def validate_locked_exact_artifact_contract(
    *,
    project_root: Path,
    artifact_hashes: Mapping[str, str],
    artifact_sizes: Optional[Mapping[str, int]] = None,
) -> None:
    """Reject a fresh/resumed canonical campaign whose theorem bytes drifted."""

    reason = locked_exact_artifact_contract_violation(
        project_root=project_root,
        artifact_hashes=artifact_hashes,
        artifact_sizes=artifact_sizes,
    )
    if reason is None:
        return
    key = reason.rsplit(":", 1)[-1]
    expected_hash = LOCKED_EXACT_ARTIFACT_SHA256.get(key)
    actual_hash = artifact_hashes.get(key)
    expected_size = LOCKED_EXACT_ARTIFACT_SIZE_BYTES.get(key)
    actual_size = None if artifact_sizes is None else artifact_sizes.get(key)
    detail_parts = [f"project_root={Path(project_root).resolve()}", f"artifact={key}"]
    if expected_hash is not None:
        detail_parts.extend(
            [f"expected_sha256={expected_hash}", f"actual_sha256={actual_hash}"]
        )
    if expected_size is not None:
        detail_parts.extend(
            [f"expected_size_bytes={expected_size}", f"actual_size_bytes={actual_size}"]
        )
    raise LockedExactArtifactContractError(reason, ", ".join(detail_parts))
