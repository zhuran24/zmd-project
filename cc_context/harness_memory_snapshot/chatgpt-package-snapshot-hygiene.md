---
name: chatgpt-package-snapshot-hygiene
description: "GPT 外发快照包卫生——包套娃指数膨胀(sha 唯一名包复制进補丁包/而 build_v80 不排除该目录→每打一包嵌入全部旧包翻倍链 12→818MB,blob 阶段必死;修=build EXCLUDED_DIR_NAMES 加補丁包,唯一名包存放目录必须在排除清单内);在途审查单未收完别清旧快照包(有在途单传新包加 --keep-old-snapshots,等槽清空再清)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

GPT 外发任务的快照包打包/清理卫生(2026-06-12/13):

- **包套娃指数膨胀 (2026-06-12)**: sha 唯一名包复制进 `補丁包/` 而 build_v80 不排除该目录 → 每打一包嵌入全部旧包 (12→52→102→204→407→818MB 翻倍链), 818MB 包传文件区 blob 阶段必死。修 = build EXCLUDED_DIR_NAMES 加 `補丁包`。教训: 唯一名包的存放目录必须在打包排除清单内。
- **在途单未收完别清旧快照包 (06-13 自踩, 未出事但险)**: `--replace` 清旧包时若另一审查单还在途用旧包, 其沙盒开工时已解包所以大概率无碍, 但属赌运气。纪律 = 有在途单时传新包加 `--keep-old-snapshots`, 等槽清空再补清理。

相关:[[chatgpt-browser-automation-pitfalls]] [[chatgpt-project-sources-upload]]
