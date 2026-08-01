"""AB16-only immutable adapters for the production cut writer interfaces.

The production ``CutLedgerWriter`` and ``CutManager`` remain byte-for-byte
unchanged and keep their ordinary mutable-file behavior.  A prospective AB16
worker imports these adapters only after package and snapshot verification,
then supplies an already connected broker capability.  Every retained byte is
published through that capability before the corresponding in-memory state is
advanced; this module owns no writable directory or staging descriptor.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Protocol

from src.cuts.ledger import (
    EVENT_TYPES,
    LEDGER_SCHEMA_VERSION,
    LedgerUsageError,
    LedgerWriteError,
    default_writer_id,
)
from src.models.cut_manager import CutManager


_GENESIS_ANCHOR = "0" * 64


class ImmutableAppendBudget(Protocol):
    """Narrow broker surface accepted by both immutable adapters."""

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]: ...


def _require_safe_component(value: str, *, field_name: str) -> None:
    if (
        not value
        or value in {".", ".."}
        or any(character in value for character in ("/", "\\", "\x00"))
    ):
        raise LedgerUsageError(f"invalid {field_name}: {value!r}")


def _require_positive_exact_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LedgerUsageError(f"{field_name} must be a positive exact integer")
    return value


def _canonical_event_line(event: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(event),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validated_receipt(
    raw_receipt: Mapping[str, object],
    payload: bytes,
    *,
    label: str,
) -> dict[str, object]:
    receipt = dict(raw_receipt)
    if not {"path", "sha256", "size_bytes"} <= set(receipt):
        raise LedgerWriteError(f"{label} receipt lacks identity fields")
    if (
        not isinstance(receipt["path"], str)
        or not receipt["path"]
        or receipt["sha256"] != hashlib.sha256(payload).hexdigest()
        or receipt["size_bytes"] != len(payload)
    ):
        raise LedgerWriteError(f"{label} receipt identity differs")
    return receipt


class AB16BudgetedCutLedgerWriter:
    """Duck-typed cut ledger whose events are immutable broker segments."""

    def __init__(
        self,
        root_dir: Path,
        *,
        scope_id: str,
        immutable_budget: ImmutableAppendBudget,
        budget_channel: str,
        budget_segment_max_bytes: int,
        genesis_context: Mapping[str, Any] | None = None,
        writer_id: str | None = None,
        budget_arm_slot: str | None = None,
        budget_event_limits: Mapping[str, int] | None = None,
    ) -> None:
        _require_safe_component(scope_id, field_name="scope_id")
        resolved_writer_id = writer_id or default_writer_id()
        _require_safe_component(resolved_writer_id, field_name="writer_id")
        _require_safe_component(budget_channel, field_name="budget_channel")
        if budget_arm_slot is not None:
            _require_safe_component(budget_arm_slot, field_name="budget_arm_slot")
        maximum = _require_positive_exact_integer(
            budget_segment_max_bytes,
            field_name="budget_segment_max_bytes",
        )
        if not hasattr(immutable_budget, "append_segment"):
            raise LedgerUsageError("immutable_budget lacks append_segment")

        event_limits: dict[str, int] = {}
        if budget_event_limits is not None:
            if not isinstance(budget_event_limits, Mapping):
                raise LedgerUsageError("budget_event_limits must be a mapping")
            for event_type, raw_limit in budget_event_limits.items():
                if event_type not in EVENT_TYPES:
                    raise LedgerUsageError(
                        "budget_event_limits contains an unknown event type"
                    )
                if (
                    isinstance(raw_limit, bool)
                    or not isinstance(raw_limit, int)
                    or raw_limit < 0
                ):
                    raise LedgerUsageError(
                        "budget_event_limits values must be exact nonnegative integers"
                    )
                event_limits[event_type] = raw_limit

        # ``root_dir`` is retained only as a diagnostic label.  This adapter
        # deliberately never creates, opens, scans, or removes that path.
        self._diagnostic_root = Path(root_dir)
        self._scope_id = scope_id
        self._writer_id = resolved_writer_id
        self._immutable_budget = immutable_budget
        self._budget_channel = budget_channel
        self._budget_segment_max_bytes = maximum
        self._budget_arm_slot = budget_arm_slot
        self._budget_event_limits = event_limits
        self._budget_event_counts: dict[str, int] = {}
        self._budget_records: list[dict[str, object]] = []
        self._budget_events: list[dict[str, Any]] = []
        self._seq = 0
        self._prev_hash = _GENESIS_ANCHOR
        self._sealed = False

        genesis: dict[str, Any] = dict(genesis_context or {})
        genesis.setdefault("predecessor_segment", None)
        genesis.setdefault("predecessor_tail_hash", None)
        genesis.setdefault("recovery_reason", "fresh_start")
        self.append("GENESIS", genesis)

    @property
    def path(self) -> Path:
        raise LedgerUsageError(
            "an AB16 budgeted ledger has immutable segment records, not one mutable path"
        )

    @property
    def writer_id(self) -> str:
        return self._writer_id

    @property
    def tail_hash(self) -> str:
        return self._prev_hash

    @property
    def is_budgeted(self) -> bool:
        return True

    @property
    def immutable_segment_records(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(record) for record in self._budget_records)

    @property
    def recorded_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._budget_events)

    def append(self, event_type: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        if self._sealed:
            raise LedgerUsageError("segment already sealed; open a new segment")
        if event_type not in EVENT_TYPES:
            raise LedgerUsageError(f"unknown ledger event type: {event_type!r}")
        reserved = {"seq", "event", "prev_event_hash", "schema_version"}
        clash = reserved.intersection(fields)
        if clash:
            raise LedgerUsageError(f"caller may not set reserved fields: {clash}")

        event: dict[str, Any] = dict(fields)
        event["schema_version"] = LEDGER_SCHEMA_VERSION
        event["event"] = event_type
        event["seq"] = self._seq
        event["prev_event_hash"] = self._prev_hash
        event.setdefault("writer_id", self._writer_id)
        event.setdefault("scope_id", self._scope_id)
        event.setdefault("wallclock_utc", time.time())
        line = _canonical_event_line(event)
        payload = line + b"\n"

        event_limit = self._budget_event_limits.get(event_type)
        if (
            event_limit is not None
            and self._budget_event_counts.get(event_type, 0) >= event_limit
        ):
            raise LedgerWriteError(
                "immutable ledger event limit exhausted before publication"
            )
        if len(payload) > self._budget_segment_max_bytes:
            raise LedgerWriteError(
                "ledger event exceeds its predeclared immutable segment allocation"
            )
        try:
            receipt = _validated_receipt(
                self._immutable_budget.append_segment(
                    self._budget_channel,
                    self._seq,
                    payload,
                    maximum_bytes=self._budget_segment_max_bytes,
                    artifact_class="ledger",
                    arm_slot=self._budget_arm_slot,
                ),
                payload,
                label="immutable ledger",
            )
        except LedgerWriteError:
            raise
        except Exception as exc:
            raise LedgerWriteError(
                f"immutable ledger publication failed: {exc}"
            ) from exc

        self._budget_records.append(receipt)
        self._budget_events.append(dict(event))
        self._budget_event_counts[event_type] = (
            self._budget_event_counts.get(event_type, 0) + 1
        )
        self._seq += 1
        self._prev_hash = hashlib.sha256(line).hexdigest()
        if event_type == "SEGMENT_SEAL":
            self._sealed = True
        return event

    def seal(self, fields: Mapping[str, Any] | None = None) -> None:
        if not self._sealed:
            self.append("SEGMENT_SEAL", dict(fields or {}))

    def __enter__(self) -> AB16BudgetedCutLedgerWriter:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.seal()
        else:
            self._sealed = True


class AB16BudgetedCutManager(CutManager):
    """CutManager-compatible runtime registry with broker-only persistence."""

    def __init__(
        self,
        checkpoint_dir: Path,
        *,
        immutable_budget: ImmutableAppendBudget,
        budget_channel: str,
        budget_segment_max_bytes: int,
        solve_mode: str = "exploratory",
        current_hashes: Mapping[str, str] | None = None,
        budget_arm_slot: str | None = None,
    ) -> None:
        _require_safe_component(budget_channel, field_name="budget_channel")
        if budget_arm_slot is not None:
            _require_safe_component(budget_arm_slot, field_name="budget_arm_slot")
        maximum = _require_positive_exact_integer(
            budget_segment_max_bytes,
            field_name="budget_segment_max_bytes",
        )
        if not hasattr(immutable_budget, "append_segment"):
            raise LedgerUsageError("immutable_budget lacks append_segment")

        # Reproduce the in-memory portion of CutManager.__init__ without
        # calling its filesystem-initializing path.  Inherited query and
        # structured-cut helpers continue to operate on these same fields.
        self.checkpoint_dir = Path(checkpoint_dir)
        self.solve_mode = str(solve_mode)
        self.current_hashes = (
            {str(key): str(value) for key, value in current_hashes.items()}
            if current_hashes is not None
            else {}
        )
        self.cuts_file = self.checkpoint_dir / "benders_cuts.jsonl"
        self.cuts = []
        self._cut_signatures = set()
        self.active_cuts = set()
        self._immutable_budget = immutable_budget
        self._budget_channel = budget_channel
        self._budget_segment_max_bytes = maximum
        self._budget_arm_slot = budget_arm_slot
        self._budget_sequence = 0
        self._budget_records: list[dict[str, object]] = []

    def _ensure_dir(self) -> None:
        """Budgeted construction owns no writable checkpoint directory."""

    def load_cuts(self) -> None:
        """Disk replay is forbidden for the immutable audit-only channel."""

        self.active_cuts.clear()

    def add_cut(
        self,
        conflict_set: list[dict[str, str]],
        reason: str,
        source: str,
    ) -> bool:
        frozen_conflict = self._runtime_signature(conflict_set)
        if frozen_conflict in self.active_cuts:
            return False
        cut_record = {
            "source": source,
            "reason": reason,
            "conflict_set": conflict_set,
        }
        payload = (json.dumps(cut_record, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        if len(payload) > self._budget_segment_max_bytes:
            raise RuntimeError(
                "runtime cut exceeds its predeclared immutable segment allocation"
            )
        receipt = _validated_receipt(
            self._immutable_budget.append_segment(
                self._budget_channel,
                self._budget_sequence,
                payload,
                maximum_bytes=self._budget_segment_max_bytes,
                artifact_class="ledger",
                arm_slot=self._budget_arm_slot,
            ),
            payload,
            label="immutable cut",
        )
        self._budget_records.append(receipt)
        self._budget_sequence += 1
        self.active_cuts.add(frozen_conflict)
        return True

    @property
    def immutable_segment_records(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(record) for record in self._budget_records)

    def clear_all(self) -> None:
        raise RuntimeError("immutable budget channels cannot be cleared or reused")


__all__ = [
    "AB16BudgetedCutLedgerWriter",
    "AB16BudgetedCutManager",
    "ImmutableAppendBudget",
]
