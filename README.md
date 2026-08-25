# ZMD Research Tree

这是 ZMD 的长期研究树，分支固定为 `research/main`。它负责问题理解、数学推导、构造、反例、求解器实验、表示与切分重构，以及把成熟结果整理成待认证候选。

它不是认证树，也不是旧主树的延续用途：

- `/home/zhuran24/zmd-pj`：旧主树，今后作为 Git 历史与既有材料的保留树，只读使用。
- 当前 worktree：研究树，允许大胆探索，但不得自授 production、certified、U/L 或发布效力。
- 认证树：尚未建立；成熟结果以后只通过选定的 promotion packet 过境，不整体合并研究分支。

## 进入研究树

先运行：

```bash
/home/zhuran24/zmd-pj/.venv/bin/python research_lab/tools/research_tree.py enter
```

随后按输出读取 `research_lab/STATE.txt` 与当前 campaign。第一次进入或目标发生变化时，再读 `research_lab/PROGRAM.txt`。

## 三层目标

1. 当前 campaign：先得到零条件完整布局。
2. 当前项目终点：在当前基地的完整预期语义下，让上下界闭合并形成可独立复验的 certified-exact 结果。
3. 未来预期：形成可绑定问题、目标与上下文，能够跨实例、跨基地并最终支持多基地联合优化的通用研究与精确求解体系。

三层目标必须同时可见，但不能互相冒充。当前 campaign 决定眼前资源，项目终点防止局部胜利被误写成完成，未来目标防止今天的方便把架构焊死。

## 研究区

- `research_lab/START.txt`：冷启动入口。
- `research_lab/PROGRAM.txt`：稳定总纲与目标层级。
- `research_lab/STATE.txt`：全树当前状态与 campaign 指针。
- `research_lab/campaigns/`：每条当前研究战役的自包含工作面。
- `research_lab/local/`：日志、缓存、临时模型与可再生运行产物，全部不进 Git。
- `research_lab/promotion/`：未来送往认证树的候选包模板。

旧仓库中的 `src/`、`rules/`、`specs/`、`docs/` 与历史研究材料仍是研究素材和代码底座，但不再是研究 agent 的默认注意力入口。
