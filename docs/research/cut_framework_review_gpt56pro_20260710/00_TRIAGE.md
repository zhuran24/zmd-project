# GPT-5.6 Pro cut framework 复审 triage（2026-07-10 主会话验尸）

> 包来源：owner 用 5.6 Pro 重跑 07-09 的 cut framework 审查（同题材同快照 88f65a5 附近；
> 5.5 Pro 那轮产出 = 硬化批 c7cd6a0）。本 triage = 三个可复现反例在当前 HEAD 的实测定性。

## 反例实测（当前 HEAD，含 c7cd6a0+批 1A-1C）

| 发现 | 快照上 | 当前 HEAD | 定性 |
|---|---|---|---|
| I-1 integrity bypass（改 cert 注入 capacity=0） | `attached: 1`（bypass 成功） | **`attached: 0`（被拦）** | 5.5 已抓、c7cd6a0 已修（接线层返回值 fail-closed）；5.6 独立重发现同一 P0。边际价值=patch 0001 的深化建议（scope 先 gate + Step 8 二次完整性检查） |
| **I-2 ghost w/h 反置**（BState 构造 `(x,y,ghost_h,ghost_w)`） | 反置 | **仍反置（复现）** | **真正新发现，未修**。square ghost 测试全绿掩盖。attach 通电后影响 cut 的 ghost scope 判定（错误 HOLD/ATTACH→可能伤 soundness），当前 certified 下 attach 禁用故无现链风险 |
| **I-3 artifact scope 空删仍 ATTACH**（Step 6 只查 cut 自报 key） | ATTACH | **仍 ATTACH（复现）** | **真正新发现，未修**。scope 依赖完备性由 cut 自报=可自删；patch 0003 改 schema v1 全 map 严格相等 |

## 处置拍板（主会话，2026-07-10）

1. **I-2/I-3 修复批立项**：attach 通电（M3/F 族接线）前硬门；patch 0002/0003 是现成起点但按纪律自审重写+完整流程（src/cuts/lifecycle.py 在 close-kernel 钉面 → reseal+慢 lane）。**排批 1 完成后**（certified 下 attach 禁用，不阻塞批 1）。
2. RFC-001（typed proof 单一真相）/RFC-002（F5 独立 verifier，呼应 A-4 共同失效批判）/RFC-003（model epoch ledger，呼应 A-6 状态机模型层不闭环）= P1.3 attach 线设计输入，通电前评估采纳度。
3. 5.6 复审对 attach 通电的三硬门建议（原子封口/F5 独立/ledger+dedup+epoch）并入通电 checklist。
