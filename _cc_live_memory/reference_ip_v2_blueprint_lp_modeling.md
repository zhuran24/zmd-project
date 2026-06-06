---
name: ip-v2-blueprint-lp-modeling
description: IP v2 蓝图稳态产量 LP 的外部源建模规则 + 已验证蓝图状态
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

`scripts/ip_v2_blueprint_steady_state_lp.py` 的建模规则（2026-05-13 修过 1 个建模 bug 后定稿）:

**外部源 = 只有矿石**, 硬白名单写死:
```python
EXTERNAL_SOURCE_ITEMS = {"item_iron_ore", "item_originium_ore"}
```

**为什么不用启发式判断**:
- 之前用过 "recipe 没产 → 外部源" 的启发式 — 这是反向推断, 脆弱.
- 反例: 未来某天加回收 recipe 能产铁矿, 启发式会把铁矿当内部循环, 但游戏里它**还是从外部送进来的**.
- 外部源是游戏机制硬事实, 不该靠 recipe 反推.

**unloader / storager / loader 不是外部源**, 是基地内部协议网络的 routing 节点:
- 在 IP v2 里, `item_port_unloader_1` (出货口) 从协议网络取物品到传送带
- `item_port_storager_1` (协议储存箱) 是网络内的物流节点
- 之前的 bug 是把所有 unloader 都当外部无限源 → 草支路被白送 60/min → 利用率算成 84.6% 而不是 100%

**已验证蓝图**:
- `~/下载/BP-2026-05-13 08_35_36.blueprint.json` (LP-verified 1156 设备) → LP 算出稳态 18 电池_3 + 12 胶囊_3 / min, 所有 production machine 100% 利用率, 收支守恒. 用户手动恢复的版本, 拓扑正确.
- 2026-05-16 update: 用户 redownload 版 `BP-2026-05-13 08_35_36.blueprint(1).json` (5/16 mtime, 1175 设备) — createdAt 仍 5/13 08:35:36, updatedAt None. 多出 19 设备可能 user 之后又加了 belts. 拓扑核心同, 仍是手调最终版.
- **D step 2 master hint 注入用这个文件** [[d-step2-blueprint-converter-state]]

**关于"过剩"利用率**:
- 上游 capacity ≥ 下游 demand 是合理设计冗余, 不是 bug
- 游戏里 "84.6% 利用率" 不代表 4 台机器闲着, 而是 "26 台机器各自有 15% 时间 stall on output full" — output buffer 满了就停一下等下游清
- 健康状态, 不该追求 100%

**采种机是 2:1 倍增器** (重要游戏机制):
- `r_seedcol_moss_*`: 1 草 → 2 种子 (不是 1:1)
- 1 采种机 + 2 种植机 cycle 形成 "净流出 1 草/cycle 给下游" 的倍增器
- 算物料平衡时漏这个会得错误结论 (例如认为 13 采种 + 26 种植 不够支撑 13 粉碎机, 实际刚好)

**配套工具**:
- 静态连通性 validator: `scripts/ip_v2_blueprint_validator.py` (检查传送带类型不匹配 + 未连通端口)
- 可视化标注 (⚠️ 仅早期 Linux host 工作树存在, **从未进 git**, Windows clone 缺此脚本, 需用时重写): `scripts/annotate_blueprint_issues.py` (在 FINAL.jpg 上画红框标注 issue 位置, 用 1 cell ≈ 127.2 px, origin (983, 732))
- 设备 spec: `/tmp/ip_v2_device_specs.json` (从 IP v2 vendored registry 导出)
- `item_port_power_sta_1` (热能池) 自消耗, 不需要接下游 — validator 已修正不再 flag 这类设备
