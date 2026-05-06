from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_patch_spec_revision import (
    build_signature_bucket_patch_spec_revision,
    write_signature_bucket_patch_spec_revision,
)


def test_signature_bucket_patch_spec_revision_classifies_s38_blocker(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)

    revision = build_signature_bucket_patch_spec_revision(**paths)

    assert revision["status"] == "completed"
    assert (
        revision["interpretation"]["classification"]
        == "output_path_finalization_revision_required"
    )
    assert revision["source_mutation_performed"] is False
    assert revision["interpretation"]["implementation_allowed_now"] is False
    assert revision["review_required_before_authorization"] is True
    revised = revision["revised_patch_spec"]
    assert revised["collection_method"].endswith(
        "_apply_ghost_anchor_signature_bucket_tightening"
    )
    assert revised["companion_finalization_method"].endswith(
        "_add_global_valid_inequalities"
    )
    assert (
        revised["collection_stats_path"]
        == "_ghost_anchor_signature_bucket_tightening_stats.signature_tightening_instrumentation"
    )
    assert (
        revised["final_build_stats_output_path"]
        == "build_stats.global_valid_inequalities.signature_bucket_capacity_bounds."
        "signature_tightening_instrumentation"
    )
    assert revised["mandatory_required_optional_separation"] is True
    assert "rect_idx" in revised["required_top_entry_fields"]
    assert "bucket_id" in revised["required_top_entry_fields"]
    assert revision["recommendation"]["action"] == "prepare_signature_bucket_re_review_package"


def test_signature_bucket_patch_spec_revision_holds_for_incomplete_reply(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    paths["review_reply_path"].write_text("looks fine\n", encoding="utf-8")

    revision = build_signature_bucket_patch_spec_revision(**paths)

    assert revision["status"] == "manual_review_required"
    assert revision["interpretation"]["classification"] == "manual_review_required"
    assert revision["revised_patch_spec"] == {}
    assert revision["recommendation"]["action"] == "hold_for_manual_review"


def test_signature_bucket_patch_spec_revision_write_mode_is_namespaced(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    revision = build_signature_bucket_patch_spec_revision(**paths)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "39_signature_bucket_patch_spec_revision"
    )

    written = write_signature_bucket_patch_spec_revision(revision, output_dir)

    assert written["json"] == output_dir / "signature_bucket_patch_spec_revision.json"
    assert written["md"] == output_dir / "signature_bucket_patch_spec_revision.md"
    payload = json.loads(written["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == "prepare_signature_bucket_re_review_package"


def test_signature_bucket_patch_spec_revision_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    revision = build_signature_bucket_patch_spec_revision(**paths)

    with pytest.raises(ValueError, match="signature bucket patch spec revision namespace"):
        write_signature_bucket_patch_spec_revision(revision, tmp_path / "bad")


def _write_inputs(root: Path) -> dict[str, Path]:
    strategy_path = root / "s36.json"
    original_spec_path = root / "s37.json"
    review_reply_path = root / "s38_reply.md"
    strategy_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "signature_bucket_internal_loop_strategy_required"
                },
                "source_model_mutation": False,
                "source_mutation_performed": False,
                "no_solve": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original_spec_path.write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {"implementation_allowed_now": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    review_reply_path.write_text(
        "\n".join(
            [
                "Review does not pass yet.",
                "The main blocker is a scope/output-path mismatch.",
                "_apply_ghost_anchor_signature_bucket_tightening runs before _add_global_valid_inequalities.",
                "Later, _add_global_valid_inequalities reconstructs and assigns build_stats.",
                "Instrumentation written directly to that path would likely be overwritten.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "strategy_path": strategy_path,
        "original_spec_path": original_spec_path,
        "review_reply_path": review_reply_path,
    }
