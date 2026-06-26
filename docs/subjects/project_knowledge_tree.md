# 项目知识面

项目有两个相互引用但物理独立的知识面：

1. Git 工作树中的代码、锁文件、机器 JSON、规格和文档。
2. `cc_memory/memory.db` 中的协作记忆节点、事实和边。

它们之间没有自动 projection。文档修改不会自动写入 memory，memory 修改也不会自动改文档。需要变更状态时，应分别按各自工具和约束更新，并保留 supersede/dependency 边，使旧判断与新判断的关系可追踪。

禁止复活 `cc_context`、`_cc_live_memory` 或第二套 memory graph。
