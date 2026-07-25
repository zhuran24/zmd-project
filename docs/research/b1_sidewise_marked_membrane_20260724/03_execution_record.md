# `22×54` 分边 marked-membrane 轻量阶段执行记录

| 项目 | 当前值 |
|---|---|
| 文档性质 | 执行史料 |
| 截止日期 | `2026-07-24` |
| 终态 | **PAUSE_FOR_USER_GAME_END** |
| authority run | `.artifacts/track_b_b1_sidewise_marked_membrane_20260724/run-20260723T155052Z-SMM1/` |

## 权威盘点

原 Track B root 的 detached formal receipt 使用固定 Python 3.13 做完整只读
重放，得到：

```json
{
  "claim": "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas",
  "production_certified": false,
  "proof_status": "VERIFIED UNSATISFIABLE",
  "replay_status": "VERIFIED",
  "upper_bound_update_authorized": true
}
```

原 root 未被修改。successor 以 detached HEAD
`398f8725c770f3c36408adebe9448a890ed886fe` 创建，并只复用三个已验收的
tracked diff：secret-scan timeout scale 及其测试、R1 proof runner 的磁盘门
测试修正。

## 轻量实现

本阶段建立：

- primary fixture DP；
- independent fixture brute-force checker；
- core-face exclusivity 与 endpoint/capacity fixtures；
- threshold、closed-schema、resource cap、symlink 与 no-overwrite canaries；
- authority bootstrap 与不可变游戏暂停记录；
- 当前状态、数学草案和模型合同。

## 验收记录

以下验收限定为离线小型 fixture 与静态检查：

- 新研究测试：`12 passed in 0.03s`；
- 新研究测试加 secret-scan timeout 聚焦项：
  `14 passed, 2 deselected in 0.06s`；
- R1 formal disk preflight 聚焦项：
  `1 passed, 6 deselected in 5.13s`；
- primary/independent core fixture 均得到 checked maximum `6`；
- strict CLI 返回 exit 3、状态 `PAUSE_FOR_USER_GAME_END`，未执行 optimizer；
- bootstrap 只读 dry-run：
  `AUTHORITY_REPLAY_PASS`、上游 `VERIFIED`、13 个 owned source records、
  `U=(1188,22)`、`L=absent`；
- `py_compile`：通过；
- Ruff check：通过；
- Ruff format check：六个 task/overlay 文件均已格式化；
- `git diff --check`：通过。

`src/tests/test_r1_upper_bound_pb_v1.py` 保持与原 authority root 的已验收字节
完全一致，因此只进入 Ruff check，不进行会改变字节的 format rewrite。

## 未运行项

截至本记录日期，明确未运行：

- strict-instance side-contact optimizer；
- strict 主复算或独立复算；
- geometry adversarial verdict；
- OPB encoder/build/translation；
- RoundingSat、VeriPB 或其他 solver；
- systemd resource worker；
- `scripts/preflight_gate.py --full`。

因此当前结果不建立新的几何必要条件或上界，账本保持
`U=(1188,22)`、`L=absent`。

## 恢复

恢复只认 authority run 内 `PAUSE_FOR_USER_GAME_END.json`。收到用户明确的
游戏结束授权后，先重新核对 bootstrap authority 与原 formal receipt，再开始
完整 strict 复算；不得把合成 fixture PASS 当成 geometry admission。
