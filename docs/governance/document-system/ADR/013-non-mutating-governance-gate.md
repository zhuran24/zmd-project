# DOC-ADR-013：以非变异统一门执行文档治理

状态：Accepted

日期：2026-08-13

## 背景

第三阶段已经把当前文档职责、知识真源、局部前门和兼容跳转收束成可机器检查的结构，但检查仍由操作者逐条调用。这样有三个缺口。

第一，本地、pull request、push 和周期审计可能运行不同命令。第二，某个 checker 或测试若顺手重写生成页、index、tracked 文件或非忽略临时文件，随后再对修改后的树报绿，绿色结果就不再对应原输入。第三，并行回归如果共享 basetemp、缓存或临时目录，会把进程顺序和相互清理带进结果。

## 决定

引入 manifest-owned 的文档治理门：

```text
.docsystem/manifest.json
  → governance_gate registry + schema
  → devtools/document_governance_gate.py
  → local / PR / push / weekly profiles
```

治理门遵守以下协议：

1. 每条 lane 使用 argv 直接启动，不经过 shell 拼接。
2. 每条 lane 获得独立进程、独立仓外临时目录、pycache、mypy、ruff 和 pytest 临时坐标。
3. 可以并行执行只读 lane，但执行前后必须比较同一种 `git_visible_state_v1` 指纹。
4. 指纹覆盖 HEAD、index entries、Git-visible path set、Git status，以及 modified、deleted 和非忽略 untracked 路径的当前 bytes/mode。
5. ignored cache 与 basetemp 不属于仓库输入，必须落在仓外临时目录，不靠事后清理掩盖。
6. 任一 lane 非零、超时，或前后指纹不同，整个 gate fail closed。
7. `changed` profile 服务本地、PR 和 push；`weekly` 增加完整历史 code-assets replay。两者引用同一 registry，不在 workflow 中复制 lane 清单。
8. current-only code-assets lane必须明确声明它不验证 frozen historical baseline 或 certified-source receipt；完整历史 replay 保留为独立 lane，不能用较窄检查冒充。

## 后果

优点：

- CI 和本地共享同一机器清单；
- 检查结果绑定到明确输入状态；
- 并行回归不共享临时目录；
- 新增 checker 必须进入 registry、schema、doctor 和红测；
- 供应快照缺少历史 Git 对象时，current lane仍可验证当前分类，但 full/weekly lane继续诚实 fail closed。

代价：

- gate 配置、runner、CI workflow 和红测成为新的 framework core；
- 任何会“自动修复”的 checker 都不能直接进入只读 lane，必须拆成显式 `render --write` 与 `check`；
- full/weekly profile 需要完整 Git object graph，轻量快照不能伪造其通过。

## 被拒绝的方案

- **只在 CI 手写命令列表**：本地和 CI 会漂移，框架也无法发现漏接线。
- **gate 先自动生成再检查**：会把陈旧投影改成新投影后报绿，失去对输入树的验收意义。
- **所有 lane 共用一个 pytest/cache 目录**：并行执行会互删或读取彼此残留。
- **为了快而只比较 `git status` 文本**：无法单独绑定 index、路径集合和已存在 dirty bytes。
