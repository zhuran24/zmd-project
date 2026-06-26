#!/usr/bin/env python
"""zmem MVP-0 CLI.

Truth source: cards/*.md.
Caches: .index/*.json, fully rebuildable.
No LLM, no behavior log, no PreToolUse/PostToolUse path.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - local host has PyYAML.
    yaml = None


ROOT = Path(__file__).resolve().parent
DEFAULT_CARDS_DIR = ROOT / "cards"
DEFAULT_INDEX_PATH = ROOT / ".index" / "cards_index.json"
DEFAULT_EVAL_PATH = ROOT / "eval" / "regression.jsonl"

SCHEMA_VERSION = "zmem-card-v1-mvp0"
PACKET_VERSION = "zmem-packet-v1-mvp0"

KINDS = {
    "constraint",
    "decision",
    "status",
    "pitfall",
    "open_obligation",
    "file_local",
    "reference",
}
PRIORITIES = {"P0", "P1", "P2", "P3"}
ACTIVE_STATUS = "active"
ALLOWED_STATUS = {"active", "superseded", "archived"}
PENDING_STATUS = {"pending", "pending_nonactive"}

WEIGHTS = {
    "trigger_hit": 0.35,
    "bm25": 0.20,
    "dense_cosine": 0.20,
    "scope_match": 0.15,
    "freshness": 0.05,
    "type_priority": 0.05,
}

# MASTER_PLAN names only decision/pitfall/local explicitly. Reference is kept
# quota-bound for MVP-0 because meta-index cards are first-class recall material.
L1_QUOTA = {
    "decision": 3,
    "pitfall": 3,
    "file_local": 2,
    "reference": 3,
}

TYPE_PRIORITY = {
    "P0": 1.0,
    "P1": 0.8,
    "P2": 0.5,
    "P3": 0.2,
}

TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/-]*|[\u4e00-\u9fff]+")


class ZmemError(Exception):
    pass


@dataclass(frozen=True)
class Card:
    path: str
    meta: dict[str, Any]
    body: str
    digest: str

    @property
    def id(self) -> str:
        return str(self.meta.get("id", ""))

    @property
    def kind(self) -> str:
        return str(self.meta.get("kind", ""))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", ""))

    @property
    def priority(self) -> str:
        return str(self.meta.get("priority", "P3"))

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.id))


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lower()


def text_blob(parts: list[Any]) -> str:
    out: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, list):
            out.extend(str(x) for x in part)
        elif isinstance(part, dict):
            out.append(stable_json(part))
        else:
            out.append(str(part))
    return "\n".join(out).lower()


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def load_frontmatter(path: Path) -> Card:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ZmemError(f"{path}: missing YAML frontmatter")
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        raise ZmemError(f"{path}: unterminated YAML frontmatter")
    frontmatter = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :]).strip()
    if yaml is None:
        raise ZmemError("PyYAML is required for YAML card frontmatter")
    meta = yaml.safe_load(frontmatter) or {}
    if not isinstance(meta, dict):
        raise ZmemError(f"{path}: frontmatter must be a mapping")
    return Card(
        path=str(path),
        meta=meta,
        body=body,
        digest=sha256_text(raw),
    )


def load_cards(cards_dir: Path) -> list[Card]:
    if not cards_dir.exists():
        raise ZmemError(f"cards dir does not exist: {cards_dir}")
    cards = [load_frontmatter(path) for path in sorted(cards_dir.glob("*.md"))]
    return cards


def evidence_values(card: Card) -> list[str]:
    provenance = as_dict(card.meta.get("provenance"))
    evidence = provenance.get("evidence")
    if isinstance(evidence, list):
        return [str(item).strip() for item in evidence if str(item).strip()]
    if evidence is None:
        return []
    text = str(evidence).strip()
    return [text] if text else []


def nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_relation_to(card: Card, other_id: str) -> bool:
    provenance = as_dict(card.meta.get("provenance"))
    relations = as_dict(card.meta.get("relations"))
    for source in (provenance, relations):
        for key in ("supersedes", "contradicts"):
            if other_id in normalize_list(source.get(key)):
                return True
    return False


def scope_key(card: Card) -> str:
    scope = as_dict(card.meta.get("scope"))
    key = {
        "domains": sorted(normalize_list(scope.get("domains"))),
        "paths": sorted(normalize_list(scope.get("paths"))),
        "symbols": sorted(normalize_list(scope.get("symbols"))),
    }
    return stable_json(key)


def validate_card_shape(card: Card) -> list[str]:
    errors: list[str] = []
    meta = card.meta
    for field in ("id", "kind", "title", "scope", "status", "priority", "triggers", "activation"):
        if field not in meta:
            errors.append(f"{card.path}: missing required field {field}")

    card_id = str(meta.get("id", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", card_id):
        errors.append(f"{card.path}: id must be lowercase slug")

    if meta.get("kind") not in KINDS:
        errors.append(f"{card.path}: kind must be one of {sorted(KINDS)}")

    status = str(meta.get("status", ""))
    if status in PENDING_STATUS or status.startswith("pending"):
        errors.append(f"{card.path}: pending cards must not live under cards/")
    elif status not in ALLOWED_STATUS:
        errors.append(f"{card.path}: status must be one of {sorted(ALLOWED_STATUS)}")

    if meta.get("priority") not in PRIORITIES:
        errors.append(f"{card.path}: priority must be one of {sorted(PRIORITIES)}")

    scope = as_dict(meta.get("scope"))
    if not scope:
        errors.append(f"{card.path}: scope must be a mapping")
    domains = normalize_list(scope.get("domains"))
    if not domains:
        errors.append(f"{card.path}: scope.domains must contain at least one domain")
    for field in ("paths", "symbols"):
        if field not in scope:
            errors.append(f"{card.path}: scope.{field} must be present, even when empty")
        elif not isinstance(scope.get(field), list):
            errors.append(f"{card.path}: scope.{field} must be a list")

    triggers = as_dict(meta.get("triggers"))
    if not triggers:
        errors.append(f"{card.path}: triggers must be a mapping")
    examples = normalize_list(triggers.get("examples"))
    if len(examples) < 1:
        errors.append(f"{card.path}: triggers.examples must contain at least one example")
    for field in (
        "intents",
        "keywords",
        "negative_keywords",
        "paths",
        "symbols",
        "error_regex",
        "examples",
    ):
        if field not in triggers:
            errors.append(f"{card.path}: triggers.{field} must be present")
        elif not isinstance(triggers.get(field), list):
            errors.append(f"{card.path}: triggers.{field} must be a list")

    if not isinstance(meta.get("activation"), dict):
        errors.append(f"{card.path}: activation must be a mapping")

    priority = str(meta.get("priority", ""))
    if priority in {"P0", "P1"} and not evidence_values(card):
        errors.append(f"{card.path}: high-priority cards require non-empty provenance.evidence")

    kind = str(meta.get("kind", ""))
    if kind == "constraint":
        if not nonempty_str(meta.get("severity")):
            errors.append(f"{card.path}: constraint cards require severity")
        if not (normalize_list(scope.get("paths")) or normalize_list(scope.get("symbols"))):
            errors.append(f"{card.path}: constraint cards require at least one scope path or symbol")
    elif kind == "status":
        validity = as_dict(meta.get("validity"))
        if not validity:
            errors.append(f"{card.path}: status cards require validity")
    elif kind == "pitfall":
        if "error_regex" not in meta or not normalize_list(meta.get("error_regex")):
            errors.append(f"{card.path}: pitfall cards require top-level error_regex")
    elif kind == "open_obligation":
        validity = as_dict(meta.get("validity"))
        if not validity.get("until") or not validity.get("invalidated_by"):
            errors.append(f"{card.path}: open_obligation cards require validity.until and validity.invalidated_by")
    elif kind == "decision":
        provenance = as_dict(meta.get("provenance"))
        if not provenance:
            errors.append(f"{card.path}: decision cards require provenance")

    provenance = as_dict(meta.get("provenance"))
    op = str(provenance.get("op", "record"))
    if op in {"supersede", "contradict", "merge"}:
        targets = normalize_list(provenance.get("supersedes")) + normalize_list(provenance.get("contradicts"))
        if not targets:
            errors.append(f"{card.path}: provenance.op={op} requires supersedes or contradicts")
        if not nonempty_str(provenance.get("reason")):
            errors.append(f"{card.path}: provenance.op={op} requires reason")
        if not evidence_values(card):
            errors.append(f"{card.path}: provenance.op={op} requires evidence")

    return errors


def verify_cards(cards: list[Card]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    active_status_by_domain: dict[str, str] = {}
    active_scope: dict[str, list[Card]] = defaultdict(list)

    for card in cards:
        errors.extend(validate_card_shape(card))
        if card.id in seen_ids:
            errors.append(f"{card.path}: duplicate id {card.id} also in {seen_ids[card.id]}")
        else:
            seen_ids[card.id] = card.path

        scope = as_dict(card.meta.get("scope"))
        if card.kind == "status" and card.status == ACTIVE_STATUS:
            for domain in normalize_list(scope.get("domains")):
                previous = active_status_by_domain.get(domain)
                if previous:
                    errors.append(
                        f"{card.path}: active status domain {domain!r} already owned by {previous}"
                    )
                else:
                    active_status_by_domain[domain] = card.id

        if card.status == ACTIVE_STATUS:
            active_scope[scope_key(card)].append(card)

    for cards_with_scope in active_scope.values():
        if len(cards_with_scope) < 2:
            continue
        for i, left in enumerate(cards_with_scope):
            for right in cards_with_scope[i + 1 :]:
                if has_relation_to(left, right.id) or has_relation_to(right, left.id):
                    continue
                errors.append(
                    f"{left.path}: active same-scope conflict with {right.id}; declare supersedes/contradicts"
                )
                errors.append(
                    f"{right.path}: active same-scope conflict with {left.id}; declare supersedes/contradicts"
                )

    return errors


def card_search_text(card: Card) -> str:
    triggers = as_dict(card.meta.get("triggers"))
    scope = as_dict(card.meta.get("scope"))
    provenance = as_dict(card.meta.get("provenance"))
    # Evidence is audit material, not activation text. Including command-shaped
    # evidence such as "python cc_memory/mem.py read ..." makes unrelated cards
    # match operational prompts.
    return text_blob(
        [
            card.id,
            card.title,
            card.meta.get("summary"),
            card.kind,
            scope.get("domains"),
            scope.get("paths"),
            scope.get("symbols"),
            triggers.get("intents"),
            triggers.get("keywords"),
            triggers.get("paths"),
            triggers.get("symbols"),
            triggers.get("examples"),
            provenance.get("reason"),
            card.body,
        ]
    )


def build_index_data(cards: list[Card]) -> dict[str, Any]:
    errors = verify_cards(cards)
    if errors:
        raise ZmemError("verify failed before build-index:\n" + "\n".join(errors))
    active_cards = [card for card in cards if card.status == ACTIVE_STATUS]
    index_cards = []
    for card in sorted(active_cards, key=lambda c: c.id):
        search_text = card_search_text(card)
        index_cards.append(
            {
                "id": card.id,
                "path": card.path,
                "digest": card.digest,
                "meta": card.meta,
                "body": card.body,
                "terms": sorted(set(tokens(search_text))),
                "search_text": search_text,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "packet_version": PACKET_VERSION,
        "cards_dir": str(DEFAULT_CARDS_DIR),
        "cards": index_cards,
    }


def write_index(index: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ZmemError(f"index missing: {path}; run `zmem.py build-index` first")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ZmemError(f"index schema mismatch in {path}")
    return data


def frame_from_args(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.frame_json or args.frame
    if raw:
        maybe_path = Path(raw)
        if args.frame_json:
            data = json.loads(raw)
        elif maybe_path.exists():
            data = json.loads(maybe_path.read_text(encoding="utf-8"))
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"prompt": raw}
    elif args.prompt:
        data = {"prompt": args.prompt}
    else:
        data = {}
    if not isinstance(data, dict):
        raise ZmemError("task frame must be a JSON object")
    return normalize_frame(data)


def normalize_frame(frame: dict[str, Any]) -> dict[str, Any]:
    prompt = str(frame.get("prompt") or frame.get("user_prompt") or frame.get("text") or "")
    normalized = dict(frame)
    normalized["prompt"] = prompt
    for key in ("intents", "keywords", "paths", "symbols", "domains", "claims"):
        normalized[key] = normalize_list(frame.get(key))
    normalized["phase"] = str(frame.get("phase", ""))
    normalized["now"] = str(frame.get("now", ""))
    return normalized


def frame_haystack(frame: dict[str, Any]) -> str:
    return text_blob(
        [
            frame.get("prompt"),
            frame.get("intents"),
            frame.get("keywords"),
            frame.get("domains"),
            frame.get("claims"),
            frame.get("phase"),
        ]
    )


def any_keyword_hit(keywords: list[str], haystack: str) -> bool:
    return any(keyword.lower() in haystack for keyword in keywords if keyword)


def path_glob_hit(patterns: list[str], paths: list[str]) -> bool:
    normalized_paths = [normalize_path(path) for path in paths]
    for pattern in patterns:
        pat = normalize_path(pattern)
        for path in normalized_paths:
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, f"*/{pat}"):
                return True
    return False


def overlap(left: list[str], right: list[str]) -> bool:
    return bool({item.lower() for item in left} & {item.lower() for item in right})


def card_negative_blocked(card_data: dict[str, Any], frame: dict[str, Any]) -> bool:
    triggers = as_dict(card_data["meta"].get("triggers"))
    return any_keyword_hit(normalize_list(triggers.get("negative_keywords")), frame_haystack(frame))


def trigger_group_scores(card_data: dict[str, Any], frame: dict[str, Any]) -> dict[str, float]:
    meta = card_data["meta"]
    triggers = as_dict(meta.get("triggers"))
    haystack = frame_haystack(frame)
    frame_terms = set(tokens(haystack))
    example_terms = set(tokens(" ".join(normalize_list(triggers.get("examples")))))

    scores = {
        "intent": 1.0 if overlap(normalize_list(triggers.get("intents")), normalize_list(frame.get("intents"))) else 0.0,
        "keyword": 1.0 if any_keyword_hit(normalize_list(triggers.get("keywords")), haystack) else 0.0,
        "path": 1.0 if path_glob_hit(normalize_list(triggers.get("paths")), normalize_list(frame.get("paths"))) else 0.0,
        "symbol": 1.0 if overlap(normalize_list(triggers.get("symbols")), normalize_list(frame.get("symbols"))) else 0.0,
        "example": 1.0 if frame_terms and example_terms and bool(frame_terms & example_terms) else 0.0,
    }
    return scores


def trigger_hit(card_data: dict[str, Any], frame: dict[str, Any]) -> float:
    triggers = as_dict(card_data["meta"].get("triggers"))
    group_values = [
        normalize_list(triggers.get("intents")),
        normalize_list(triggers.get("keywords")),
        normalize_list(triggers.get("paths")),
        normalize_list(triggers.get("symbols")),
        normalize_list(triggers.get("examples")),
    ]
    active_groups = sum(1 for values in group_values if values)
    if active_groups == 0:
        return 0.0
    return sum(trigger_group_scores(card_data, frame).values()) / active_groups


def bm25_like(card_data: dict[str, Any], frame: dict[str, Any]) -> float:
    query_terms = set(tokens(frame_haystack(frame)))
    if not query_terms:
        return 0.0
    card_terms = set(card_data.get("terms") or tokens(card_data.get("search_text", "")))
    direct = len(query_terms & card_terms) / max(len(query_terms), 1)
    haystack = card_data.get("search_text", "")
    substring_hits = sum(1 for term in query_terms if term and term in haystack)
    substring = substring_hits / max(len(query_terms), 1)
    return min(1.0, max(direct, substring))


def scope_match(card_data: dict[str, Any], frame: dict[str, Any]) -> float:
    scope = as_dict(card_data["meta"].get("scope"))
    parts = [
        1.0 if overlap(normalize_list(scope.get("domains")), normalize_list(frame.get("domains"))) else 0.0,
        1.0 if path_glob_hit(normalize_list(scope.get("paths")), normalize_list(frame.get("paths"))) else 0.0,
        1.0 if overlap(normalize_list(scope.get("symbols")), normalize_list(frame.get("symbols"))) else 0.0,
    ]
    return max(parts)


def freshness(card_data: dict[str, Any], frame: dict[str, Any]) -> float:
    # Deterministic by default: no wall-clock dependency unless frame.now is supplied.
    updated = str(card_data["meta"].get("updated_at", ""))
    now = str(frame.get("now") or "")
    if not updated or not now:
        return 0.5
    try:
        y1, m1, d1 = [int(x) for x in updated[:10].split("-")]
        y2, m2, d2 = [int(x) for x in now[:10].split("-")]
    except Exception:
        return 0.5
    days = abs((y2 * 372 + m2 * 31 + d2) - (y1 * 372 + m1 * 31 + d1))
    if days <= 30:
        return 1.0
    if days <= 180:
        return 0.7
    if days <= 365:
        return 0.4
    return 0.2


def force_reason(card_data: dict[str, Any], frame: dict[str, Any]) -> str | None:
    meta = card_data["meta"]
    if meta.get("status") != ACTIVE_STATUS:
        return None
    kind = meta.get("kind")
    triggers = as_dict(meta.get("triggers"))
    activation = as_dict(meta.get("activation"))
    scope = as_dict(meta.get("scope"))
    haystack = frame_haystack(frame)

    if activation.get("session_start_l0") is True and "session-start" in normalize_list(frame.get("intents")):
        return "session_start_l0"

    if kind == "constraint":
        if path_glob_hit(normalize_list(scope.get("paths")) + normalize_list(triggers.get("paths")), normalize_list(frame.get("paths"))):
            return "must_know_constraint_path"
        if overlap(normalize_list(scope.get("symbols")) + normalize_list(triggers.get("symbols")), normalize_list(frame.get("symbols"))):
            return "must_know_constraint_symbol"
        if any_keyword_hit(normalize_list(activation.get("claim_guards")), haystack):
            return "must_know_constraint_claim_guard"

    if kind == "status":
        if meta.get("status") == "superseded":
            return None
        phase_terms = normalize_list(activation.get("phase")) + normalize_list(triggers.get("keywords"))
        claim_terms = normalize_list(activation.get("claims")) + normalize_list(activation.get("claim_guards"))
        if any_keyword_hit(phase_terms + claim_terms, haystack):
            return "must_know_active_status"

    if kind == "open_obligation":
        if activation.get("always_on") is True:
            return "must_know_open_obligation_always_on"
        arming_terms = normalize_list(activation.get("arming")) + normalize_list(triggers.get("keywords"))
        if any_keyword_hit(arming_terms, haystack):
            return "must_know_open_obligation_armed"

    return None


def score_card(card_data: dict[str, Any], frame: dict[str, Any], dense_enabled: bool = False) -> dict[str, Any]:
    dense = 0.0
    features = {
        "trigger_hit": trigger_hit(card_data, frame),
        "bm25": bm25_like(card_data, frame),
        "dense_cosine": dense if dense_enabled else 0.0,
        "scope_match": scope_match(card_data, frame),
        "freshness": freshness(card_data, frame),
        "type_priority": TYPE_PRIORITY.get(str(card_data["meta"].get("priority")), 0.0),
    }
    score = sum(WEIGHTS[key] * features[key] for key in WEIGHTS)
    return {"score": round(score, 6), "features": features}


def card_packet_entry(card_data: dict[str, Any], layer: str, score_data: dict[str, Any], reason: str) -> dict[str, Any]:
    meta = card_data["meta"]
    body = str(card_data.get("body", ""))
    snippet = body.splitlines()[0] if body else ""
    return {
        "id": meta.get("id"),
        "kind": meta.get("kind"),
        "title": meta.get("title"),
        "priority": meta.get("priority"),
        "layer": layer,
        "score": score_data.get("score", 1.0),
        "reason": reason,
        "features": score_data.get("features", {}),
        "scope": meta.get("scope", {}),
        "snippet": snippet[:500],
    }


def compile_context(index: dict[str, Any], frame: dict[str, Any], dense_enabled: bool = False) -> dict[str, Any]:
    l0: list[dict[str, Any]] = []
    candidates_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    l2: list[dict[str, Any]] = []
    forced_ids: set[str] = set()
    blocked: list[str] = []

    for card_data in index.get("cards", []):
        if card_negative_blocked(card_data, frame):
            blocked.append(str(card_data["meta"].get("id")))
            continue
        reason = force_reason(card_data, frame)
        if reason:
            entry = card_packet_entry(card_data, "L0", {"score": 1.0, "features": {}}, reason)
            l0.append(entry)
            forced_ids.add(str(card_data["meta"].get("id")))
            continue
        score_data = score_card(card_data, frame, dense_enabled=dense_enabled)
        features = score_data["features"]
        recall_signal = (
            features["trigger_hit"] > 0
            or features["bm25"] > 0
            or features["scope_match"] > 0
            or features["dense_cosine"] > 0
        )
        if not recall_signal:
            continue
        if score_data["score"] <= 0:
            continue
        item = card_packet_entry(card_data, "candidate", score_data, "scored")
        candidates_by_kind[str(card_data["meta"].get("kind"))].append(item)

    l1: list[dict[str, Any]] = []
    for kind in sorted(candidates_by_kind):
        items = sorted(
            candidates_by_kind[kind],
            key=lambda item: (-float(item["score"]), str(item["id"])),
        )
        quota = L1_QUOTA.get(kind, 0)
        promoted = 0
        for item in items:
            features = item.get("features", {})
            # Only a real trigger or scope signal earns the user-visible L1 slot.
            # A bm25-only substring brush is too weak to surface a card here and
            # would flood L1 with topically-adjacent noise; demote it to an L2
            # pointer instead. (No gold-standard expected card is bm25-only.)
            strong_signal = (
                float(features.get("trigger_hit", 0.0)) > 0.0
                or float(features.get("scope_match", 0.0)) > 0.0
            )
            if strong_signal and promoted < quota:
                item["layer"] = "L1"
                item["reason"] = f"quota:{kind}"
                l1.append(item)
                promoted += 1
            else:
                item["layer"] = "L2"
                item["reason"] = "weak:bm25-only" if not strong_signal else f"overflow:{kind}"
                l2.append(item)

    l0 = sorted(l0, key=lambda item: str(item["id"]))
    l1 = sorted(l1, key=lambda item: (str(item["kind"]), -float(item["score"]), str(item["id"])))
    l2 = sorted(l2, key=lambda item: (-float(item["score"]), str(item["id"])))
    frame_digest = sha256_text(stable_json(frame))
    return {
        "packet_version": PACKET_VERSION,
        "frame_digest": frame_digest,
        "layers": {
            "L0": l0,
            "L1": l1,
            "L2": l2,
        },
        "diagnostics": {
            "dense_enabled": bool(dense_enabled),
            "dense_note": "disabled in MVP-0 synchronous path",
            "weights": WEIGHTS,
            "l1_quota": L1_QUOTA,
            "forced_count": len(forced_ids),
            "blocked_by_negative_keywords": blocked,
        },
    }


def filter_layers(packet: dict[str, Any], requested: list[str]) -> dict[str, Any]:
    wanted = {layer.strip() for layer in requested if layer.strip()}
    if not wanted:
        return packet
    packet = json.loads(stable_json(packet))
    for layer in list(packet["layers"]):
        if layer not in wanted:
            packet["layers"][layer] = []
    return packet


def format_packet_text(packet: dict[str, Any]) -> str:
    lines = ["# zmem context packet", f"version: {packet['packet_version']}", f"frame_digest: {packet['frame_digest']}"]
    for layer in ("L0", "L1", "L2"):
        items = packet["layers"].get(layer, [])
        lines.append("")
        lines.append(f"## {layer}")
        if not items:
            lines.append("(none)")
            continue
        for item in items:
            lines.append(
                f"- {item['id']} [{item['kind']}/{item['priority']}] score={item['score']} reason={item['reason']}"
            )
            if item.get("snippet"):
                lines.append(f"  {item['snippet']}")
    return "\n".join(lines)


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        cards = load_cards(Path(args.cards_dir))
        errors = verify_cards(cards)
    except ZmemError as exc:
        print(f"VERIFY FAIL: {exc}", file=sys.stderr)
        return 1
    if errors:
        print(f"VERIFY FAIL: {len(errors)} error(s)")
        for error in errors:
            print(error)
        return 1
    print(f"VERIFY OK: {len(cards)} card(s)")
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    try:
        cards = load_cards(Path(args.cards_dir))
        index = build_index_data(cards)
        write_index(index, Path(args.index))
    except ZmemError as exc:
        print(f"BUILD-INDEX FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"INDEX OK: {len(index['cards'])} active card(s) -> {args.index}")
    return 0


def load_context_index(args: argparse.Namespace) -> dict[str, Any]:
    index_path = Path(args.index)
    if index_path.exists():
        return load_index(index_path)
    if args.require_index:
        raise ZmemError(f"index missing: {index_path}; run build-index first")
    cards = load_cards(Path(args.cards_dir))
    return build_index_data(cards)


def cmd_context(args: argparse.Namespace) -> int:
    try:
        frame = frame_from_args(args)
        index = load_context_index(args)
        packet = compile_context(index, frame, dense_enabled=args.enable_dense)
        packet = filter_layers(packet, args.layers.split(","))
    except (ZmemError, json.JSONDecodeError) as exc:
        print(f"CONTEXT FAIL: {exc}", file=sys.stderr)
        return 1

    if args.format == "text":
        print(format_packet_text(packet))
    else:
        print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def selected_ids(packet: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for layer in ("L0", "L1"):
        ids.update(str(item["id"]) for item in packet["layers"].get(layer, []))
    return ids


def cmd_eval(args: argparse.Namespace) -> int:
    try:
        index = load_context_index(args)
    except ZmemError as exc:
        print(f"EVAL FAIL: {exc}", file=sys.stderr)
        return 1

    eval_path = Path(args.eval_file)
    if not eval_path.exists():
        print(f"EVAL FAIL: missing eval file {eval_path}", file=sys.stderr)
        return 1

    total = 0
    passed = 0
    failures: list[str] = []
    for line_no, line in enumerate(eval_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        total += 1
        try:
            case = json.loads(stripped)
            frame = normalize_frame(as_dict(case.get("frame")))
            expected = set(normalize_list(case.get("expected_cards")))
            forbidden = set(normalize_list(case.get("forbidden_cards")))
            packet = compile_context(index, frame, dense_enabled=False)
            got = selected_ids(packet)
        except Exception as exc:
            failures.append(f"line {line_no}: malformed case: {exc}")
            continue
        missing = sorted(expected - got)
        forbidden_hit = sorted(forbidden & got)
        case_id = case.get("id", f"line-{line_no}")
        if not missing and not forbidden_hit:
            passed += 1
            print(f"{case_id}: PASS expected={sorted(expected)} selected={sorted(got)}")
        else:
            failures.append(
                f"{case_id}: FAIL missing={missing} forbidden_hit={forbidden_hit} selected={sorted(got)}"
            )

    for failure in failures:
        print(failure)
    if failures:
        print(f"EVAL FAIL: {passed}/{total} case(s) passed")
        return 1
    print(f"EVAL OK: {passed}/{total} case(s) passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zmem", description="zmem MVP-0 card compiler")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="validate card schema and reconciliation gates")
    verify.add_argument("--cards-dir", default=str(DEFAULT_CARDS_DIR))
    verify.set_defaults(func=cmd_verify)

    build = sub.add_parser("build-index", help="compile cards into a deterministic offline index")
    build.add_argument("--cards-dir", default=str(DEFAULT_CARDS_DIR))
    build.add_argument("--index", default=str(DEFAULT_INDEX_PATH))
    build.set_defaults(func=cmd_build_index)

    context = sub.add_parser("context", help="compile a task frame into an L0/L1/L2 packet")
    context.add_argument("--cards-dir", default=str(DEFAULT_CARDS_DIR))
    context.add_argument("--index", default=str(DEFAULT_INDEX_PATH))
    context.add_argument("--frame", help="task frame JSON path, inline JSON, or raw prompt")
    context.add_argument("--frame-json", help="inline task frame JSON")
    context.add_argument("--prompt", help="raw prompt convenience input")
    context.add_argument("--layers", default="L0,L1,L2", help="comma-separated layers to emit")
    context.add_argument("--format", choices=("json", "text"), default="json")
    context.add_argument("--enable-dense", action="store_true", help="reserved; disabled by default in MVP-0")
    context.add_argument("--require-index", action="store_true")
    context.set_defaults(func=cmd_context)

    eval_cmd = sub.add_parser("eval", help="run activation regression frames")
    eval_cmd.add_argument("--cards-dir", default=str(DEFAULT_CARDS_DIR))
    eval_cmd.add_argument("--index", default=str(DEFAULT_INDEX_PATH))
    eval_cmd.add_argument("--eval-file", default=str(DEFAULT_EVAL_PATH))
    eval_cmd.add_argument("--require-index", action="store_true")
    eval_cmd.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
