# diff_fuzz — certified 路径差分对拍工具包 (验证加固 tier ②)

机械验证层: 随机小实例 + **独立朴素验证器**对拍 CP-SAT certified 路径, 不一致 = 必有 bug。不依赖任何 AI/reviewer 能力, 是审查(tier ③)的能力上限兜底。本地运行零外发。

## 设计原则

1. **零共享代码路径**: 验证器自重导几何约定 (port front / occupied cells / coverage), 用裸 BFS/集合代数复核, 绝不 import 被测的 guard/interval/table 逻辑——否则被测 bug 会在验证器里自我豁免 (同构盲区)。
2. **self-test 必抓案例**: 每个验证器自带已知 bug 形态的判别力自证 (A-1 dead-end / B-01 重叠 / 容量超载), 验证器先证明自己能抓再上岗。
3. **reverse 方向 (抓 false-INFEASIBLE) 的方法论坑**: 需要完整可行性 oracle, 但 exact master 的核心约束 (ghost 空矩形) 独立复现 ≈ 重写半个 master。解法 = **嫌疑 witness 缩成 pinned pool 重喂被测 solver 二次裁决**: 仅 pinned 仍 FEASIBLE 才计真 over-cut (solver 自相矛盾), pinned INFEASIBLE = 验证器缺约束的假阳性, 自动过滤并计入 `reverse_filtered`。
4. mismatch ≠ 立即定罪: 先用 `--inspect` 复现单例, 判「真 bug vs 验证器不完整」, 再走正式 finding 流程。

## 切片

| 文件 | 被测 | oracle 覆盖 | 已知结果 |
|---|---|---|---|
| `routing_connectivity_diff.py` | `RoutingSubproblem.solve/extract_routes` | 全局 source→sink 连通 + 每 source 必有出路 (A-1 对偶) + cell-layer 容量 + port exact-one | 累计 900 实例 0 不一致 (含 F04-R4 落地后复跑 150) |
| `master_geometry_diff.py` | `MasterPlacementModel` exact 坐标路径 | 正向: no-overlap (真实 footprint) / bounds / 电力覆盖 (coverage∩occupied); 反向: 小实例暴力穷举 + pinned 自裁; **生成器含无线箱形态** (方形无端口单朝向全 anchor, 镜像 post-F-01 协议箱几何, `wireless_mode` ~50% 掺入) | 累计 ~1760 实例 0 不一致 (28 假阳性全滤; 其中无线箱形态 168 实例, seeds 100-105) |

## 用法 (repo 根, `python3.13`)

```powershell
python3.13 cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
python3.13 cc_context/verification/diff_fuzz/routing_connectivity_diff.py --batch 200 --seed 7
python3.13 cc_context/verification/diff_fuzz/master_geometry_diff.py --batch 80 --seed 1
python3.13 cc_context/verification/diff_fuzz/master_geometry_diff.py --seed 1 --inspect 34  # 复现某 reverse 嫌疑
```

exit 0 = 全净; exit 1 = 有 mismatch/异常 (输出前 20 条)。

## 坑备忘

- routing 的 sink-front 状态约定是 `flow_out = port.dir` (几何上"背对" port), 真路径必须绕到 front 格另一侧进入; 独立实现别按直觉几何想当然 (踩过)。
- `defaultdict.get(k)` 无默认值返回 None——遍历邻接表用 `.get(k, ())`。
- AI Safety Contract: 本工具只读被测对象 + 自建实例, 不写 checkpoints/solutions/blueprints, 不碰证明源。

## 待做

- binding 建模忠实度 oracle (难点: binding 语义本身要独立重述)。
- ~~preprocess wireless 修复落地后, 按新候选几何重跑全部切片 + 把无线箱实例形态加进 master 切片生成器~~ ✅ 2026-06-12 (wireless_mode 形态 + seeds 100-105 共 360 实例 + routing 复跑 150, 全 0 不一致)。
