# 旧文档树架构主题兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

文档框架的完整现行定义已进入 framework architecture；本主题路径只保留稳定跳转。

## 当前入口

- [文档系统架构](../governance/document-system/ARCHITECTURE.md)：当前类型系统、策略继承、分区与生成投影。
- [维护协议](../governance/document-system/MAINTAINING.md)：安全改变框架、schema、policy 和迁移的方法。

## 维护边界

- 不要在主题页复制第二份架构定义。
- 退出当前职责前的正文见 [历史快照](../history/navigation/subjects_doc_tree_architecture_pre_phase3_batch3_20260812.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
