# diff_fuzz — certified 路径差分对拍工具包 (验证加固 tier ②)

机械验证层: 随机小实例 + **独立朴素验证器**对拍 CP-SAT certified 路径, 不一致 = 必有 bug。不依赖任何 AI/reviewer 能力, 是审查(tier ③)的能力上限兜底。本地运行零外发。

## 设计原则

1. **零共享代码路径**: 验证器自重导几何约定 (port front / occupied cells / coverage), 用裸 BFS/集合代数复核, 绝不 import 被测的 guard/interval/table 逻辑——否则被测 bug 会在验证器里自我豁免 (同构盲区)。
2. **self-test 必抓案例**: 每个验证器自带已知 bug 形态的判别力自证 (A-1 dead-end / B-01 重叠 / 容量超载), 验证器先证明自己能抓再上岗。
3. **reverse 方向 (抓 false-INFEASIBLE) 的方法论坑**: 需要完整可行性 oracle, 但 exact master 的核心约束 (ghost 空矩形) 独立复现 ≈ 重写半个 master。解法 = **嫌疑 witness 缩成 pinned pool 重喂被测 solver 二次裁决**: 仅 pinned 仍 FEASIBLE 才计真 over-cut (solver 自相矛盾), pinned INFEASIBLE = 验证器缺约束的假阳性, 自动过滤并计入 `reverse_filtered`。
4. mismatch ≠ 立即定罪: 先用 `--inspect` 复现单例, 判「真 bug vs 验证器不完整」, 再走正式 finding 流程。
5. **同构盲区二次见证**: 当独立验证器的枚举骨架与被测枚举骨架结构相近 (回溯+叉乘是该语义的唯一自然实现) 时, 单靠 set-equality 无法排除「两边共享同一概念性 bug」。解法 = 再加一条**闭式公式**独立计数 (binding 切片用多项式系数 `n!/((n-Σk)!·Πk!)`), 与双方域大小都对一遍——公式是从组合数学独立导出的第三见证, 即便骨架同构也能抓共有的概念 bug。

## 切片

| 文件 | 被测 | oracle 覆盖 | 已知结果 |
|---|---|---|---|
| `routing_connectivity_diff.py` | `RoutingSubproblem.solve/extract_routes` | 全局 source→sink 连通 + 每 source 必有出路 (A-1 对偶) + cell-layer 容量 + port exact-one; **+ pattern-closure**: 每个 route-state 的 (flow_in,flow_out,layer) ∈ 独立推导的 48-pattern 合法集 (belt12+splitter16+merger16 + 4 直桥, 从 specs/03 §3.6.5-3.6.8 + specs/09 §9.3.3 推, 已对照 `_iter_state_patterns` 逐元素相等) + 桥下 L0 必空或直线带; 生成器 multi-sink/multi-source 逼出 splitter/merger, 双商品交叉自然产桥 | 累计 ~1350 实例 0 不一致 (pattern 扩展后 450: seeds 0-2 各 150, 实测每批 belt~2500 / bridge~800 / splitter~65 / merger~65 全类型压到) |
| `master_geometry_diff.py` | `MasterPlacementModel` exact 坐标路径 | 正向: no-overlap (真实 footprint) / bounds / 电力覆盖 (coverage∩occupied); 反向: 小实例暴力穷举 + pinned 自裁; **生成器含无线箱形态** (方形无端口单朝向全 anchor, 镜像 post-F-01 协议箱几何, `wireless_mode` ~50% 掺入) | 累计 ~1760 实例 0 不一致 (28 假阳性全滤; 其中无线箱形态 168 实例, seeds 100-105) |
| `binding_model_diff.py` | `PortBindingModel.build/solve/extract_selection/extract_port_specs` + `port_binding` 枚举 (默认 `routing_context=None` 路径) | [A] 固定操作 pose 级绑定域 set-equality + **多项式闭式计数二次见证** + active_ports 一致性; 可行性精确刻画 (FEASIBLE ⟺ sum(req_out)≤#out_slots ∧ sum(req_in)≤#in_slots ∧ 各 pose 端口格够, 双向无 pinned); [C1] 绑定选择合法 + [C2]/[C3] generic 输出/输入 per-commodity 精确计数 + 单赋; [D] extract_port_specs 重建 (routing_free/virtual 过滤, instance_id 区分). 生成器掺 pose_optional 合成 + shared-namespace (驱动 routing_free 输出过滤) | 累计 ~1210 实例 0 不一致 (加固后 600: seeds 0-4 各 120, pose_optional ~30/批 + shared_ns ~35/批 + 端口不足 expected_errors ~10/批如期 ValueError) |

## 用法 (repo 根, `python3.13`)

```powershell
python3.13 cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
python3.13 cc_context/verification/diff_fuzz/routing_connectivity_diff.py --batch 200 --seed 7
python3.13 cc_context/verification/diff_fuzz/master_geometry_diff.py --batch 80 --seed 1
python3.13 cc_context/verification/diff_fuzz/master_geometry_diff.py --seed 1 --inspect 34  # 复现某 reverse 嫌疑
python3.13 cc_context/verification/diff_fuzz/binding_model_diff.py --self-test
python3.13 cc_context/verification/diff_fuzz/binding_model_diff.py --batch 120 --seed 0
python3.13 cc_context/verification/diff_fuzz/binding_model_diff.py --seed 0 --inspect 7  # 复现单例
```

> 注: 本 checkout 主环境是 `python` (python.org 3.13), `python3.13` 是商店备份; 二者都能跑, README 沿用历史 `python3.13` 写法。

exit 0 = 全净; exit 1 = 有 mismatch/异常 (输出前 20 条)。

## 坑备忘

- routing 的 sink-front 状态约定是 `flow_out = Opp(port.dir)`，即 front 格朝 connector 送料；独立实现别按直觉几何想当然 (踩过)。
- `defaultdict.get(k)` 无默认值返回 None——遍历邻接表用 `.get(k, ())`。
- binding 可行性精确刻画仅在 `EXACT_BINDING_USE_OVERLOAD_SEPARATION` **关** 时成立 (该 env 开启的 hard nogood 会合法地让模型 INFEASIBLE); `run_binding()` 已 fail-fast 守卫这个 env, 别在跑 binding 切片时开它。
- binding 重复物理端口格 (同一侧同 `(x,y,dir)`) 物理退化: 被测按 index 枚举 (两同格→两 pattern), 本验证器按 `(x,y,dir)` 集合语义。生成器 (`_fresh_cells` 全局唯一坐标) 永不产重复格; 万一遇到 (真实 pose) 验证器发 `[NOTE]` 跳过 set 比对而非给错判。
- AI Safety Contract: 本工具只读被测对象 + 自建实例, 不写 checkpoints/solutions/blueprints, 不碰证明源。

## 待做

- ~~binding 建模忠实度 oracle (难点: binding 语义本身要独立重述)~~ ✅ 2026-06-14 (`binding_model_diff.py`; 默认 `routing_context=None` 路径; 4 视角 workflow 对抗式复核后加固: 多项式二次见证破同构盲区 / [C1] 非法绑定+越界自检 / overload-env 守卫 / pose_optional+shared_ns 覆盖 / dup-cell 诚实 NOTE)。
- **binding RAB-SEP `routing_context!=None` 路径** (front-blocked 绑定 pattern 剪枝, 可致 false-INFEASIBLE) 独立切片 —— 需独立重导 port-front-status oracle (重述 occupancy + front 几何), 当前 binding 切片显式不覆盖。
- **routing 实体排斥 + 桥不穿实体 (specs/09 §9.3.1 / §9.3.3.3, HIGH)** —— routing 切片当前用 `RoutingGrid(set(), ...)` 空占用, 整个 solid-obstacle 排斥面 (route-state 不落实体格、桥不跨实体、桥端无缝起降) 完全未压, 是 routing 面**最大真缺口**。下一增量 = generator 植入 occupied cells + RoutingGrid 带非空占用 + 独立查"无 route-state 落实体 / 无桥跨实体"。
- **routing 端口度数精确 = N (N>1) (specs/09 §9.4.1, MED)** —— 当前 generator 只发单度端口 (每 front 一个 spec, N=1 隐含), N≥2 的 `sum(发射)==N` 度数履行未压。(1 格间隔 §9.3.5 由 placement 面负责, SUT 在 routing 侧是 stub, 不属本切片。)
- ~~preprocess wireless 修复落地后, 按新候选几何重跑全部切片 + 把无线箱实例形态加进 master 切片生成器~~ ✅ 2026-06-12 (wireless_mode 形态 + seeds 100-105 共 360 实例 + routing 复跑 150, 全 0 不一致)。
