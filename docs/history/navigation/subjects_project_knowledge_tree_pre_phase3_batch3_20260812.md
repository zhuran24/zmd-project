# 项目知识面

仓库内的可追踪知识由三类对象组成：

- machine source，负责规则、义务、gate 和 checked-in solver 状态；
- claim / decision ledger，负责稳定身份、作用域、前提、后果和 supersede 关系；
- dossier，负责把结论连回原始研究包、外审包和本地可选工件。

聊天记录、个人笔记或外部记忆系统都可能提供发现线索，但不会自动改变仓库知识状态。要让一个判断成为可查的项目结论，必须把它落到上述源之一，并通过 [`../../devtools/check_knowledge_docs.py`](../../devtools/check_knowledge_docs.py) 的一致性检查。
