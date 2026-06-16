# 代码导航图(找路用)

> ⚠️ 这张图只说"代码放在哪、模块叫什么"——**不代表任何模块真做到了它名字暗示的事**,也不标"哪里重要 / 先读哪个"。从哪入手、重点怀疑哪里你自己定,一切以代码实际实现为准。

## 入口
- `main.py` — 程序入口

## src/ 顶层目录(各放什么)

| 目录 | 放什么 |
|---|---|
| `src/search/` | 外层候选搜索、Benders 主循环、campaign 持久化、并行调度 |
| `src/models/` | CP-SAT 建模:放置 master、几何 master、各子问题 |
| `src/cuts/` | Benders cut 的生成与生命周期、oracle |
| `src/preprocess/` · `src/placement/` · `src/interchange/` | 预处理、候选生成、数据交换 |
| `src/io/` · `src/runtime/` | 持久化 / 序列化、运行时(CPU 拓扑 / checkpoint) |
| `src/render/` · `src/adapters/` | 渲染、外部数据适配(postprocess) |
| `src/tests/` | 测试 |
| `rules/` · `specs/` · `data/preprocessed/` | 规则真值、规格文档、冻结输入工件 |

## 求解主流程(按调用顺序——这是结构事实,不是"它保证了什么")

```
main.py
 └ src/search/outer_search.py             外层候选矩形循环
    └ src/search/benders_loop.py          Benders / LBBD 分解主循环
       ├ src/models/master_model.py              放置 master(CP-SAT)
       ├ src/models/exact_coordinate_master.py   ghost rectangle 坐标 master
       ├ src/models/binding_subproblem.py        端口绑定子问题
       ├ src/models/routing_subproblem.py        网格布线子问题
       ├ src/models/flow_subproblem.py           多商品流子问题
       └ src/cuts/lifecycle.py                   子问题不可行 → 生成 cut 收紧 master
    └ src/search/exact_campaign.py             campaign 持久化 / resume
    └ src/search/exact_parallel_scheduler.py   多进程并行波次
```

## 去哪读
- cut family 实现 → `src/cuts/`(各 family + oracle);对应测试 → `src/tests/cuts/`
- 规则 / 配方 / 目标真值 → `rules/canonical_rules.json`
- 冻结输入工件 → `data/preprocessed/`(candidate_placements / mandatory_exact_instances / generic_io_requirements)
