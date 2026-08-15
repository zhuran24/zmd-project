# DOC-ADR-018：非破坏性真实仓库落地与漂移语义迁移

状态：Accepted
日期：2026-08-14

## 背景

供应快照把真实仓库中的大量 untracked artifact 当成了 tracked 内容。真实共享工作区还在快照后继续修改 `CLAUDE.md`、旧 roadmap 和旧 dashboard。累计补丁在供应树中的绿色结果不能证明它能安全覆盖真实仓库。

旧应用脚本通过整树 hash 锁定沙盒基线，并在失败时执行 `git reset --hard` 与 `git clean`。在共享工作区中，这会删除 untracked agent 指令和数 GB evidence。简单 `--exclude` 冲突文件同样不充分，因为它只能越过 hunk，不能证明快照后新增的 owner 记录和欠账已经迁移。

## 决定

建立 manifest-owned 的落地协议和独立 runner：

1. 每次落地动态执行路径级 `git apply --check`，不使用固定冲突清单；
2. 已登记漂移保存仓外计划快照、落地时点仓内历史归档和 SHA-256；
3. 未登记漂移 fail closed，必须通过 framework 变更补充迁移合同；
4. 基础补丁只应用当前仍通过检查的路径，不自动 staging、commit 或 rollback；
5. owner 记录、维护欠账和 agent overlay 通过 typed obligation 与 ACK 迁移；
6. `decisions.jsonl` 与 `docs/项目说明/HISTORY.md` 在迁移期间按字节前缀验证 append-only；
7. package-owned successor 只有在归档和语义迁移通过后才安装；
8. `CLAUDE.md` 保持 workspace overlay，由操作者调和，不由补丁强制覆盖；
9. runner 不含 reset、clean、add-all、commit 或 amend 能力。

## 为什么不是固定三文件排除

冲突集合会随真实仓库继续写入而增长。把当前三条路径写死，只是在下一次漂移前暂时有效。动态测量把“已知迁移合同”与“此次实际冲突”分开：

```text
实际冲突 ⊆ 已登记迁移源  → 可以继续
实际冲突出现未知路径      → 阻断并扩协议
```

这让结构保持 fail closed，同时避免把所有未来文件都预先列入排除面。

## 为什么归档与迁移必须分开

历史归档回答“落地时真实字节是什么”；当前账本和 successor 回答“现在怎样表达这份知识”。直接改写旧页会把两件事混在一起，并失去判断是否遗漏的基线。

ACK 不复制知识正文，只保存迁移坐标和核验要求。具体命题仍由 decision、claim、ROADMAP、HISTORY 或 agent operations 真源承载。

## 后果

正面结果：

- 沙盒和真实仓库拓扑差异不会再通过添加 untracked 工件来掩盖；
- 快照后 owner 记录和欠账不能被静默覆盖；
- 失败不会触发破坏性整树清理；
- 恢复与审计可以依靠计划、归档、ACK 和 receipt 精确重放。

代价：

- 落地多出显式规划、归档和迁移步骤；
- 新类型漂移必须先扩协议和测试；
- 工具只能验证迁移合同，仍需人确认 owner 语义和 workspace overlay 内容。
