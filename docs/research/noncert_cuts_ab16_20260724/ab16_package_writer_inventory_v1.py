#!/usr/bin/env python3
"""Closed, research-only inventory of the prospective AB16 write surface.

This module is declarative.  It grants no write capability and does not make a
static source scan an authority proof.  The package-pinned broker, native
helper, retained descriptors, and closure actors remain the runtime
enforcement boundary.  The inventory exists so that adding a direct writer to
one of the prospective execution roles fails a focused governance check.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final


AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
PACKAGE_WRITER_INVENTORY_SCHEMA: Final = (
    "noncert-cuts-ab16-package-writer-inventory-v1"
)

FALSE_AUTHORITY: Final = MappingProxyType(
    {
        "changes_certified_exact": False,
        "changes_cut_state": False,
        "changes_lower_bound": False,
        "changes_production": False,
        "changes_upper_bound": False,
        "whole_witness_authorized": False,
    }
)

# Exact source files whose prospective path can reach a retained formal-root
# writer, an immutable append adapter, model export, terminal publication, or
# one of the three concurrency locks.  Phase-3 calibration roles and the
# pre-package Gate-A/Gate-B producer are deliberately outside this milestone.
PROSPECTIVE_EXECUTION_TOOL_FILES: Final = (
    "ab16_arm_attempt_closure_v1.py",
    "ab16_authority_v2.py",
    "ab16_budget_authority_v1.py",
    "ab16_budget_broker_v1.py",
    "ab16_budgeted_writers_v1.py",
    "ab16_campaign_bootstrap_v2.py",
    "ab16_closure_actor_v1.py",
    "ab16_final_release_actor_v1.py",
    "ab16_formal_campaign_v1.py",
    "ab16_formal_controller_v1.py",
    "ab16_formal_launch_authority_v1.py",
    "ab16_formal_launch_validator_v1.py",
    "ab16_formal_loader_v1.py",
    "ab16_formal_orchestrator_v1.py",
    "ab16_formal_success_verifier_v1.py",
    "ab16_native_budget_helper_v1.py",
    "ab16_outer_closeout_state_v1.py",
    "ab16_outer_guardian_v1.py",
    "ab16_outer_refunit_closeout_v1.py",
    "ab16_recovery_closeout_v1.py",
    "ab16_resource_admission_v1.py",
    "ab16_terminal_gate_v3.py",
    "baseline_admission_v1.py",
    "baseline_rebuild_v1.py",
    "cut_free_incumbent_replay_v1.py",
    "organic_arm_replay_v1.py",
    "organic_arm_runner_v1.py",
    "organic_resource_lifecycle_v2.py",
    "organic_resource_verifier_v2.py",
    "organic_unit_orchestrator_v2.py",
    "package_independent_verifier_v1.py",
    "replay_ab16_formal_root_alt_v1.py",
    "replay_ab16_formal_root_v1.py",
    "systemd_unit_reference_v1.py",
)

PROSPECTIVE_EXTERNAL_EXECUTION_TOOL_FILES: Final = (
    "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/"
    "campaign_authority_v4.py",
)

CORE_WRITER_FILES: Final = (
    "src/cuts/ledger.py",
    "src/models/cut_manager.py",
)

# Each route names the only authority that may perform the corresponding
# prospective write.  ``entrypoints`` are review anchors, not a replacement
# for the runtime broker/FD/Landlock checks.
WRITER_ROUTES: Final = MappingProxyType(
    {
        "append-channels": {
            "authority": "persistent-budget-broker",
            "entrypoints": (
                "ab16_budget_authority_v1.FormalBudgetBroker.append_segment",
                "ab16_budget_broker_v1.BrokerProcessFormalBudgetBackend.append_segment",
                "ab16_budgeted_writers_v1.AB16BudgetedCutLedgerWriter.append",
                "ab16_budgeted_writers_v1.AB16BudgetedCutManager.add_cut",
                "organic_arm_runner_v1.BrokerProcessArmBudgetBackend.append_segment",
            ),
            "path_contract": "registered-channel-segment-no-replace-v1",
        },
        "detached-replay": {
            "authority": "broker-post-seal-or-outside-closure-publisher",
            "entrypoints": (
                "ab16_arm_attempt_closure_v1.replay_and_publish_arm_attempt_root",
                "ab16_final_release_actor_v1._FinalReleaseServer._publish_replay_receipt",
                "organic_arm_runner_v1.BrokerProcessArmBudgetBackend.publish_accepted_arm_replay",
                "organic_arm_replay_v1.write_exclusive",
                "replay_ab16_formal_root_alt_v1.replay_formal_root",
                "replay_ab16_formal_root_v1.replay_formal_root",
            ),
            "path_contract": "root-closed-before-outside-no-overwrite-replay-v1",
        },
        "fixed-artifacts": {
            "authority": "persistent-budget-broker",
            "entrypoints": (
                "ab16_budget_authority_v1.FormalBudgetBroker.publish_bytes",
                "ab16_budget_authority_v1.FormalBudgetBroker.publish_preverified_descriptor",
                "ab16_budget_broker_v1.publish_preallocated_extent",
                "organic_arm_runner_v1.BrokerProcessArmBudgetBackend.publish_bytes",
            ),
            "path_contract": "retained-root-fd-preallocated-rename-noreplace-v1",
        },
        "model-export": {
            "authority": "native-helper-sealed-memfd-then-budget-broker",
            "entrypoints": (
                "ab16_budget_broker_v1.BrokerProcessFormalBudgetBackend.export_model_to_sealed_memfd",
                "organic_arm_runner_v1.BrokerProcessArmBudgetBackend.export_model_to_sealed_memfd",
            ),
            "path_contract": "rlimit-fsize-o-trunc-seal-scm-rights-no-replace-v1",
        },
        "scratch-tmpdir": {
            "authority": "budget-broker-directory-capability-plus-landlock",
            "entrypoints": (
                "ab16_budget_authority_v1.FormalBudgetBroker.register_directory",
                "ab16_budget_broker_v1.BrokerProcessFormalBudgetBackend.register_directory",
                "baseline_rebuild_v1._prepare_budget_workspace",
                "organic_arm_runner_v1._prepare_selected_attempt",
            ),
            "path_contract": "broker-created-read-only-worker-tmpdir-v1",
        },
        "terminal-cleanup": {
            "authority": "recovery-and-single-use-closure-actors",
            "entrypoints": (
                "ab16_budget_broker_v1._SharedBrokerRuntime.publish_release_terminal",
                "ab16_closure_actor_v1.ClosureServer._close",
                "ab16_final_release_actor_v1._FinalReleaseServer.run",
                "ab16_recovery_closeout_v1.RecoveryServer._takeover",
                "ab16_arm_attempt_closure_v1.publish_arm_attempt_manifest",
            ),
            "path_contract": "preallocated-closeout-disarm-manifest-no-writers-v1",
        },
    }
)

# Direct filesystem/FD mutation scopes admitted by the prospective runtime.
# The focused AST check requires every observed direct mutation in the closed
# source set to belong to this list.  Legacy fallbacks remain listed because
# their bytes are still supported, but prospective tests must prove that the
# budget-enabled path never reaches them.
DIRECT_MUTATION_SCOPES: Final = MappingProxyType(
    {
        "docs/research/noncert_cuts_ab16_20260724/ab16_authority_v2.py": (
            "_mkdir_exclusive",
            "_write_exclusive",
        ),
        "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/campaign_authority_v4.py": (
            "mkdir_exclusive",
            "write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_budget_authority_v1.py": (
            "FormalBudgetBroker.create",
            "FormalBudgetBroker.publish_bytes",
            "FormalBudgetBroker.publish_preverified_descriptor",
            "FormalBudgetBroker.register_directory",
            "FormalBudgetBroker.reserve_retained_staging",
            "RetainedStagingReservation.publish_bytes",
            "_rename_noreplace",
            "_write_all_at",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_budget_broker_v1.py": (
            "BrokerProcessFormalBudgetBackend._sealed_bytes_memfd",
            "BrokerProcessFormalBudgetBackend.export_model_to_sealed_memfd",
            "BrokerServer._prepare_closure",
            "BrokerServer._prepare_recovery",
            "FinalReleaseParentCapability.close",
            "_SharedBrokerRuntime.publish_release_terminal",
            "_prepare_extent",
            "_seal_abandoned_reservation",
            "_sealed_claim_memfd",
            "consume_once_extent",
            "publish_preallocated_extent",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_campaign_bootstrap_v2.py": (
            "_BootstrapBudgetAccount.register_directory",
            "_BootstrapBudgetAccount.reserve_retained_staging",
            "_BootstrapBudgetAccount.reserve_retained_staging_at_parent",
            "_BootstrapRetainedStaging.publish_bytes",
            "_bootstrap_budget_preallocate",
            "_bootstrap_budget_write_extent",
            "_bootstrap_mkdir_exclusive",
            "_rename_noreplace_at",
            "_bootstrap_write_exclusive",
            "_materialize_repository_snapshot",
            "_publish_package_independent_replay",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_final_release_actor_v1.py": (
            "_FinalReleaseServer._close_owned",
            "_FinalReleaseServer._seal_unselected",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_campaign_v1.py": (
            "acquire_formal_locks",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py": (
            "spawn_delayed_formal_launch_owner.publish_launch_artifact",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_native_budget_helper_v1.py": (
            "build_shared_object",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_guardian_v1.py": (
            "GuardianLockLease.evidence",
            "_chmod_bound_socket_at",
            "_rename_noreplace_at",
            "_restore_unverified_retirement",
            "_retire_bound_socket_at",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_refunit_closeout_v1.py": (
            "PinnedHost.lock_evidence",
        ),
        "docs/research/noncert_cuts_ab16_20260724/ab16_resource_admission_v1.py": (
            "HeldResourceLocks.acquire",
            "HeldResourceLocks.identities",
            "_open_launch_lock_probes",
        ),
        "docs/research/noncert_cuts_ab16_20260724/baseline_admission_v1.py": (
            "write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/baseline_rebuild_v1.py": (
            "_mkdir_exclusive",
            "_write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/cut_free_incumbent_replay_v1.py": (
            "_write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/organic_arm_replay_v1.py": (
            "write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py": (
            "BrokerProcessArmBudgetBackend._sealed_bytes_memfd",
            "BrokerProcessArmBudgetBackend.export_model_to_sealed_memfd",
            "HashChainJournal.__init__",
            "HashChainJournal.append",
            "_mkdir_exclusive",
            "_prepare_selected_attempt",
            "_write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/organic_resource_lifecycle_v2.py": (
            "write_exclusive",
        ),
        "docs/research/noncert_cuts_ab16_20260724/organic_resource_verifier_v2.py": (
            "write_exclusive",
        ),
        "src/cuts/ledger.py": (
            "CutLedgerWriter.__init__",
            "CutLedgerWriter._create_segment_exclusive",
            "CutLedgerWriter.append",
        ),
        "src/models/cut_manager.py": (
            "CutManager._ensure_dir",
            "CutManager.add_cut",
            "CutManager.clear_all",
        ),
    }
)

DISARMED_PACKAGE_WRITER_SCOPES: Final = frozenset(
    {
        # The post-verifier loader deletes this reproducible-build utility and
        # its subprocess binding before exposing the native-helper wrapper.
        "ab16_native_budget_helper_v1.build_shared_object",
    }
)

LEGACY_DIRECT_WRITER_SCOPES: Final = frozenset(
    {
        "baseline_admission_v1.write_exclusive",
        "baseline_rebuild_v1._mkdir_exclusive",
        "baseline_rebuild_v1._write_exclusive",
        "cut_free_incumbent_replay_v1._write_exclusive",
        "organic_arm_replay_v1.write_exclusive",
        "organic_arm_runner_v1.HashChainJournal.__init__",
        "organic_arm_runner_v1.HashChainJournal.append",
        "organic_arm_runner_v1._mkdir_exclusive",
        "organic_arm_runner_v1._prepare_selected_attempt",
        "organic_arm_runner_v1._write_exclusive",
        "organic_resource_lifecycle_v2.write_exclusive",
        "organic_resource_verifier_v2.write_exclusive",
        "src.cuts.ledger.CutLedgerWriter.__init__",
        "src.cuts.ledger.CutLedgerWriter._create_segment_exclusive",
        "src.cuts.ledger.CutLedgerWriter.append",
        "src.models.cut_manager.CutManager._ensure_dir",
        "src.models.cut_manager.CutManager.add_cut",
        "src.models.cut_manager.CutManager.clear_all",
    }
)

__all__ = [
    "AUTHORITY_SCOPE",
    "CORE_WRITER_FILES",
    "DIRECT_MUTATION_SCOPES",
    "DISARMED_PACKAGE_WRITER_SCOPES",
    "FALSE_AUTHORITY",
    "LEGACY_DIRECT_WRITER_SCOPES",
    "PACKAGE_WRITER_INVENTORY_SCHEMA",
    "PROSPECTIVE_EXTERNAL_EXECUTION_TOOL_FILES",
    "PROSPECTIVE_EXECUTION_TOOL_FILES",
    "WRITER_ROUTES",
]
