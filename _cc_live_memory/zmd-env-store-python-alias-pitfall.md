---
name: zmd-env-store-python-alias-pitfall
index_summary: "商店 Store Python 半夜自动升级弄坏 `python` alias(静默失败 exit 49/9009 会话中途挂),python3.13.exe 是好的;alias 坏时 pre-commit 误报 STALE 先用 python3.13 复核"
description: zmd 坑——商店 Store Python 半夜自动升级会弄坏 `python` alias(静默失败 exit 49/9009 会话中途挂), `python3.13.exe` 是好的;别用真身 exe+PYTHONPATH;alias 坏时 pre-commit 误报 STALE 先用 python3.13 复核
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **坑(2026-06-12 实测踩过): Store Python 会半夜自动升级并弄坏 `python` alias** —— 3.13.13→3.13.14 升级后 `python`/`python.exe` 执行别名静默失败(无输出 exit 49/9009,会话中途突然挂),但 **`python3.13.exe` alias 是好的**(完整 AppX 上下文, user site-packages/ruff/pytest 全正常)。修法: 改用 `python3.13` 跑一切;或等重启自愈。**结局(06-12 晚收口)**: owner 为摆脱商店自动更新装了 python.org 3.13.14 到 Program Files 并设为默认(起初忘装包,`python` 一度 ModuleNotFoundError);已 `pip freeze --no-deps` 克隆补齐并验证全绿,**现在 `python` = 主环境**(见上),商店版降为备份。商店自动更新再坏也只伤备份,不用专门关。别用「真身 exe + PYTHONPATH」组合——pytest-randomly/ruff shim 在那条路上断。**连带症状**: pre-commit hook 内部调 `python` 的检查会静默失败并误报 (实测 commit 时报 "authoritative_numbers.json STALE" 但 `python3.13 scripts/gen_authoritative_numbers.py --check` = up to date, 焊死的 currency 测试也绿)——alias 坏掉期间 hook 的 WARN 先用 python3.13 复核再信。

相关:[[zmd-checkout-env]] [[zmd-env-python]]
