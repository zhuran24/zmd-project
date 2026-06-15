"""记忆树 repo<->harness 对账 + harvest (memtree 重构 P0/P2, 2026-06-15)。

定位 (GPT-5.5 Pro 外审 + team 收敛的四层模型):
- live harness (~/.claude/projects/<slug>/memory) = 运行时工作副本 + 写入入口;
  Claude Code auto-memory 真正召回读的树。
- repo cc_context/memory = curated 整理层 (发布 / 索引 / 长期整理面)。
- _cc_live_memory = curated 的逐字节镜像 (远程可见)。
- 本工具是「不撒谎的账本」的第一块: 按 frontmatter `name` 对账两棵树,
  抓**同名节点内容/描述漂移** —— 这是最骗人的失败 (节点名在、内容 stale,
  现有 sync --check 只查 snake 投影类、查不到 kebab 共维护节点的 drift)。

铁律 (harvest-only): 本工具**只读 harness, 永不写 active harness**。
  没有 --restore-inactive-harness 这种显式重武器, 任何路径都不碰 harness。

模式:
- --check (默认, P0 冻结+观测): 只对账, 不写任何文件。产出 manifest 字符串 + 漂移报告到 stdout。
- --write-manifest: 额外把 manifest JSON 落到 cc_context/knowledge/。仍只读 harness。

回归样本 (GPT 外审钦点): `zmd-round2-dispatch-fix-state` 当前 repo 比 harness 新 (另一会话把
Round5 RESET 提进 repo, harness 节点没跟上)。--check 必须把它列进 same-name drift。

用法:
    python cc_context/tools/memory_harvest.py --check
    python cc_context/tools/memory_harvest.py --check --harness-dir <path>
    python cc_context/tools/memory_harvest.py --check --write-manifest

注: 基于 jsonl-cwd 证据的 active-harness resolver 是后续阶段 (GPT rule 2);
本阶段 --harness-dir 默认指向当前已确认活跃的 slug, 可显式覆盖。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_MEM = ROOT / "cc_context" / "memory"
# 当前已确认活跃 slug (2026-06-15 实测最近活动); resolver 见后续阶段。
DEFAULT_HARNESS = (
    Path.home() / ".claude" / "projects" / "C--claude-pj-zmd-pj" / "memory"
)
MANIFEST_OUT = ROOT / "cc_context" / "knowledge" / "memory_harvest_manifest.json"
REGRESSION_SAMPLE = "zmd-round2-dispatch-fix-state"
# handoff 现状源在 harness 故意留 stub (sync 跳过 handoff_), 与 repo 全文必然不同 =
# 有意漂移, 非问题。不进「真漂移」清单, 单列以免账本喊狼。
KNOWN_INTENTIONAL_STUB = {"windows-ninth-review-pending"}

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def parse_node(path: Path) -> dict | None:
    """从一个 .md 取 name / description / body_sha / desc_sha。无 name 则返回 None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm_match = _FM_RE.match(text)
    front = fm_match.group(1) if fm_match else text
    body = text[fm_match.end():] if fm_match else ""
    name_match = _NAME_RE.search(front)
    if not name_match:
        return None
    desc_match = _DESC_RE.search(front)
    description = (desc_match.group(1).strip().strip('"').strip() if desc_match else "")
    return {
        "name": name_match.group(1).strip(),
        "file": path.name,
        "desc_sha": _sha(description),
        "body_sha": _sha(body),
        "mtime": path.stat().st_mtime,
    }


def scan_tree(mem_dir: Path) -> dict[str, dict]:
    """目录里全部 .md (除 MEMORY.md) -> {name: node}。同名后出现的覆盖前者并告警。"""
    nodes: dict[str, dict] = {}
    for md in sorted(mem_dir.glob("*.md")):
        if md.name == "MEMORY.md":
            continue
        node = parse_node(md)
        if node:
            nodes[node["name"]] = node
    return nodes


def memory_md_bytes(mem_dir: Path) -> int:
    mem = mem_dir / "MEMORY.md"
    return mem.stat().st_size if mem.exists() else 0


def build_manifest(repo_dir: Path, harness_dir: Path) -> dict:
    repo = scan_tree(repo_dir)
    harn = scan_tree(harness_dir)
    repo_names, harn_names = set(repo), set(harn)
    common = repo_names & harn_names

    drift = []
    for name in sorted(common):
        r, h = repo[name], harn[name]
        body_diff = r["body_sha"] != h["body_sha"]
        desc_diff = r["desc_sha"] != h["desc_sha"]
        if body_diff or desc_diff:
            newer = "repo" if r["mtime"] >= h["mtime"] else "harness"
            drift.append({
                "name": name,
                "body_diff": body_diff,
                "desc_diff": desc_diff,
                "newer_side": newer,
            })

    real_drift = [d for d in drift if d["name"] not in KNOWN_INTENTIONAL_STUB]
    stub_drift = [d for d in drift if d["name"] in KNOWN_INTENTIONAL_STUB]

    return {
        "repo_dir": str(repo_dir),
        "harness_dir": str(harness_dir),
        "harness_present": harness_dir.is_dir(),
        "repo_node_count": len(repo),
        "harness_node_count": len(harn),
        "repo_memory_md_bytes": memory_md_bytes(repo_dir),
        "harness_memory_md_bytes": memory_md_bytes(harness_dir),
        "repo_only": sorted(repo_names - harn_names),
        "harness_only": sorted(harn_names - repo_names),
        "common_count": len(common),
        "same_name_drift": real_drift,
        "intentional_stub_drift": stub_drift,
    }


HARVEST_DIR = ROOT / "cc_context" / "harness_memory_harvest"
_SECRET_PATTERNS = [re.compile(p) for p in (
    r"sk-[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[bap]-[A-Za-z0-9-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)]


def scan_secret(text: str) -> str | None:
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


def name_to_path(mem_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for md in sorted(mem_dir.glob("*.md")):
        if md.name == "MEMORY.md":
            continue
        node = parse_node(md)
        if node:
            out[node["name"]] = md
    return out


def do_harvest(harness_dir: Path, m: dict) -> dict:
    """从 live harness **只读**收割进 repo ledger: harness-only -> new/,
    同名真漂移 -> updates/ (落 harness 侧 stale 内容存证), secret 命中 -> quarantine/。
    永不写 harness。LF 行尾 (避 repo 行尾政策 gate)。"""
    paths = name_to_path(harness_dir)
    written: dict[str, list] = {"new": [], "updates": [], "quarantine": []}

    def emit(name: str, subdir: str) -> None:
        src = paths.get(name)
        if src is None or not src.exists():
            return
        text = src.read_text(encoding="utf-8")
        sec = scan_secret(text)
        target_sub = "quarantine" if sec else subdir
        out_dir = HARVEST_DIR / target_sub
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")
        if sec:
            written["quarantine"].append({"name": name, "pattern": sec, "from": subdir})
        else:
            written[subdir].append(name)

    for name in m["harness_only"]:
        emit(name, "new")
    for d in m["same_name_drift"]:
        emit(d["name"], "updates")

    HARVEST_DIR.mkdir(parents=True, exist_ok=True)
    (HARVEST_DIR / "harvest_manifest.json").write_text(
        json.dumps({"manifest": m, "written": written}, ensure_ascii=False, indent=2),
        encoding="utf-8", newline="\n",
    )
    return written


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="对账并打印报告 (默认行为)")
    ap.add_argument("--harness-dir", type=Path, default=DEFAULT_HARNESS)
    ap.add_argument("--repo-dir", type=Path, default=REPO_MEM)
    ap.add_argument(
        "--write-manifest", action="store_true",
        help="额外把 manifest JSON 落到 cc_context/knowledge/ (仍只读 harness)",
    )
    ap.add_argument(
        "--harvest", action="store_true",
        help="只读收割 live harness -> repo ledger (new/updates/quarantine); 永不写 harness",
    )
    args = ap.parse_args()

    if not args.repo_dir.is_dir():
        print(f"repo memory 目录不存在: {args.repo_dir}")
        return 1
    if not args.harness_dir.is_dir():
        print(f"harness 目录不存在: {args.harness_dir} (用 --harness-dir 指定; "
              "resolver 见后续阶段)")
        return 1

    m = build_manifest(args.repo_dir, args.harness_dir)
    print(f"repo  : {m['repo_node_count']} 节点, MEMORY.md {m['repo_memory_md_bytes']} B")
    print(f"harness: {m['harness_node_count']} 节点, MEMORY.md "
          f"{m['harness_memory_md_bytes']}/24576 B  ({m['harness_dir']})")
    print(f"common : {m['common_count']}; repo-only {len(m['repo_only'])}; "
          f"harness-only {len(m['harness_only'])}")
    def _flags(d: dict) -> str:
        return "+".join(f for f, k in (("body", "body_diff"), ("desc", "desc_diff")) if d[k])

    print(f"真·同名漂移 (需关注): {len(m['same_name_drift'])} 个")
    for d in m["same_name_drift"]:
        print(f"  DRIFT {d['name']}  [{_flags(d)}]  newer={d['newer_side']}")
    if m["intentional_stub_drift"]:
        print(f"有意 stub 漂移 (非问题, handoff 现状源): {len(m['intentional_stub_drift'])} 个")
        for d in m["intentional_stub_drift"]:
            print(f"  stub  {d['name']}  [{_flags(d)}]")

    all_drift = m["same_name_drift"] + m["intentional_stub_drift"]
    sample_caught = any(d["name"] == REGRESSION_SAMPLE for d in all_drift)
    print(f"\n回归样本 {REGRESSION_SAMPLE} 当前是否漂移: {sample_caught} "
          f"(False = 已被并发会话同步消除, 非工具漏抓)")

    if args.write_manifest:
        MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_OUT.write_text(
            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        print(f"manifest -> {MANIFEST_OUT}")

    if args.harvest:
        w = do_harvest(args.harness_dir, m)
        print(f"\nharvest -> {HARVEST_DIR}")
        print(f"  new (harness-only): {len(w['new'])}")
        print(f"  updates (同名漂移存证): {len(w['updates'])}  {w['updates']}")
        print(f"  quarantine (疑似 secret): {len(w['quarantine'])}  {w['quarantine']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
