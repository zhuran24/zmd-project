# L13 — v10 Witness Preflight (GPT v10 提出)

## 当时项目情况

L12 v8 anchor slicing 死后. GPT 收到 v9 review 包 (含 v8 死亡数据) 后出新 plan.

## 为什么走这条路

GPT v10 plan: **witness-only mandatory-placement preflight**. 算法 sound:
1. 已有 complete mandatory hint
2. 计算 mandatory 占用格
3. 找 compatible ghost anchors (跟 mandatory 不交)
4. clone master + 固定 mandatory + anchor literal == 1
5. clone FEASIBLE → 进 binding/routing
6. fail-closed: INFEASIBLE/UNKNOWN/timeout → 回退 normal master

PROJECT_LOCK 兼容 ✓.

## 实验过程

- SHA256 校验 ✓
- patch clean apply
- 2212 pytest passed (5 新测试)
- 跟 trial7 同 candidate + community hint + slicing on + 30 min budget 实测

## 实验结果

**关键发现**: preflight 在大 candidate 永不 trigger:

| 字段 | 值 |
|---|---|
| complete_hint | True |
| mandatory_hint_occupied_cell_count | **3122 格** (70×70=4900 的 64%) |
| compatible_anchor_count | **0** (target ≥1) |
| reason | `no_compatible_ghost_anchor` |

跑不同 candidate size:

| Ghost (w×h) | compatible / total | 比例 |
|---|---|---|
| 8×8 | 611/3969 | 15.4% |
| 15×15 | 149/3136 | 4.8% |
| 20×15 | 0/2856 | **0.0%** |
| 27×15 | 0/2464 | **0.0%** |

preflight 在 area ≥ 300 大 candidate 上永远 0 compatible anchor. 项目目标是大面积 max_lex, paradigm 对真目标无效.

## 经验跟教训 (含瓶颈理解更新)

- **认知错误**: GPT 假设 "complete 266-facility witness 跟 blueprint align". 实际我们 community blueprint 只 225 mandatory, 缺 41 由 greedy heuristic 填, **greedy 不知道 blueprint 留 27×15 空地, 41 个填进空地区域**. merge 后 mandatory 占用破坏 blueprint 留空.
- **GPT 错估类型: 前提错估** (跟 v8 算法错估不同源).
- **瓶颈理解更新**: 算法 sound 不等于在我们 data 上能 trigger. data ≠ paper 假设的 production data shape.

## code/

- `code/` 含 GPT v10 patch + smoke trial + telemetry
- 详 `code/README.md`
