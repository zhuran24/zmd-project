# W0 一元 lowering 金丝雀协议冻结凭据

> **日期：** 2026-08-16
> **状态：** `READY_FOR_FREEZE_COMMIT`
> **边界：** 本凭据只核对协议包的身份、自洽和禁止面；不表示 implementation 已存在或实验已运行。

## 冻结文件身份

| 文件 | SHA-256 |
|---|---|
| `00_OWNER_AUTHORIZATION_20260816.md` | `38af63394b8954751080f31283b17932f968e8b33431df9743a430f91376bb82` |
| `01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md` | 以本次提交中的字节为准；implementation 将钉死 freeze commit，而非复制一份易漂移 hash |
| `02_ENDPOINT_METRICS_PROTOCOL_V1.md` | `ee55147e2791b5c53181719d2f7ddcc68e59d31a627d1645f9ec21d250e7b2f7` |
| `03_ENDPOINT_METRICS_PROTOCOL_V1.json` | 以本次提交中的字节为准；endpoint checker 将钉死 freeze commit |

## 预提交检查

- machine endpoint protocol JSON 可严格解析，登记 11 个 sensitivity tests；
- `docctl intake --changed` 正确分类新增 research 文档；
- `docctl doctor` 为 PASS；
- worktree diff check 无新增空白错误；
- tracked `src/`、`scripts/`、规则、认证和发布面零修改；
- 通用 D3/D4 保持冻结；
- implementation、run 与报告尚未开始。

隔离 worktree 中 `check_knowledge_docs.py` 只报告既有 CATALOG 仓外绝对路径在 worktree 深度下的相对链接重算差异；该生成器位置效应不属于本协议改动，不写入 freeze commit。协议落回活树后必须在活树执行最终 intake／doctor／knowledge 三检。
