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
5. 层隔离:第一层炸掉只降级成一行警告,其余两层照常汇总;
6. **零足迹是全路径不变量**:路径不存在时不许"顺手建一个 0 字节库",打不开也
   不许回退到会写侧车的裸 mode=ro;
7. **degraded miss ≠ 完整 miss**:任一层降级(整层炸了 / immutable 读跳过了
   live WAL)时,未命中要如实说"这不等于不存在",只有三层都跑完的未命中才配
   印那句"no layer has"。

第 4/5 两条是 2026-08-03 第一轮审查打回来的:上一版 fixture 造的是 DELETE 模式
最小库,只比主库 sha256 又只看 -wal,把 `mode=ro` 会新建 -wal/-shm、在只读目录直接
"attempt to write a readonly database" 这件事整个漏过去了;三次 hits.extend 之间
也没有 try/except,首层一炸后两层的命中一起消失。
第 6/7 两条是同日第二轮复验实测打回来的:`?immutable=1` 少了 `mode=ro`,对不存在
的路径会**创建** 0 字节文件并答 SELECT 1;回退分支又把侧车写了回来;而有 writer
持着未 checkpoint 的行时,find 对一条真实存在的 id 印了 "no layer has"。

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
    """三层都正常跑完的未命中 = 干净的完整 miss,不许挂降级字样。"""
    result = _find(layers, "nothing-anywhere")
    assert result.returncode == 1
    assert "no layer has" in result.stdout
    assert "cc_memory_vnext" in result.stdout
    assert str(layers["file_memory"]) in result.stdout
    assert "降级" not in result.stdout, "全层正常的未命中被误标成降级"


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
    """炸掉一层后的未命中 = degraded miss:退出码仍是 1,但文案不许说"三层都没有"。"""
    layers["db"].write_bytes(b"this is not a sqlite database at all")
    result = _find(layers, "nothing-anywhere")
    assert result.returncode == 1
    assert "cc_memory 层查不了" in result.stdout
    assert "降级" in result.stdout
    assert "未命中不等于不存在" in result.stdout
    assert "no layer has" not in result.stdout, "整层没查成还宣称三层查无=把 degraded miss 说成完整 miss"


# --- B1/B2 2026-08-03 审查:纯只读不是"少写一点",degraded miss 不是 miss ----


def _connect_immutable(db: Path):
    mod = _mem_module()
    try:
        return mod.connect_immutable(db)
    finally:
        sys.modules.pop("mem_under_test_find", None)


def test_immutable_open_never_creates_a_database_file(tmp_path):
    """不存在的路径:必须报错,不许"顺手建一个 0 字节库"再答 SELECT 1。"""
    missing = tmp_path / "no-such-dir"
    missing.mkdir()
    db = missing / "memory.db"
    assert not db.exists()
    with pytest.raises(sqlite3.Error):
        _connect_immutable(db)
    assert not db.exists(), "只读 opener 建出了一个数据库文件"
    assert sorted(p.name for p in missing.iterdir()) == []


def test_immutable_open_leaves_no_sidecars_on_a_wal_database(layers):
    db = layers["db"]
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    con = _connect_immutable(db)
    try:
        assert con.execute("SELECT id FROM entries").fetchall()
    finally:
        con.close()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in db.parent.iterdir()) == ["memory.db"]


def test_immutable_open_has_no_sidecar_creating_fallback(layers):
    """旧版在 immutable 打不开时回退裸 mode=ro,把侧车写回来了 —— 不许再有。

    用真实的 opener + 一次真实的 sqlite3.connect 失败来验:失败必须原样抛出,
    而不是换个更宽松的 URI 再试一次(那次重试正是侧车的来源)。
    """
    mod = _mem_module()
    try:
        db = layers["db"]
        real_connect = sqlite3.connect
        uris: list[str] = []

        def flaky(database, *a, **kw):
            uris.append(str(database))
            if len(uris) == 1:
                raise sqlite3.OperationalError("simulated: this build has no immutable VFS")
            return real_connect(database, *a, **kw)

        mod.sqlite3.connect = flaky
        try:
            with pytest.raises(sqlite3.Error):
                mod.connect_immutable(db)
        finally:
            mod.sqlite3.connect = real_connect
        assert len(uris) == 1, f"打不开就该抛,不该再试一次:{uris}"
        assert "immutable=1" in uris[0] and "mode=ro" in uris[0]
        assert sorted(p.name for p in db.parent.iterdir()) == ["memory.db"]
    finally:
        sys.modules.pop("mem_under_test_find", None)


def test_find_degrades_the_whole_answer_when_a_live_wal_hides_rows(layers):
    """有并发写者、行还没 checkpoint:immutable 读看不见 -> 未命中必须标降级。"""
    writer = sqlite3.connect(layers["db"])
    writer.execute("PRAGMA journal_mode = WAL")
    writer.execute("INSERT INTO entries VALUES ('wal-only', '还没 checkpoint 的行')")
    writer.commit()
    try:
        wal = Path(str(layers["db"]) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0, "fixture 没造出 live WAL"
        result = _find(layers, "wal-only")
        assert result.returncode == 1
        assert "降级" in result.stdout
        assert "未命中不等于不存在" in result.stdout
        assert "live WAL" in result.stdout
        assert "no layer has" not in result.stdout
    finally:
        writer.close()


def test_find_still_answers_cleanly_for_rows_the_live_wal_already_holds(layers):
    """同一个 live WAL 下,主库里已有的行照常命中 —— 只是清单要标"可能不全"。"""
    writer = sqlite3.connect(layers["db"])
    writer.execute("PRAGMA journal_mode = WAL")
    writer.execute("INSERT INTO entries VALUES ('wal-only', '还没 checkpoint 的行')")
    writer.commit()
    try:
        result = _find(layers, "only-in-sqlite")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "entry:only-in-sqlite" in result.stdout
        assert "可能不全" in result.stdout
    finally:
        writer.close()


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


# --- M-01 2026-08-08:文件记忆层不是一个目录,是一堆命名空间 -------------------
#
# CC 按「项目路径的写法」各开一个命名空间,所以同一摊活从 ~/claude pj/zmd 干和从
# ~/zmd-pj 干,卡片落进两个平级目录。08-08 普查:本机 6 个 ~/.claude/projects/*/
# memory/,234 张卡里 153 张在当前命名空间之外(最大的一个 117 张,五月 cand-C
# 考古就在里面,08-04 为找不到它花过真金白银)。find 是唯一的跨层入口,它只扫一个
# 目录 = 那 153 张卡根本不在搜索面上,而 find 的未命中还长得像权威结论。
#
# 夹具用假 HOME 走真 CLI:`Path.home()` 在 POSIX 上认 HOME 环境变量,模块常量
# FILE_MEMORY_DIR 是 import 时算的,所以子进程里换 HOME 就等于换掉整个文件记忆层
# ——不 mock、不改被测码,和生产同一条路径。


CURRENT_NS = "-home-zhuran24-zmd-pj"
ORPHAN_NS = "-home-zhuran24-claude-pj-zmd"


@pytest.fixture()
def fake_home(tmp_path):
    """假 HOME:两个命名空间,当前的一张卡 + 孤儿的一张卡(用真实的下划线命名)。"""
    home = tmp_path / "home"
    projects = home / ".claude" / "projects"
    current = projects / CURRENT_NS / "memory"
    orphan = projects / ORPHAN_NS / "memory"
    third = projects / "-home-zhuran24-claude-pj-pj1" / "memory"
    for d in (current, orphan, third):
        d.mkdir(parents=True)
    (current / "in-current-namespace.md").write_text("# 当前命名空间\n", encoding="utf-8")
    (current / "both-namespaces.md").write_text("# 当前的同名卡\n", encoding="utf-8")
    # 117 张孤儿卡全是 snake_case;当前命名空间全是 kebab-case。
    (orphan / "project_cand_c_column_generation_phase0_go.md").write_text(
        "# 五月 cand-C 考古\n", encoding="utf-8"
    )
    (orphan / "both_namespaces.md").write_text("# 孤儿的同名卡\n", encoding="utf-8")
    # 文件名与 frontmatter id 不一致、且 id 是 snake_case:走 id 行那条分支
    (orphan / "renamed_orphan_card.md").write_text(
        "---\nid: snake_id_not_in_filename\n---\n正文\n", encoding="utf-8"
    )
    (third / "only_in_third_namespace.md").write_text("# 第三个命名空间\n", encoding="utf-8")
    return {"home": home, "current": current, "orphan": orphan, "third": third}


def _find_with_home(fake_home, tmp_path, needle, *extra):
    """真 CLI + 假 HOME + 不传 --file-memory-dir(走模块默认常量)。"""
    env = dict(os.environ, HOME=str(fake_home["home"]))
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [
            sys.executable,
            str(MEM),
            "--db",
            str(tmp_path / "no-such.db"),
            "find",
            needle,
            "--cards-dir",
            str(tmp_path / "no-such-cards"),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_find_reaches_cards_in_an_orphan_namespace(fake_home, tmp_path):
    """承重:当前命名空间之外的卡必须能被找到,否则 153 张卡等于不存在。"""
    result = _find_with_home(fake_home, tmp_path, "project_cand_c_column_generation_phase0_go")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "project_cand_c_column_generation_phase0_go.md" in result.stdout
    assert ORPHAN_NS in result.stdout


def test_orphan_hits_are_labelled_with_their_namespace(fake_home, tmp_path):
    """命中要带来源:分不清「我现在写进去的收件箱」和「五月的旧库」就等于没找到。"""
    result = _find_with_home(fake_home, tmp_path, "project_cand_c_column_generation_phase0_go")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"[orphan:{ORPHAN_NS}]" in result.stdout
    assert "[current]" not in result.stdout


def test_current_namespace_hits_are_labelled_current(fake_home, tmp_path):
    result = _find_with_home(fake_home, tmp_path, "in-current-namespace")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[current]" in result.stdout
    assert "orphan:" not in result.stdout


def test_current_namespace_sorts_before_orphans(fake_home, tmp_path):
    """同名卡两边都有时,当前命名空间那张必须排在前面。"""
    result = _find_with_home(fake_home, tmp_path, "both-namespaces")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[current]" in result.stdout and f"[orphan:{ORPHAN_NS}]" in result.stdout
    assert result.stdout.index("[current]") < result.stdout.index(f"[orphan:{ORPHAN_NS}]")


def test_find_sweeps_every_namespace_not_just_two(fake_home, tmp_path):
    result = _find_with_home(fake_home, tmp_path, "only_in_third_namespace")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "-home-zhuran24-claude-pj-pj1" in result.stdout


def test_snake_case_cards_match_by_their_own_name(fake_home, tmp_path):
    """`norm()` 把 `_` 折成 `-`,只 norm 针不 norm 文件名 = snake_case 卡用任何拼写
    都找不到(117 张孤儿卡全是 snake_case)。两边都要 norm。"""
    hyphen = _find_with_home(fake_home, tmp_path, "project-cand-c-column-generation-phase0-go")
    assert hyphen.returncode == 0, hyphen.stdout + hyphen.stderr
    assert "project_cand_c_column_generation_phase0_go.md" in hyphen.stdout
    underscore = _find_with_home(fake_home, tmp_path, "project_cand_c_column_generation_phase0_go")
    assert underscore.returncode == 0, underscore.stdout + underscore.stderr
    assert "project_cand_c_column_generation_phase0_go.md" in underscore.stdout


def test_snake_case_frontmatter_id_matches_too(fake_home, tmp_path):
    """文件名对不上时靠 frontmatter `id:` 找 —— 那条分支也得两边都 norm。"""
    result = _find_with_home(fake_home, tmp_path, "snake-id-not-in-filename")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "renamed_orphan_card.md" in result.stdout


def test_miss_text_owns_up_to_how_many_namespaces_were_swept(fake_home, tmp_path):
    result = _find_with_home(fake_home, tmp_path, "nothing-anywhere-at-all")
    assert result.returncode == 1
    assert "个其他命名空间已同扫" in result.stdout


def test_explicit_file_memory_dir_override_is_not_expanded(layers, tmp_path):
    """`--file-memory-dir` 指到别处时只扫那一个目录 —— 不许顺手把它的邻居也拖进来。

    否则拿 tmp 夹具跑测试会扫到别的会话的 basetemp,结果不确定。
    """
    sibling = layers["file_memory"].parent / "memory"
    sibling.mkdir()
    (sibling / "should-not-be-found.md").write_text("# 邻居\n", encoding="utf-8")
    result = _find(layers, "should-not-be-found")
    assert result.returncode == 1, result.stdout
    assert "should-not-be-found.md" not in result.stdout


def test_file_memory_layer_limit_is_a_layer_budget_not_a_per_dir_budget(fake_home, tmp_path):
    """`--limit` 是「每层最多报几条」;扩成多命名空间后不能变成「每个目录 N 条」。

    夹具刻意造成 2 + 4 而不是 4 + 4:第一个目录必须**吃不满**预算,否则外层那句
    `if len(hits) >= limit: break` 会替真正的承重件(`limit - len(hits)`)挡住变异,
    用例就变成钉 break 而不是钉预算算术(M1-E 实测存活过一次)。
    """
    for i in range(2):
        (fake_home["current"] / f"budget-card-{i}.md").write_text("# x\n", encoding="utf-8")
    for i in range(4):
        (fake_home["orphan"] / f"budget_card_{i}.md").write_text("# x\n", encoding="utf-8")
    result = _find_with_home(fake_home, tmp_path, "budget-card", "--limit", "3")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0].startswith("find: 3 hit(s)"), result.stdout
