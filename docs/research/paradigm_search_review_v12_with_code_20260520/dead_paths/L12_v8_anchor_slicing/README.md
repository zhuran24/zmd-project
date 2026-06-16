# L12 — v8 Anchor Slicing (GPT v8 提出)

## 当时项目情况

L1-L10 全死 + L11 (牺牲严格性) 用户拒绝. 项目通过 GPT review 包 v7 请求新 paradigm.

## 为什么走这条路

GPT v8 plan: ghost-anchor disjunctive decomposition env-gated 拆 N anchor. 关注**"anchor choice 撑开搜索树"假设** — master 在 ghost rect 形状外搜 anchor location 是搜索树主体, lock anchor 后剪掉搜索树外层.

## 实验过程

GPT 给 patch 9.4 MB v8 zip. 实测:
- SHA256 校验 ✓
- patch clean apply 0 hunk fuzz
- 2211 pytest passed / 0 failed (4 新测试)
- 单 anchor (22,28) 27×15 + community hint + MAX_ANCHORS=5 + 30 min budget 实测

## 实验结果

| 维度 | Full overlay | Single slice @(22,28) | Δ |
|---|---|---|---|
| build wall | 53.7s | 4.5s | **-92%** |
| proto vars | 19406 | 16943 | -13% |
| proto cons | 56452 | 38578 | -32% |
| build RAM | 1.86 GiB | 0.52 GiB | -72% |

但 **solve 阶段实测打死**: 307s anchor (0,0) UNKNOWN, branches 5,510,114 — 真在搜但搜不动. 跟 trial7 1h UNKNOWN 同 quality.

## 经验跟教训 (含瓶颈理解更新)

- **认知错误**: anchor choice **不是**搜索树主体. 锁 anchor 后 master 仍有 385 万 mandatory pose literal 等待搜索. 真搜索主体是 266 facility 几何摆放.
- **GPT 错估类型: 算法错估**. 优化的是 build 不是 solve, ROI 实质负.
- **瓶颈理解更新**: master.solve 难度的主体来自 facility placement 自身, 不在 anchor 选择. v3 (5/13) + v8 (5/16) 都是同类错估 — "关注 build 没量 solve".

## code/

- `code/` 含 GPT v8 patch + smoke trial + 实测 log
- 详 `code/README.md` (实际归档自 docs/research/v8_anchor_slicing_smoke_20260516/)
