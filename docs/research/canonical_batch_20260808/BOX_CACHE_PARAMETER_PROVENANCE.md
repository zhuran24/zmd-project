# 协议箱缓存参数 provenance 存档（canonical 08-08 批）

> 本文是 `rules/canonical_rules.json` →
> `semantics.protocol_storage_box_wireless.slot_count_clause.cache_parameters.provenance`
> 指向的归档件。canonical 条款只放结论与证据等级，链条与逐字源码摆在这里。
>
> 立档缘由：08-08 freeze-ritual 批把 **fill-first 明文**与**单槽容量 50** 两个参数首次写进冻结件。
> 在此之前它们只活在推导史里，而 `26_rules_handbook.md` §4.1 的箱堵塞不可达账**两本都压在它们身上**
> ——不连 provenance 一起入册，就是把未入册参数偷偷写进冻结件
> （记忆卡 `classification-labels-hide-parameters` 点名的「标签藏参数」）。

---

## 1. 可入档条目（份6 盲对勘席原件，逐字转录）

出处：`.artifacts/gpt_pro_review_batch_20260807/verdict/fen6/CROSSCHECK_6S.md` 深挖 1 ②
（同书 N5 行另记「逐字核对，6 组每组恰一个 50」）。

```
条目：protocol_storage_box 单槽容量 = 50，共 6 组
出处：IndustrialPlanner（上游模拟器）src/registry/entity-definition.ts:835-866
      createEntityDefinition({ id: "storager_1", … storageSlotGroups: [
        createStorageSlotGroup("storage_slot_1", ItemDomainFlag.Solid,
                               createSlots("slot", [50], ItemDomainFlag.Solid)),
        … 同构重复至 "storage_slot_6" … ] })
      createSlots(prefix, capacities, …) 逐 capacity 造一个槽（:517-526），
      故 [50] = 恰一个容量 50 的槽；6 组 × 1 槽 × 50 = 静态本地容量 300。
证据等级：上游模拟器**规则层**源码（非游戏客户端）。按权威序
      owner 游戏定谳 > 模拟器规则层 > canonical 文本，此条可作 canonical 的支撑 provenance，
      但仍不能顶替 owner 的游戏实测；它与 owner 2026-07-18 五答、2026-08-06 slot_count_clause 一致。
快照标识：6_sim_rule_derivation/small（= full/IndustrialPlanner_7b946c16 同字节）
核对人/日期：份6 盲对勘席，2026-08-07（逐字目视 + 行号复核）
```

---

## 2. 落位顺序的机制链（三段，逐段有源码）

同书深挖 1 ① 的结论：**严格说是「声明顺序里最早可收的那一组」，不是内容导向的 fill-first。**

1. **一组 = 一节点**。`compileStorageSlotGroups`（`topology-compiler.ts:720-737`）对每个
   `storageSlotGroup` 各调一次 `compileStorageNodeSet`；箱的 6 组因同时有输入和输出绑定而各拆成
   input-view / output-view 两个节点（`:754-803`），共 12 节点——与 `entity-definition.ts:805`
   的注释「编译节点：12 个」一致。
2. **一个端口 × 6 个绑定节点 = 6 条边**。`compilePhysicalConnections` 找到「上游带 → 箱 in_s_k」
   这条物理连接后，`topology-compiler.ts:250-280` 对
   `sourcePort.boundNodeIds × targetPort.boundNodeIds` 做双重循环建边；箱的输入口绑定了全部 6 组，
   于是产生 6 条边，**push 顺序即槽组声明顺序**。
3. **逐边试，失败就试下一条**。`stage-3:300-345` 的输出边循环对每条边独立调
   `selectAcceptedSourceForEdge` → `findInputSlotForItem(node=该组)`；某条边失败只 `continue`，不中断。

**回归测试钉死**：`storage-multi-slot-routing.test.ts:176-188`——两种商品进箱，断言必落在
`storage_slot_1` 和 `storage_slot_2`，直连带与相邻分流器两种上游都测。

### 与 owner 定谳的关系（canonical 条款按这个口径写）

owner 2026-08-06 晚定谳两半：**同种商品可占多组**（「当然是会的」）＋**满格后开新格 = fill-first**。
两半在模拟器里都成立；模拟器给出的更精确机制是「6 个独立单槽组上取最早可收者」。

- 日常行为**看起来**就是 fill-first：组从前往后填、也从前往后排空（stage-3 锚点按 `groupOrder` 升序、
  10 s 提交一次清空全部组），所以「已开的同种组」总是排在空组前面。
- 字面 fill-first 的反例存在但**要靠周期内的空洞**才成立：若 1 号组空、3 号组装着未满的 X，
  来一件 X 会落进 **1 号组**（空槽分支先命中），于是 X 同时占两组。这不违反组内互斥
  （互斥只在同一组内生效）。**在一个 10 s 冲刷周期内两种读法重合**——冲刷把全部组一起清空，
  之后按声明顺序重填，早于某已定型组的空组不会出现。

⇒ canonical `cache_parameters` 的写法：**owner 定谳作条款主体**，模拟器机制作
`Simulator rule-layer precision:` 补充，并写明周期内重合；`evidence_grade` 再声明一次
「模拟器行只是佐证，永不能顶替 owner 游戏定谳」。**这不是对 owner 裁决的修正，是同一结论的机制细化**
（记忆卡 `owner-testimony-is-game-authority`：owner 口述 = 游戏定谳级，不得因「只是口述」降级）。

---

## 3. 这两个参数在本批承重的地方（改一个字要回头看的清单）

| 承重点 | 依赖哪个参数 |
|---|---|
| `slot_count_clause.statement` 的逐次到货接收不变量 | 容量 50（「occupied ≠ full」这句话的全部内容） |
| `slot_count_clause.blocking_reachability_note` (a) 格数账 | 落位顺序 + 容量 50 |
| 同上 (b) 件数账 | 容量 50（「≪ 缓存总量」那一步） |
| `mixed_commodity_flow.terminal_clause` 的**实例级 discharge 注** | 两者都要（15 件 / 300 件 / 单槽 50 / 6 组） |
| `26_rules_handbook.md` §4.1 两本账 | 两者都要（本批前它们标着「前提尚未入册」） |

---

## 4. 仍然欠的一步（不挡本批）

份6 对勘书原话：单槽容量 50 的条目「**仍待 owner 游戏瞥一眼定级**」。
本批按模拟器规则层等级入册，`evidence_grade` 已如实写明它不是 owner 游戏定谳级。
若 owner 将来在游戏里实测确认，把 `evidence_grade` 升级即可，**结论与数字预期不变**
（模拟器规则层与 owner 2026-07-18 五答、2026-08-06 定谳三方已一致）。
