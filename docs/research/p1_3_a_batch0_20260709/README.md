# A 批 0：C6 供电编码原型头对头（2026-07-09）

> 上游：M6 诊断（`../p1_3_m6_diagnosis_20260709/07_final_diagnosis.md`）+ A 设计工作流（架构师+对抗审查，主刀 C6/备刀 C1）。
> 原型 = 测量专用 monkeypatch（`c6_encoding_patch.py`），不碰 sealed，结果绝不回流 certified。

## C6 机制

witness 的「证人编号 + AddElement-over-变量数组」→ pairwise `cover_lit[i][j]` 布尔 + 4 条矩形相交不等式挂 enforcement（几何算术照抄 `_add_power_coverage_selected_geometry:5388-5403`，含 `+2+radius-1` 不对称常量）+ `Σ cover_lit ≥ active`。红线（对抗审查）：`cover_lit ≤ pole.active` 必需（inactive 杆坐标钉域角，漏掉=假覆盖）。

## 结果

| 关卡 | witness 基线 | C6 v0 |
|---|---|---|
| 玩具等价性（可解/必死） | — | **PASS**（判决一致） |
| 钉死验证 单核 300s | UNKNOWN，7.2M br，冲突率 0.07% | UNKNOWN，12.1K br，**冲突率 10.9%**（传播 traction ~150×，每节点重 ~600×） |
| 自由搜索 w12 1800s（probing1/automatic） | UNKNOWN，4.17M br，453 conflicts | UNKNOWN，3.76M br，**37,113 conflicts（~90×）** |
| 钉死验证 w12 600s（b0_1b） | INFEASIBLE @94.5s（witness 数据）| 见 b0_1b_pinned_c6_w12.json |

## 批 0 中期判读

机制诊断兑现：**「element 传播盲区」假设被证实**——C6 让求解器从蒙眼狂奔（0.07-0.011% 冲突率）变成真实对抗（1-11%）。但 traction 质变未在 300-1800s 预算内转化为判决：节点变重（582,169 个 cover 文字 × 4 不等式）抵消了大部分收益。

C6 v0 = 方向对、力度不够。下一步候选：C6 域剪枝优化（杆域全满使 pair 剪枝无从下手——受限）/ **C1 备刀**（杆侧 pose 布尔化 = 真静态线性形态，B1 的直接对应物，理论上限更高）/ C6+C1 混合。
