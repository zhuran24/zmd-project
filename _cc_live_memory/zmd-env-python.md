---
name: zmd-env-python
index_summary: "无 .venv;主环境=C:\\Program Files\\Python313\\ 的 python.org 3.13.14(`python`);依赖 --no-deps 克隆(litellm 钉 jsonschema 必须 --no-deps);商店版 python3.13 备份"
description: zmd 用哪个 Python 跑——无 .venv;主环境=C:\Program Files\Python313\ 的 python.org 3.13.14(`python`);依赖 --no-deps 克隆(litellm 钉 jsonschema 必须 --no-deps);商店版 python3.13 是备份
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **无 `.venv`** — **主环境(2026-06-12 起) = `C:\Program Files\Python313\` 的 python.org 3.13.14(`python`,无自动更新)**,依赖从商店版 `pip freeze` 经 TUNA 镜像 `--no-deps` 全量克隆(249 包,ortools 9.15.6755;克隆当天全量 pytest 2923 绿)。**已知良性不一致**: litellm 钉 `jsonschema==4.23.0` 但实装 4.25.1(与源环境一致)——pip 解析器会因此 ResolutionImpossible,**克隆/批量补装必须 `--no-deps`**。商店版(`python3.13`)保留作备份,此后不再保证同步;装新依赖默认进主环境。git hooks(pre-push/pre-commit)解释器优先级已翻成 `python` 优先。

相关:[[zmd-checkout-env]] [[zmd-env-store-python-alias-pitfall]]
