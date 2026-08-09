# M6 判决实验：钉死布局强制验证（2026-07-09）

## 设计

对抢救出的 3 份 greedy 重建布局（anchor 132/133/134，离线几何验证 0 重叠、占用 3544、洞已留），在当前 6×6 coordinate master 上把全部 266 实例的 x/y/mode + ghost anchor 钉死，**presolve 全关**（绕开 presolve 税——此组合历史上从未试过）纯传播+搜索判定。脚本 `~/m5_runs/m6_replay_forced_validation.py`、`m6b_power_isolation.py`（待归档 linux_tools/）。

## 结果

| 实验 | 配置 | 结果 |
|---|---|---|
| M6（全模型钉死） | presolve-off/fixed/单核/300s ×3 anchor | 3/3 UNKNOWN——7.2M branches、冲突率 0.07%：**钉死布局后 solver 仍在 763 个自由电线杆槽位空间蒙眼狂奔** |
| M6b-A（供电族关掉重建 core，钉死） | 同上/120s ×3 | **3/3 OPTIMAL，2.6-5.3 秒**——几何/ghost/打包/端口/对称全体无辜 |
| M6b-B（供电保留，钉死，火力全开） | presolve-off/automatic/w12/600s，anchor 132 | **INFEASIBLE @94.5s**（1.36M branches）——两天来第一个非 UNKNOWN 判决 |

## 判决

1. **首解之墙 = 供电补全（pole completion）**，证据无混杂：同一布局，无供电 5 秒 OPTIMAL、有供电 94 秒 INFEASIBLE。
2. **greedy 重建布局是供电不可行的**（至少 anchor 132）——重建只管几何，72% 占用的密集打包挤死了电线杆的覆盖格局。q2a 的原始直觉（曾被对抗复核正确降级为「无区分性证据」）就此实锤。
3. **机制**：master 冷搜索需要同时打包+留杆位，供电编码（witness 式+763 槽）传播反推力≈0 → 百万分支 0.1% 冲突率的「无引导溺水」形态；火力足够时供电子模型可判定（94s INFEASIBLE），问题是与打包耦合时无引导。
4. 修复方向（生产工作，呈 owner）：power-aware 布局构造（重建时预留杆位）/供电编码改造（提高传播强度）/两阶段分解。与 archaeology 路的 B1 证据呼应（pose-bool 编码把供电做成 x≤Σcoverers 的逐 pose 线性式，53s OPTIMAL——供电编码形态正是两代表示的关键差异之一）。

## 下一发

C-1A 单 anchor 全模型（4225 析取→1，供电保留）：出解=anchor 多重性×供电联合墙（修复=anchor 分片，天然适配 EXACT_PARALLEL_PROCESSES）；UNKNOWN=供电单独即墙；INFEASIBLE=该 anchor 真无解（采样多 anchor 判全局）。
