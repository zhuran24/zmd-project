# P1.2 supervisor 重做 — 方向草案（待 owner 拍方向）

> 状态：草案，回应 2026-06-23 第 5 轮外审（2 独立 reviewer，~11 BLOCK，capsule 根治未闭）。
> 本文只定**方向**；方向定了再出详细设计 → Codex 实现 → Opus 审 → 外审。

## 1. capsule 为什么没闭根（一句话）

**信任根放错了进程。** 现在「这个结果 publishable / CERTIFIED」这个裁决，是在**大求解进程（producer）内部**做的——它调模块全局 `_invoke_isolated_capsule` / `_invoke_isolated_replay`，然后只检查返回的 mapping 字段自洽。

外审证明：**同进程把这俩函数一换**（monkeypatch），伪造体拿到 nonce 原样回显 + 拼个 FEASIBLE/INFEASIBLE，就 mint `publishable=True`（或把真可行候选投影成 INFEASIBLE），**不启动子进程、不跑 binding/routing、不改任何文件**。nonce 只证「应答看过请求」（防重放），**不证「应答来自真 verifier」**。

→ capsule 把可伪造性从「造 verdict 对象」**平移**到「造 response mapping」，根没动。隔离子进程是真的，但**决定要不要信它的那一方（父进程）本身可在进程内被绕过**，所以隔离等于白做。

## 2. 修复原则：**把信任根从「整个求解进程」缩到「最小可信 supervisor」**

不可能没有信任根——总得有**某段代码**被信任去「忠实地跑验证 + 发布」。当前信任根 = 整个 producer 进程（巨大、进程内可变、可 monkeypatch）= 不可审、不可信。

目标：把信任根缩小到一段**最小、可人审、hash 钉死**的 supervisor 代码。producer 只产候选、**不自证**；supervisor 独立裁决发布。其余一切（求解器、verifier、checker）= **verified-not-trusted**（supervisor 在信任前先核 hash）。

> 这是「信任洋葱」的下一层，也是两个 reviewer 的头号必修一致点。

## 3. 架构（方向）

```
┌─ 最小可信 supervisor（新，小，= 声明的 TCB）────────────────┐
│ 0. 自举完整性：import 任何项目代码【之前】，先核：          │
│    - 将执行的全部源 + package initializer 的字节（机器推导的 │
│      authority-transitive import closure，不是手列四文件）   │
│    - 拒绝 package-shadow（目录 package 遮蔽已哈希 .py）、     │
│      拒绝项目根未哈希 package、绑 checked-root==executed-root │
│    - 解释器身份（sys.executable 固定 + 子进程 -I -B -X，沿用 │
│      PYC 修；site/.pth/sitecustomize 启动面也要堵）          │
│ 1. supervisor 自己生成 nonce（producer 拿不到生成权）        │
│ 2. supervisor 自己起隔离 verifier child（不经 producer 的    │
│    可替换 _invoke_*；spawn 代码在 TCB 内）                   │
│ 3. child read-once 读 campaign 权威字节（规范路径+预期摘要）、│
│    自己解析 candidates/final_result/proofs，验确切 stored    │
│    (R*,π*) 字节 —— 【禁止 producer 覆盖】(删 capsule:265-266)│
│ 4. supervisor 校验 child 应答（nonce + 摘要 + 来源在 TCB 内）│
│ 5. supervisor 直接执行 publication（producer 无发布权）      │
└──────────────────────────────────────────────────────────┘
        ↑ producer（大求解进程）只把候选+路径交上来，不自证
```

**关键差别**：现在「父进程」= 大 producer（不可信）；改后「编排+裁决方」= 最小 supervisor（小、可审、钉死）。monkeypatch `_invoke_*` 要想得逞，得改 supervisor 源——而它在硬 floor + 人审 TCB 边界，且小到能审。可伪造性不再「平移」，因为编排方本身是 TCB。

## 4. 逐 BLOCK 闭合映射

| 外审 BLOCK | 闭法 |
|---|---|
| **应答无来源认证**（BLOCK-1/2/3，LIVE）| 编排+裁决移进最小 supervisor；producer 无发布权、不调可替换 `_invoke_*` |
| **stored-byte 未绑**（BLOCK-D）| child read-once 读权威字节自验，删 producer 覆盖（capsule:265-266）|
| **source-exec-before-digest TOCTOU** | 自举完整性：import **之前**核字节，不是 import 后再哈 |
| **package-shadow / 项目根未哈希 package** | 自举核 import 拓扑：拒目录 package 遮蔽 + 未哈希项目根 package |
| **phase checker / runtime guard 不在 floor** | 纳入机器推导的硬 floor（authority-transitive closure）|
| **checked-root ≠ executed-root** | 绑 checked-root==executed-root |
| **sink inventory 非闭世界** | 扫全部可执行入口 + 拒新未哈希强状态 sink |
| **scanner 假不可达 / late-rebind shadow** | 一旦全部被检查源都在硬 floor，降级为 checker-TCB latent；同时补 reachability/rebinding 判据 |

## 5. 改后声明的最小 TCB（诚实）

- **supervisor 自身源**（小、人审、git/hash 钉死）。
- Python 解释器 + stdlib + ortools C 扩展（`.pyd/.so`）。
- OS / 硬件。

其余（producer 求解器、verifier、checker、所有项目 .py）= verified-not-trusted，supervisor 信任前先核。**这条 TCB 线比现在窄得多、且可审**——这就是「收敛」的实质（不是「审到零发现」，是把不可审的大进程信任换成可审的小 supervisor 信任）。

## 6. 范围 / 风险 / 要 owner 拍的

- **范围**：这是**架构重做**，不是补洞。新建 supervisor 入口 + 自举完整性核验 + 重排 publication 控制流 + floor 机器推导 + child read-once。比 FIX-1~5 任一个都大。
- **风险**：① publication 控制流改动牵涉 outer_search / exact_campaign / certified_surface 的发布链，回归面大（我全量 preflight 兜）；② 自举完整性的 import-closure 推导要准（漏一个传递依赖=留洞）；③ supervisor 越小越好审，但要小到只做编排+裁决、不把求解逻辑也拖进 TCB。
- **要你拍的方向**：
  1. **走 supervisor 重做**（推荐）vs **降级承认 producer 进程=命名 TCB**（= 在 PROJECT_LOCK 把「运行认证发布的进程字节码」显式声明为信任、不再宣称隔离防同进程伪造）。后者省事但 reviewer 已指出 manifest 自称防 monkeypatch、降级=收回那个 claim、且公开面诚实度下降。
  2. supervisor 是**独立进程/入口**，还是**主进程内的最小信任 bootstrap 段**？（前者隔离强、改动大；后者轻、但要证 bootstrap 段不被同进程后续代码污染）
  3. 是否**先只做 CORE（应答来源认证 + stored-byte + 自举完整性）**、tamper-only 一簇（floor 机器推导、sink 闭世界）分二期？

## 7. 不要回退的（两 reviewer 都确认真闭）
F3 own-body、FIX-5 read-once、verifier 内部 witness 一致性、旧 `_fresh_run_marker` 入口 fail-close、四结构源同树静态 floor、五 anchor 不能 data-only 自升、FIX-4 I1、PYC-EXEC-DIGEST 窄洞。supervisor 重做要**叠在这些之上**，不是推倒重来。
