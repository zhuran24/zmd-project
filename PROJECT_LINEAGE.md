# ZMD 项目连续性与 Git 历史

状态：公开历史族谱 · 核验日期：2026-08-29

ZMD 是一个连续项目。历史上两次完成完整备份并重建 `.git`，因此 Git 对象图中存在三个无父根时期；这代表 Git 记录断代，不代表研究项目重新开始。“Git 世代”只表示一段连续的 Git parent 链，不表示一个新项目。

## 总图

```text
第一代 Git
270bb2d ... 2101450（本地原始 ID；公开末端为 a7a8271）
                    ║ 第一次备份并重建 .git
                    ║ 项目文件和研究工作继续
第二代 Git          ║
79afc8f ... 6ca5f38
                    ║ 第二次备份并重建 .git
                    ║ 项目文件和研究工作继续
第三代 Git          ║
a72003b ... ede4fa4
                    ├── main
                    ├── research/main
                    └── 认证树
                        ├── certification/main
                        └── certification/baseline-repair-20260825
```

第一代根提交 `270bb2d` 的标题是 `Initial commit: migrate from Codex workspace`。它只标记项目第一次进入这份 Git，不能作为项目真正创建日期。

## 第一代与第一次 Git 重建

第一代主活动历史的原始末端是：

```text
2101450636b17e98504fb73d0680a95f601c9565
```

脱敏后的公开末端是 `a7a827164880426319b78f1ca60a9d7cab50b49d`；根提交早于凭据进入历史，因此公开根仍为 `270bb2d243157c74c36cd4de82a029db7859e9fc`。

公开固定入口为标签 `history/clear-1-before-20260616`。第一代原始本地分支、当时保存的远端分支位置和公开脱敏后的提交对应关系，记录在 [history/ref-architecture.json](history/ref-architecture.json)；它们不再占用 GitHub 分支列表。

2026-06-16，旧 Git、项目记忆和 Claude Code 脚手架完成备份后从工作目录中清除。29 分 56 秒后，同一项目目录以无父根提交 `79afc8f478fa6f706ad0396b8df50235e1c640fe` 建立第二代 Git。

跨断点文件账：

| 项目 | 数量 |
|---|---:|
| 清理前 tracked paths | 2357 |
| 清理后 tracked paths | 2227 |
| 共同路径 | 2223 |
| 共同路径中字节完全相同 | 2174 |
| 共同路径中字节发生变化 | 49 |
| 仅清理前存在 | 134 |
| 仅清理后存在 | 4 |

134 个清理前独有项主要是 128 份 agent transcript，以及少量 hint-trial、checkpoint、共享说明和 MCP 配置。49 个共同路径差异中，47 个只有换行格式差异；实质内容变化集中在 `.gitattributes` 和 `.gitignore`。

完整 portable bundle（精确本机位置只记录在私有法证索引中）：

```text
zmd_repo_all.bundle
size: 162358410 bytes
sha256: 8bb34b80a5f845e907b7a2b0dd87ddd76f4498ea210c06dc4238318f31ec751b
```

该 bundle 通过 `git bundle verify`，包含 27 个 advertised refs；第一代有名引用合计可达 937 个提交。

## 第二代与第二次 Git 重建

第二代主线从 `79afc8f478fa6f706ad0396b8df50235e1c640fe` 延续到：

```text
6ca5f38cf05baaf530b8b6f9ebe628f803a9405b
```

公开固定入口为标签 `history/clear-2-before-20260809`。第二代原始本地分支和当时保存的远端分支位置，完整记录在 [history/ref-architecture.json](history/ref-architecture.json)；它们不再作为可移动分支。

2026-08-09，完整 `.git` 和 Claude Code 基础设施再次备份并清除；项目科学主体保留在原工作目录中。新根 `a72003b527786254bf6fa699fe252610f4c8658b` 建立第三代 Git。

跨断点文件账：

| 项目 | 数量 |
|---|---:|
| 清理前 tracked paths | 3533 |
| 清理后 tracked paths | 3422 |
| 共同路径 | 3422 |
| 共同路径中字节完全相同 | 3415 |
| 共同路径中字节发生变化 | 7 |
| 仅清理前存在 | 111 |
| 仅清理后存在 | 0 |

111 个删除路径由 Claude Code 记忆、GitHub workflow、Git hook 和根级 agent 说明组成。第二次重建前的工作树另有 3 个已经修改但尚未提交的文件和 132 个未纳入 Git 的项目，因此清理前标签只固定当时最后一次已经提交的状态，不包含这些尚未提交的磁盘改动。

完整 Git 档案（精确本机位置只记录在私有法证索引中）：

```text
git-dir.tar.zst
size: 30622889 bytes
sha256: dafeaa761c0993f50f516f9b94c9ed59027f0de3a761de22284f688f29b86b0a
```

第二代 `main` 有 820 个提交；全部有名分支合计可达 836 个提交。

## 三树时期

三条当前路线共享提交：

```text
ede4fa4b883d0aa965141700d2475af1b96817c8
```

| 角色 | 规范分支 | 分叉后的首个独有提交 |
|---|---|---|
| 历史材料树 | `main` | `c0bd300b2ace087c36ac4e8f69cf304811330332` |
| 研究树 | `research/main` | `c3f02946957869c7d90fc94087699c4443e7753b` |
| 认证树 | `certification/main` | `7392088898e2317fa47f497eb42b4de1880ea1da` |

这是普通 Git 分叉，三条路线拥有共同 parent 历史。

公开仓库有四个分支，但项目仍然是三棵树。`certification/baseline-repair-20260825` 是认证树内部的基线修复线，不是第四棵树；截至 2026-08-29 核验时，它与 `certification/main` 指向同一个提交。

## 连续性标签

| 标签 | 含义 |
|---|---|
| `history/clear-1-before-20260616` | 第一次重建前最后一次已经提交的状态 |
| `history/clear-1-after-20260616` | 第一次重建后的无父根提交 |
| `history/clear-2-before-20260809` | 第二次重建前最后一次已经提交的状态 |
| `history/clear-2-after-20260809` | 第二次重建后的无父根提交 |
| `history/three-tree-split-20260824` | 三树共同分叉点 |

## 2026-08-29 公开引用整理

分支是会随着后续提交向前移动的工作入口；标签是固定在某个提交上的历史标记。第一次汇总公开历史时，为了不漏掉任何入口，把几种不同性质的 Git 指针都暂时做成了 GitHub 分支：

| 当时的指针来源 | 名称数 |
|---|---:|
| 现在实际工作的分支 | 4 |
| 第一代本地分支 | 10 |
| 第一代保存的远端分支位置 | 13 |
| 第二代本地分支 | 37 |
| 第二代保存的远端分支位置 | 3 |
| 第三代没有分支名、只由 DevSpace 工作目录保活的末端 | 7 |
| 为浏览第一、二代而人工增加的入口 | 2 |
| 两个旧 GitHub 仓库的分支 | 6 |
| 合计 | 82 |

所以 GitHub 曾显示 82 个分支，并不表示项目真的同时开发 82 条路线。多个名字还会指向同一个提交：82 个名字只有 60 个不同的末端提交（Git 通常称为 tip）。

如果 tip A 是 tip B 的祖先，保留 B 就已经把 A 包含在历史里；只有不被任何其他 tip 包含的，才叫“独立末端”。60 个不同 tip 中共有 21 个独立末端；其中 3 个是当前分支的不同末端（两条认证分支同点），18 个是历史末端。18 个历史末端中，第一、二次重建前的两个末端已经由连续性标签固定，另外 16 个新建了 `history/endpoints/*` 固定标签。

整理后的公开分支只有：

| 分支 | 作用 |
|---|---|
| `main` | 历史材料树 |
| `research/main` | 研究树 |
| `certification/main` | 认证树主线 |
| `certification/baseline-repair-20260825` | 认证树内的基线修复线 |

其余 78 个分支名已经移除；这些名字指向 57 个不同提交。在删除 78 个分支后、提交本记录前的核验快照中，清理前已有的 2,273 个提交仍全部可达，提交集合的 SHA-256 仍是 `4ccff0b135aa602f060e7c80dd73f95d902d77d5d9217d09fb17c979bb63852b`。

[机器索引](history/ref-architecture.json)保存了原来 82 个名字中的每一个：当时的名字、来源类型、tip 提交、是否属于独立末端，以及现在由哪个分支或标签直接固定或作为祖先保活。也就是说，分支列表变干净了，但“当时有哪些入口、哪些是末端、它们互相是什么包含关系”没有丢。

## 旧 GitHub 支线

旧仓库 `zhuran24/zmd_pj` 删除前共有四个分支：`main`、`topology-opt`、`legacy-20260701-prerebuild-main` 和 `legacy-20260701-prerebuild-topology-opt`。主线停在第二代中途；两个 `legacy-20260701-prerebuild-*` 分支不在本地第一、二代完整备份中，并共同形成一个独立末端。这个末端由 `history/endpoints/old-github/zmd-pj/legacy-prerebuild-main` 标签固定，四个旧名字和祖先关系都记录在机器索引中。

四条旧分支与新仓库逐一核对哈希后，`zhuran24/zmd_pj` 于 2026-08-29 从 GitHub 删除。`zhuran24/zmd-legacy` 不属于这次淘汰范围，继续保留。

另一个旧仓库 `zhuran24/zmd-legacy` 的独立 `gemini-line` 同样不在第一代 bundle 中；它由 `history/endpoints/old-github/zmd-legacy/gemini-line` 标签固定，旧分支名记录在机器索引中。

## 公开历史与本地法证档案

第一代历史曾包含一项 Google API 凭据。公开历史已在所有普通文本和 ZIP 内部文件中机械替换符合该凭据格式的值，因此受影响的第一代公开提交使用新的 commit ID。提交顺序、作者、时间、消息、文件路径和非敏感内容继续保留。

本地统一法证镜像和两份原始备份保留原始 Git 对象与原始 commit ID。[公开引用机器索引](history/ref-architecture.json)记录的是脱敏后公开图中的分支名和公开 commit ID；第一代原始末端与公开末端的对应关系见 [history/continuity.json](history/continuity.json)。

公开仓库保存：

- 4 个实际工作的公开分支；
- 5 个连续性标签和 16 个额外历史末端标签；
- 清理前公开的 82 个分支名称（其中 4 个保留、78 个移除）、来源类型、提交和保活关系的完整机器索引；
- 旧 GitHub 仓库独有的提交，以及当时没有分支名、只由 DevSpace 工作目录保活的 7 个第三代末端提交。

公开仓库不把已经失去引用的 reflog-only、dropped stash、临时 index、untracked 或 WIP 快照制造成公开分支。它们继续保存在本地法证档案中。
