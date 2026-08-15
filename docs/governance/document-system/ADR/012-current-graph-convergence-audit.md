# DOC-ADR-012｜用 current 文档图完成职责收束验收

状态：Accepted
日期：2026-08-12

## 背景

显式 policy、前门注册表和 section registry 已经能说明一份文档是什么、由哪个入口进入，以及旧路径如何兼容。但“每个 current 文档都声明了 section”仍不足以证明读者或 agent 能从局部入口真正到达它；“每个文件都有 purpose”也不足以阻止多份 living 文档共享同一个含糊职责。

第三阶段还发现两种会让旧问题复生的路径：手写 current guide 继续固化 gate、hash 或测试收据，以及新入口继续把生成式兼容跳转当作正常下钻路径。它们都可能在链接与 schema 完全有效时悄悄恢复多套现态。

## 决定

增加两个框架不变量：

- `DOC-INV-015` 要求每个非兼容跳转的 current Markdown，都能从它声明 section 的唯一入口，经同一 section 内的 current Markdown 链接到达。
- `DOC-INV-016` 要求可变 current 文档拥有可区分的唯一职责；`reference_only` 或 `forbidden` 文档不得复制前门注册表中登记的易变状态模式；current 正文不得链接生成式兼容跳转。

`devtools/docctl.py` 从现有真源计算完整审计，并生成 `docs/CONVERGENCE_REPORT.md`。报告不是新的手写 dashboard，也不授予项目 authority。它只投影：

- current Markdown 与 section 数量；
- 每个 section 的成员和局部可达性；
- 重复可变职责；
- 手写易变状态命中；
- current 文档到 retired redirect 的链接；
- fail-closed 阻断项。

`docctl doctor` 同时检查报告新鲜度与审计结果。新增 current 文档若只有 policy 标签、却没有局部入口链接，框架将阻断。

## 迁移

1. 为 certification 建立有界局部入口，保留 `PROJECT_LOCK.md` 的 owner-only authority。
2. 补齐 project manual、specifications、operations、research、history 与 implementation navigation 的断链。
3. 将仍混入批次状态、hash、测试收据或历史 inventory 的 current 正文做字节保真归档，再把现行页改写为稳定合同。
4. 给可变 current 文档分配可区分的精确 purpose。
5. 生成职责、section、compatibility 与 convergence 投影，并加入回归测试。

## 后果

局部入口现在不只是“存在”，而是对其 current 成员形成可验证的导航闭包。兼容跳转保留旧 URL，但不能重新成为 current 图的承重节点。易变状态可以存在于机器 authority、生成投影和历史 evidence 中，却不能再次渗回手写 current guide。

代价是新增 current 文档时必须同时处理 purpose、section 和入口链接；改变审计语义时必须原子更新 invariant、ADR、架构、维护指南、迁移和测试。这一成本被限制在框架变更，不会让普通内容修改每次加载全套手册。
