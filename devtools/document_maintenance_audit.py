#!/usr/bin/env python3
"""Read-only periodic maintenance audit for the self-describing document system.

The audit intentionally consumes existing policy, knowledge and lifecycle ledgers.
It never writes a second semantic truth source.  Findings are either mechanical
errors, overdue review triggers, or informational queues that must be resolved
through the same intake/knowledge/policy write path used by ordinary changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import os
import subprocess
from typing import Any, Iterable, Mapping, Sequence


_SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


class MaintenanceAuditError(RuntimeError):
    """Fail-closed maintenance-audit error."""


@dataclass(frozen=True)
class MaintenanceFinding:
    check_id: str
    kind: str
    severity: str
    subject: str
    message: str
    action_ids: tuple[str, ...]
    details: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "kind": self.kind,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
            "action_ids": list(self.action_ids),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class MaintenanceAuditResult:
    profile: str
    as_of: date
    snapshot_as_of: date
    fail_on: tuple[str, ...]
    findings: tuple[MaintenanceFinding, ...]

    @property
    def counts(self) -> Mapping[str, int]:
        return {
            severity: sum(finding.severity == severity for finding in self.findings)
            for severity in ("error", "warning", "info")
        }

    @property
    def passed(self) -> bool:
        blocked = set(self.fail_on)
        return all(finding.severity not in blocked for finding in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "as_of": self.as_of.isoformat(),
            "snapshot_as_of": self.snapshot_as_of.isoformat(),
            "fail_on": list(self.fail_on),
            "passed": self.passed,
            "counts": dict(self.counts),
            "findings": [finding.as_dict() for finding in self.findings],
        }


def parse_audit_date(value: str | None, *, default: date | None = None) -> date:
    """Parse an ISO date used by a deterministic audit run."""

    if value is None:
        return default or date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MaintenanceAuditError(f"invalid audit date {value!r}; expected YYYY-MM-DD") from exc


def run_maintenance_audit(
    system: Any,
    *,
    profile: str,
    as_of: date,
) -> MaintenanceAuditResult:
    """Run one manifest-owned audit profile without changing repository state."""

    profiles = system.maintenance_audit_profiles
    checks = system.maintenance_audit_checks
    profile_record = profiles.get(profile)
    if profile_record is None:
        raise MaintenanceAuditError(
            f"unknown maintenance profile {profile!r}; available: {', '.join(sorted(profiles))}"
        )

    snapshot_as_of = parse_audit_date(str(system.maintenance_audit_payload["snapshot_as_of"]))
    findings: list[MaintenanceFinding] = []
    handlers = {
        "audit_snapshot_age": _check_audit_snapshot_age,
        "ephemeral_expiry": _check_ephemeral_expiry,
        "active_dossier_age": _check_active_dossier_age,
        "triage_backlog": _check_triage_backlog,
        "review_followups": _check_review_followups,
        "living_freshness": _check_living_freshness,
        "deprecated_knowledge_references": _check_deprecated_knowledge_references,
        "terminology_collision": _check_terminology_collision,
        "topic_coverage": _check_topic_coverage,
        "open_claim_queue": _check_open_claim_queue,
        "phase_boundary_surface": _check_phase_boundary_surface,
    }
    for check_id in profile_record["check_ids"]:
        record = checks[str(check_id)]
        kind = str(record["kind"])
        handler = handlers.get(kind)
        if handler is None:
            raise MaintenanceAuditError(f"unsupported maintenance check kind: {kind}")
        findings.extend(handler(system, record, as_of, snapshot_as_of))

    findings.sort(
        key=lambda item: (
            -_SEVERITY_ORDER[item.severity],
            item.check_id,
            item.subject,
            item.message,
        )
    )
    return MaintenanceAuditResult(
        profile=profile,
        as_of=as_of,
        snapshot_as_of=snapshot_as_of,
        fail_on=tuple(str(value) for value in profile_record["fail_on"]),
        findings=tuple(findings),
    )


def _finding(
    record: Mapping[str, Any],
    severity: str,
    subject: str,
    message: str,
    **details: Any,
) -> MaintenanceFinding:
    if severity not in _SEVERITY_ORDER:
        raise MaintenanceAuditError(f"unsupported maintenance severity: {severity}")
    return MaintenanceFinding(
        check_id=str(record["id"]),
        kind=str(record["kind"]),
        severity=severity,
        subject=subject,
        message=message,
        action_ids=tuple(str(value) for value in record.get("action_ids", [])),
        details=details,
    )


def _required_days(parameters: Mapping[str, Any], key: str) -> int:
    value = parameters.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MaintenanceAuditError(f"maintenance parameter {key} must be a positive integer")
    return value


def _age_severity(age_days: int, parameters: Mapping[str, Any]) -> str:
    warning_days = _required_days(parameters, "warning_days")
    error_days = _required_days(parameters, "error_days")
    if warning_days >= error_days:
        raise MaintenanceAuditError("warning_days must be less than error_days")
    if age_days >= error_days:
        return "error"
    if age_days >= warning_days:
        return "warning"
    return "info"


def _record_date(record: Mapping[str, Any], *keys: str) -> date | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return parse_audit_date(value)
    return None


def _check_audit_snapshot_age(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del system
    age_days = (as_of - snapshot_as_of).days
    if age_days < 0:
        return (
            _finding(
                record,
                "error",
                "maintenance-snapshot",
                f"维护投影快照 {snapshot_as_of} 晚于审计日期 {as_of}。",
                age_days=age_days,
            ),
        )
    severity = _age_severity(age_days, record["parameters"])
    return (
        _finding(
            record,
            severity,
            "maintenance-snapshot",
            f"维护投影快照日期为 {snapshot_as_of}，距本次审计 {age_days} 天。",
            age_days=age_days,
        ),
    )


def _check_ephemeral_expiry(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del snapshot_as_of
    findings: list[MaintenanceFinding] = []
    records = system.ephemeral_payload.get("records", [])
    for item in records:
        expires_at = _record_date(item, "expires_at")
        if expires_at is None:
            findings.append(
                _finding(record, "error", str(item.get("path", "unknown")), "临时文档缺少有效 expires_at。")
            )
            continue
        remaining = (expires_at - as_of).days
        severity = "error" if remaining < 0 else "warning" if remaining <= 7 else "info"
        if remaining < 0:
            message = f"临时文档已过期 {-remaining} 天，必须执行 {item['exit_action']} 退出事务。"
        else:
            message = f"临时文档距到期还有 {remaining} 天，退出动作是 {item['exit_action']}。"
        findings.append(
            _finding(
                record,
                severity,
                str(item["path"]),
                message,
                expires_at=expires_at.isoformat(),
                exit_action=str(item["exit_action"]),
                successor_path=item.get("successor_path"),
            )
        )
    if not findings:
        findings.append(_finding(record, "info", "ephemeral-registry", "当前没有登记中的临时文档。", count=0))
    return tuple(findings)


def _check_active_dossier_age(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del snapshot_as_of
    system._ensure_knowledge()
    dossiers = system._dossiers or ()
    findings: list[MaintenanceFinding] = []
    for dossier in dossiers:
        if dossier.get("lifecycle") != "active":
            continue
        workflow = dossier.get("workflow")
        opened_at = _record_date(workflow, "opened_at") if isinstance(workflow, Mapping) else None
        opened_at = opened_at or _record_date(dossier, "date")
        if opened_at is None:
            findings.append(
                _finding(
                    record,
                    "info",
                    str(dossier["id"]),
                    "active dossier 没有可用于年龄计算的 opened_at/date；保持显式人工复核。",
                    path=str(dossier["path"]),
                )
            )
            continue
        age_days = (as_of - opened_at).days
        severity = _age_severity(max(age_days, 0), record["parameters"])
        findings.append(
            _finding(
                record,
                severity,
                str(dossier["id"]),
                f"active dossier 已打开 {age_days} 天；应继续工作、更新 next action，或以 typed outcome 关闭。",
                path=str(dossier["path"]),
                opened_at=opened_at.isoformat(),
                age_days=age_days,
            )
        )
    if not findings:
        findings.append(_finding(record, "info", "active-dossiers", "当前没有 active dossier。", count=0))
    return tuple(findings)


def _check_triage_backlog(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del snapshot_as_of
    system._ensure_knowledge()
    source = Path(system.root) / str(system.manifest["knowledge_sources"]["backfill_triage"])
    payload = _read_json_object(source)
    reviewed_at = parse_audit_date(str(payload["ledger_reviewed_at"]))
    age_days = (as_of - reviewed_at).days
    severity = _age_severity(max(age_days, 0), record["parameters"])
    groups = tuple((system._triage_groups or {}).values())
    findings: list[MaintenanceFinding] = [
        _finding(
            record,
            severity,
            "backfill-triage-ledger",
            f"triage ledger 最近复核于 {reviewed_at}，当前包含 {len(groups)} 个分组。",
            age_days=age_days,
            group_count=len(groups),
            dossier_count=sum(len(group.get("dossier_ids", [])) for group in groups),
        )
    ]
    for group in groups:
        findings.append(
            _finding(
                record,
                "info",
                str(group["id"]),
                f"{len(group.get('dossier_ids', []))} 个 dossier 处于 {group['disposition']}，优先级 {group['priority']}。",
                dossier_count=len(group.get("dossier_ids", [])),
                disposition=str(group["disposition"]),
                priority=str(group["priority"]),
                reopen_triggers=list(group.get("reopen_triggers", [])),
            )
        )
    return tuple(findings)


def _check_review_followups(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del snapshot_as_of
    system._ensure_knowledge()
    reviews = tuple((system._backfill_reviews or {}).values())
    findings: list[MaintenanceFinding] = []
    for review in reviews:
        if review.get("status") != "current" or not review.get("unresolved"):
            continue
        reviewed_at = _record_date(review, "reviewed_at")
        if reviewed_at is None:
            severity = "error"
            age_days = None
        else:
            age_days = (as_of - reviewed_at).days
            severity = _age_severity(max(age_days, 0), record["parameters"])
        unresolved = [str(value) for value in review.get("unresolved", [])]
        findings.append(
            _finding(
                record,
                severity,
                str(review["id"]),
                f"current review 保留 {len(unresolved)} 个未决项；重审触发：{review['next_review_trigger']}",
                dossier_id=str(review["dossier_id"]),
                reviewed_at=review.get("reviewed_at"),
                age_days=age_days,
                unresolved=unresolved,
                next_review_trigger=str(review["next_review_trigger"]),
            )
        )
    if not findings:
        findings.append(_finding(record, "info", "review-followups", "current semantic review 没有未决项。", count=0))
    return tuple(findings)


def _check_living_freshness(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del snapshot_as_of
    parameters = record["parameters"]
    allowed_classes = {str(value) for value in parameters.get("document_classes", [])}
    warning_multiplier = float(parameters.get("warning_multiplier", 1.0))
    error_multiplier = float(parameters.get("error_multiplier", 2.0))
    if warning_multiplier <= 0 or error_multiplier <= warning_multiplier:
        raise MaintenanceAuditError("living freshness multipliers must satisfy 0 < warning < error")

    current_paths = tuple(system.convergence_audit()["current_paths"])
    candidates: list[tuple[str, Mapping[str, Any], int]] = []
    for relpath in current_paths:
        resolution = system.resolve(str(relpath), "read")
        contract = resolution.contract
        if contract.get("document_class") not in allowed_classes:
            continue
        max_days = contract.get("review_policy", {}).get("max_interval_days")
        if not isinstance(max_days, int) or isinstance(max_days, bool) or max_days <= 0:
            continue
        candidates.append((str(relpath), contract, max_days))

    root = Path(system.root)
    candidate_paths = [path for path, _, _ in candidates]
    touches = dict(_last_touch_dates(root, candidate_paths))
    # A patch-applied or otherwise Git-visible change is a fresh maintenance
    # trigger even before it is committed. Overlaying the deterministic audit
    # date keeps generated projections identical before and after commit.
    changed_paths = _git_changed_paths(root)
    for relpath in candidate_paths:
        if relpath in changed_paths:
            touches[relpath] = as_of
    findings: list[MaintenanceFinding] = []
    for relpath, contract, max_days in candidates:
        touched = touches.get(relpath)
        if touched is None:
            findings.append(
                _finding(
                    record,
                    "info",
                    relpath,
                    "当前 Git 图中没有该文档的已提交触达日期；新建或未提交路径不据此判定陈旧。",
                    max_interval_days=max_days,
                )
            )
            continue
        age_days = (as_of - touched).days
        warning_days = max(1, int(max_days * warning_multiplier))
        error_days = max(warning_days + 1, int(max_days * error_multiplier))
        if age_days < warning_days:
            continue
        severity = "error" if age_days >= error_days else "warning"
        findings.append(
            _finding(
                record,
                severity,
                relpath,
                f"距最近 Git 触达 {age_days} 天，超过 policy 复核间隔 {max_days} 天；需要语义复核而非仅刷新日期。",
                document_class=str(contract["document_class"]),
                last_touched=touched.isoformat(),
                age_days=age_days,
                max_interval_days=max_days,
            )
        )
    findings.append(
        _finding(
            record,
            "info",
            "living-freshness-summary",
            f"按 review_policy 检查了 {len(candidates)} 份 current 文档；Git 日期仅作为重审触发器。",
            checked_count=len(candidates),
            overdue_count=sum(item.severity in {"warning", "error"} for item in findings),
        )
    )
    return tuple(findings)


def _check_deprecated_knowledge_references(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del as_of, snapshot_as_of
    system._ensure_knowledge()
    parameters = record["parameters"]
    deprecated_statuses = {str(value) for value in parameters.get("deprecated_statuses", [])}
    allowed_tokens = tuple(str(value).casefold() for value in parameters.get("allowed_context_tokens", []))
    deprecated = {
        claim_id: str(claim.get("status"))
        for claim_id, claim in (system._claims or {}).items()
        if claim.get("status") in deprecated_statuses
    }
    current_paths = tuple(system.convergence_audit()["current_paths"])
    findings: list[MaintenanceFinding] = []
    scanned = 0
    for relpath in current_paths:
        resolution = system.resolve(str(relpath), "read")
        if resolution.contract.get("document_class") == "generated_projection":
            continue
        path = Path(system.root) / str(relpath)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(_finding(record, "error", str(relpath), f"无法读取 current 文档：{exc}"))
            continue
        scanned += 1
        for line_number, line in enumerate(lines, start=1):
            line_folded = line.casefold()
            for claim_id, status in deprecated.items():
                if claim_id not in line:
                    continue
                if any(token in line_folded for token in allowed_tokens):
                    continue
                findings.append(
                    _finding(
                        record,
                        "error",
                        f"{relpath}:{line_number}",
                        f"current 手写文档引用 {status} claim {claim_id}，但同一行没有显式历史/失效语境。",
                        claim_id=claim_id,
                        claim_status=status,
                        line=line.strip(),
                    )
                )
    if not findings:
        findings.append(
            _finding(
                record,
                "info",
                "deprecated-reference-summary",
                f"扫描 {scanned} 份 current 手写文档，没有发现无语境的失效 claim 引用。",
                scanned_count=scanned,
                deprecated_claim_count=len(deprecated),
            )
        )
    return tuple(findings)


def _check_terminology_collision(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del as_of, snapshot_as_of
    system._ensure_knowledge()
    terms = tuple((system._terms or {}).values())
    owners: dict[str, str] = {}
    labels: dict[str, str] = {}
    findings: list[MaintenanceFinding] = []
    for term in terms:
        term_id = str(term["id"])
        values = [str(term["canonical_label"]), *(str(value) for value in term.get("aliases", []))]
        for value in values:
            normalized = " ".join(value.casefold().split())
            previous = owners.get(normalized)
            if previous is not None and previous != term_id:
                findings.append(
                    _finding(
                        record,
                        "error",
                        value,
                        f"术语标签 {value!r} 同时属于 {previous} 与 {term_id}。",
                        normalized=normalized,
                        first_term_id=previous,
                        second_term_id=term_id,
                        first_label=labels[normalized],
                    )
                )
            else:
                owners[normalized] = term_id
                labels[normalized] = value
    if not findings:
        findings.append(
            _finding(
                record,
                "info",
                "terminology-summary",
                f"{len(terms)} 个 term 的 canonical label 与 alias 没有跨 ID 碰撞。",
                term_count=len(terms),
                label_count=len(owners),
            )
        )
    return tuple(findings)


def _check_topic_coverage(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del as_of, snapshot_as_of
    system._ensure_knowledge()
    claims = system._claims or {}
    terms = system._terms or {}
    topics = system._topics or {}
    visible = set(system.visible_paths())
    findings: list[MaintenanceFinding] = []
    open_coverage: set[str] = set()
    for topic_id, topic in topics.items():
        for claim_id in topic.get("claim_ids", []):
            if str(claim_id) not in claims:
                findings.append(_finding(record, "error", topic_id, f"topic 引用未知 claim：{claim_id}"))
        for claim_id in topic.get("open_question_claim_ids", []):
            claim_key = str(claim_id)
            open_coverage.add(claim_key)
            claim = claims.get(claim_key)
            if claim is None:
                findings.append(_finding(record, "error", topic_id, f"topic 引用未知 open claim：{claim_id}"))
            elif claim.get("status") != "open":
                findings.append(
                    _finding(record, "error", topic_id, f"open_question_claim_ids 包含非 open claim：{claim_id}")
                )
        for term_id in topic.get("term_ids", []):
            if str(term_id) not in terms:
                findings.append(_finding(record, "error", topic_id, f"topic 引用未知 term：{term_id}"))
        for entry_path in topic.get("entry_paths", []):
            if str(entry_path) not in visible:
                findings.append(_finding(record, "error", topic_id, f"topic 入口不存在或不可见：{entry_path}"))
    for claim_id, claim in claims.items():
        if claim.get("status") == "open" and claim_id not in open_coverage:
            findings.append(_finding(record, "error", claim_id, "open claim 没有进入任何 topic 的开放问题坐标。"))
    if not findings:
        findings.append(
            _finding(
                record,
                "info",
                "topic-summary",
                f"{len(topics)} 个 topic 的 claim、term、entry 与 open-claim 坐标完整。",
                topic_count=len(topics),
                open_claim_count=sum(claim.get("status") == "open" for claim in claims.values()),
            )
        )
    return tuple(findings)


def _check_open_claim_queue(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del as_of, snapshot_as_of
    system._ensure_knowledge()
    open_claims = sorted(
        (claim for claim in (system._claims or {}).values() if claim.get("status") == "open"),
        key=lambda claim: str(claim["id"]),
    )
    if not open_claims:
        return (_finding(record, "info", "open-claims", "当前没有 status=open 的 claim。", count=0),)
    return tuple(
        _finding(
            record,
            "info",
            str(claim["id"]),
            str(claim["title"]),
            authority=str(claim.get("authority", "")),
            scope=list(claim.get("scope", [])),
            updated_at=claim.get("updated_at"),
        )
        for claim in open_claims
    )


def _check_phase_boundary_surface(
    system: Any,
    record: Mapping[str, Any],
    as_of: date,
    snapshot_as_of: date,
) -> Sequence[MaintenanceFinding]:
    del as_of, snapshot_as_of
    system._ensure_knowledge()
    dossiers = tuple(system._dossiers or ())
    reviews = tuple((system._backfill_reviews or {}).values())
    claims = tuple((system._claims or {}).values())
    groups = tuple((system._triage_groups or {}).values())
    ephemeral = tuple(system.ephemeral_payload.get("records", []))
    return (
        _finding(
            record,
            "info",
            "phase-boundary-inventory",
            "阶段边界必须逐项处置 active workflow、语义未决项、长尾分诊、开放命题与临时材料；清单不自动授予 close。",
            active_dossiers=sum(item.get("lifecycle") == "active" for item in dossiers),
            triage_groups=len(groups),
            triaged_dossiers=sum(len(item.get("dossier_ids", [])) for item in groups),
            unresolved_current_reviews=sum(
                item.get("status") == "current" and bool(item.get("unresolved")) for item in reviews
            ),
            open_claims=sum(item.get("status") == "open" for item in claims),
            ephemeral_documents=len(ephemeral),
        ),
    )


def _git_changed_paths(root: Path) -> set[str]:
    """Return tracked and untracked Git-visible changes without mutating Git state."""

    commands = (
        ("git", "diff", "--name-only", "-z", "HEAD", "--"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    )
    changed: set[str] = set()
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            return set()
        changed.update(
            os.fsdecode(raw_path)
            for raw_path in completed.stdout.split(b"\0")
            if raw_path
        )
    return changed


def _last_touch_dates(root: Path, paths: Iterable[str]) -> Mapping[str, date]:
    selected = tuple(sorted(set(paths)))
    if not selected:
        return {}
    command = [
        "git",
        "-c",
        "core.quotepath=false",
        "log",
        "--format=@@%cs",
        "--name-only",
        "--no-renames",
        "--",
        *selected,
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {}
    result: dict[str, date] = {}
    current_date: date | None = None
    selected_set = set(selected)
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("@@"):
            current_date = parse_audit_date(line[2:])
            continue
        if current_date is not None and line in selected_set and line not in result:
            result[line] = current_date
    return result


def _read_json_object(path: Path) -> Mapping[str, Any]:
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaintenanceAuditError(f"cannot read maintenance source {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise MaintenanceAuditError(f"maintenance source is not an object: {path}")
    return payload
