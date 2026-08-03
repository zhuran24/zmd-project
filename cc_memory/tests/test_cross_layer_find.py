# -*- coding: utf-8 -*-
"""跨层 find 与 read/search 未命中提示(2026-08-03 普查 §3.4 第 3 项)。

不接 CI(preflight 快 lane 只跑 src/tests);手跑:
    python -m pytest -p no:randomly --basetemp=.pytest_tmp/find \
        cc_memory/tests/test_cross_layer_find.py -q

普查实测:三层记忆各有各的库,却没有"这个 id 在哪层"的入口——22 次
`unknown node` 死路 + 一次 40 分钟跨层迷路(ortools 卡)。本文件钉:
1. 三层各自能被命中、层名与路径都报出来;
2. 全不命中时 exit 1 且把查过哪几层说清;
3. read/search 未命中时提示 find;
4. find 全程零文件系统足迹:**WAL 模式**库(生产同构)查完 -wal / -shm 都不落地、
   主库字节不变,连目录本身 0555 只读都照样查得动;
5. 层隔离:第一层炸掉只降级成一行警告,其余两层照常汇总。

第 4/5 两条是 2026-08-03 审查打回来的:上一版 fixture 造的是 DELETE 模式最小库,
只比主库 sha256 又只看 -wal,把 `mode=ro` 会新建 -wal/-shm、在只读目录直接
"attempt to write a readonly database" 这件事整个漏过去了;三次 hits.extend 之间
也没有 try/except,首层一炸后两层的命中一起消失。

全部用 tmp fixture 造的库/目录,不碰真实 memory.db 与真实卡片目录。
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / "cc_memory" / "mem.py"


def _mem_module():
    spec = importlib.util.spec_from_file_location("mem_under_test_find", MEM)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


@pytest.fixture()
def layers(tmp_path):
    """A three-layer fixture: tiny sqlite db + vnext cards dir + file-memory dir.

    The db is deliberately in **WAL** mode, like the real `cc_memory/memory.db`
    (`connect()` sets `PRAGMA journal_mode = WAL`). Journal mode is the whole
    difference between "read-only" and "leaves no trace": a DELETE-mode fixture
    can never reproduce the `-wal`/`-shm` sidecars a `mode=ro` open creates.
    """
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "memory.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("CREATE TABLE entries (id TEXT PRIMARY KEY, title TEXT)")
    con.execute("CREATE TABLE facts (id TEXT PRIMARY KEY, value TEXT)")
    con.execute("CREATE TABLE aliases (alias TEXT PRIMARY KEY, target_type TEXT, target_id TEXT)")
    con.execute("INSERT INTO entries VALUES ('only-in-sqlite', 'sqlite 层独有')")
    con.execute("INSERT INTO facts VALUES ('fact-only-in-sqlite', 'v')")
    con.commit()
    con.close()

    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "only-in-vnext.md").write_text("---\nid: only-in-vnext\n---\n正文\n", encoding="utf-8")
    # 文件名与 frontmatter id 不一致的卡:必须靠 id 行也能找到
    (cards / "renamed-file.md").write_text("---\nid: id-not-in-filename\n---\n正文\n", encoding="utf-8")

    file_memory = tmp_path / "file_memory"
    file_memory.mkdir()
    (file_memory / "only-in-file-memory.md").write_text("# 文件记忆卡\n", encoding="utf-8")

    return {"db": db, "cards": cards, "file_memory": file_memory}


def _find(layers, needle, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(MEM),
            "--db",
            str(layers["db"]),
            "find",
            needle,
            "--cards-dir",
            str(layers["cards"]),
            "--file-memory-dir",
            str(layers["file_memory"]),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("needle", "layer", "locator_fragment"),
    [
        ("only-in-sqlite", "cc_memory", "entry:only-in-sqlite"),
        ("fact-only-in-sqlite", "cc_memory", "fact:fact-only-in-sqlite"),
        ("only-in-vnext", "cc_memory_vnext", "only-in-vnext.md"),
        ("id-not-in-filename", "cc_memory_vnext", "renamed-file.md"),
        ("only-in-file-memory", "file_memory", "only-in-file-memory.md"),
    ],
)
def test_find_reports_layer_and_path(layers, needle, layer, locator_fragment):
    result = _find(layers, needle)
    assert result.returncode == 0, result.stderr
    assert layer in result.stdout
    assert locator_fragment in result.stdout


def test_find_walks_every_layer_not_just_the_first(layers):
    # 同一个词命中两层时两层都要报出来,否则跨层迷路只挪了一格。
    (layers["file_memory"] / "only-in-vnext.md").write_text("# 同名文件记忆\n", encoding="utf-8")
    result = _find(layers, "only-in-vnext")
    assert result.returncode == 0, result.stderr
    assert "cc_memory_vnext" in result.stdout
    assert "file_memory" in result.stdout


def test_find_miss_names_the_layers_it_checked(layers):
    result = _find(layers, "nothing-anywhere")
    assert result.returncode == 1
    assert "no layer has" in result.stdout
    assert "cc_memory_vnext" in result.stdout
    assert str(layers["file_memory"]) in result.stdout


def test_find_tolerates_missing_layer_directories(layers, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(MEM),
            "--db",
            str(tmp_path / "no-such.db"),
            "find",
            "only-in-file-memory",
            "--cards-dir",
            str(tmp_path / "no-such-cards"),
            "--file-memory-dir",
            str(layers["file_memory"]),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "file_memory" in result.stdout


def test_find_never_writes_to_the_db(layers):
    db = layers["db"]
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert _find(layers, "only-in-sqlite").returncode == 0
    assert _find(layers, "nothing-anywhere").returncode == 1
    after = hashlib.sha256(db.read_bytes()).hexdigest()
    assert before == after
    # 零侧车:-wal 和 -shm 都不许被创建出来(`mode=ro` 在 WAL 库上两个都建)。
    leftovers = sorted(p.name for p in db.parent.iterdir() if p.name != db.name)
    assert leftovers == [], f"find 在 WAL 库旁留下了侧车文件: {leftovers}"


def test_find_works_when_the_db_directory_is_read_only(layers):
    """0555 目录:`mode=ro` 会直接 'attempt to write a readonly database'。"""
    db_dir = layers["db"].parent
    os.chmod(db_dir, 0o555)
    try:
        result = _find(layers, "only-in-sqlite")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "entry:only-in-sqlite" in result.stdout
        assert "查不了" not in result.stdout, "只读目录不该把 cc_memory 层整层降级掉"
    finally:
        os.chmod(db_dir, 0o755)
    assert sorted(p.name for p in db_dir.iterdir()) == ["memory.db"]


def test_find_reports_other_layers_when_the_sqlite_layer_explodes(layers):
    """首层炸掉 = 一行警告 + 其余两层照常汇总(走完三层是硬语义)。"""
    layers["db"].write_bytes(b"this is not a sqlite database at all")
    result = _find(layers, "only-in-vnext")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cc_memory 层查不了" in result.stdout
    assert "cc_memory_vnext" in result.stdout
    assert "only-in-vnext.md" in result.stdout


def test_find_still_exits_1_when_a_layer_explodes_and_nothing_matches(layers):
    layers["db"].write_bytes(b"this is not a sqlite database at all")
    result = _find(layers, "nothing-anywhere")
    assert result.returncode == 1
    assert "cc_memory 层查不了" in result.stdout
    assert "no layer has" in result.stdout


def test_read_and_search_misses_point_at_find():
    mod = _mem_module()
    try:
        assert "find" in mod.CROSS_LAYER_FIND_HINT
        source = MEM.read_text(encoding="utf-8")
        # 提示必须真的接在两个未命中分支上,而不只是定义了一个常量。
        assert source.count("print(CROSS_LAYER_FIND_HINT)") == 2
        assert "unknown node: {args.node}" in source
    finally:
        sys.modules.pop("mem_under_test_find", None)


def test_file_memory_dir_constant_points_at_the_real_layer():
    mod = _mem_module()
    try:
        assert mod.FILE_MEMORY_DIR.name == "memory"
        assert mod.FILE_MEMORY_DIR.parent.name == "-home-zhuran24-zmd-pj"
        assert mod.VNEXT_CARDS_DIR == ROOT / "cc_memory_vnext" / "cards"
    finally:
        sys.modules.pop("mem_under_test_find", None)
