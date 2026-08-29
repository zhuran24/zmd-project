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
                    └── certification/main
```

第一代根提交 `270bb2d` 的标题是 `Initial commit: migrate from Codex workspace`。它只标记项目第一次进入这份 Git，不能作为项目真正创建日期。

## 第一代与第一次 Git 重建

第一代主活动历史的原始末端是：

```text
2101450636b17e98504fb73d0680a95f601c9565
```

脱敏后的公开末端是 `a7a827164880426319b78f1ca60a9d7cab50b49d`；根提交早于凭据进入历史，因此公开根仍为 `270bb2d243157c74c36cd4de82a029db7859e9fc`。

公开主入口为 `history/first-generation`，原始分支保存在 `history/epoch-1/heads/*`，旧远端引用保存在 `history/epoch-1/remotes/*`。

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

公开主入口为 `history/second-generation`，原始分支保存在 `history/epoch-2/heads/*`，旧远端引用保存在 `history/epoch-2/remotes/*`。

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

111 个删除路径由 Claude Code 记忆、GitHub workflow、Git hook 和根级 agent 说明组成。第二次重建前的工作树另有 3 个 tracked modifications 和 132 个 untracked entries，因此清理前标签只表示当时 committed HEAD，不表示完整磁盘快照。

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

## 连续性标签

| 标签 | 含义 |
|---|---|
| `history/clear-1-before-20260616` | 第一次重建前的 committed HEAD |
| `history/clear-1-after-20260616` | 第一次重建后的无父根提交 |
| `history/clear-2-before-20260809` | 第二次重建前的 committed HEAD |
| `history/clear-2-after-20260809` | 第二次重建后的无父根提交 |
| `history/three-tree-split-20260824` | 三树共同分叉点 |

## 旧 GitHub 支线

旧仓库 `zhuran24/zmd_pj` 的主线停在第二代中途；其两个 `legacy-20260701-prerebuild-*` 分支不在本地第一、二代完整备份中。本公开仓库把它们保存在 `history/old-github-zmd_pj/*`。

另一个旧仓库 `zhuran24/zmd-legacy` 的独立 `gemini-line` 同样不在第一代 bundle 中，本公开仓库把它保存在 `history/old-github-zmd-legacy/*`。

## 公开历史与本地法证档案

第一代历史曾包含一项 Google API 凭据。公开历史已在所有普通文本和 ZIP 内部文件中机械替换符合该凭据格式的值，因此受影响的第一代公开提交使用新的 commit ID。提交顺序、作者、时间、消息、文件路径和非敏感内容继续保留。

本地统一法证镜像和两份原始备份保留原始 Git 对象与原始 commit ID。机器索引中的 `original_*` 字段均指本地法证身份。

公开仓库保存：

- 所有经过公开内容审查的有名分支；
- 旧 GitHub 仓库独有的有名支线；
- 7 个仅由第三代 detached DevSpace worktree 保活的历史 tip。

公开仓库不把已经失去引用的 reflog-only、dropped stash、临时 index、untracked 或 WIP 快照制造成公开分支。它们继续保存在本地法证档案中。
