# DOC-ADR-007：有效性事件与显式换代谱系

状态：Accepted
日期：2026-08-11

## 背景

历史材料中的“失败”并不是一种东西。直接坐标反例会推翻命题，owner 语义裁决会替代旧解释，validator 缺陷会使一批 replay 失去可信度，不忠实 fixture 会使实验观察失去识别性，资源条款与参数同时变化会造成错误归因，而修复后的 proof replay 只恢复声明范围内的结果。

若这些情况都只写成 `negative_result`、`historical` 或标题里的“已撤回”，后续 agent 仍然无法回答：旧命题究竟错在哪里、哪些层受影响、是否已有 successor、修复是否完成，以及旧材料还能以什么方式安全引用。单有 `supersedes` 数组也不够，因为它只给出边，不解释换代原因和复用边界。

## 决定

1. claim 增加可选 `validity_profile`，记录：
   - `event_type`：直接反驳、语义替代、作用域修正、实现失效、实验失效、归因更正、路线撤回或修复后重验；
   - `affected_layers`：canonical 语义、模型编码、候选 inventory、validator、solver runtime、实验设计、证明论证、文档或研究策略；
   - `basis`：反例、owner 裁决、事故重放、差异测试、受控实验、独立重算、proof replay 或证据缺口；
   - `reuse_policy`：禁止复用、仅作历史、复用前重验、仅复用方法、在列明前提下不受影响或修复后可用；
   - `repair_state` 与 `temporal_scope`。
2. `status=refuted` 或 `status=superseded` 的 claim 必须有 `validity_profile`。任何含 `supersedes` 边的 successor 也必须解释其有效性事件。
3. `supersedes` 只表示语义替代，不表示证明依赖。被标为 `superseded` 的 claim 必须有至少一条反向 successor 边；successor 不能自身也是 `refuted` 或 `superseded`。
4. `current_after_repair` 只有在 `repair_state=revalidated` 时可用。`revalidation` 必须有 proof replay、独立重算、差异测试或受控实验中的至少一种正向依据。
5. 直接反例、语义收窄与实现/实验失效分开登记。实现修复只恢复声明组件，不能自动恢复整个研究路线；实验 TIMEOUT、预算耗尽或零激活不能冒充反驳。
6. 新增自动投影 `docs/VALIDITY_LEDGER.md`，集中展示有效性事件分布、显式换代图、复用策略、修复状态和所有仍为 current 且引用 validity claim 的语义审阅。完整命题与 evidence 仍留在 CATALOG 与 dossier。
7. 将“失效与修复必须保留方向性”登记为 `DOC-INV-010`。checker 与 schema 负责阻断无原因 refuted/superseded、无 successor 的替代、未重验却标为可用，以及局部修复外推成整条路线恢复。

## 后果

- agent 可以按路径获得一条 claim 的紧凑有效性卡，不必先通读事故报告和后续更正文书。
- 历史证据保留原貌，同时更正、反例和重验通过稳定 ID 接成可查询谱系。
- checker 可以阻断“标题说已替代但没有 successor”、“refuted 没有原因”、“修复未验证却标可用”等漂移。
- profile 不改变 authority。owner、rules、production 与 research 各自的效力仍由 claim 顶层字段和原 authority 源决定。

## 未采用的方案

- **只在标题写 REFUTED / SUPERSEDED**：不可查询，也无法证明 successor 与复用边界完整。
- **把所有事故统一登记为 negative result**：会混淆命题反例、实现 bug、fixture 缺陷和错误归因。
- **静默改写旧报告**：破坏历史证据和认知演化，违反 `DOC-INV-002`。
- **仅保留 supersedes 边**：能看到谁替代谁，却看不到为什么、影响哪一层以及是否已经重验。
