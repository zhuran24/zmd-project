# SMM3 authority recovery 执行记录

| 项目 | 记录值 |
|---|---|
| 截止日期 | `2026-07-24` |
| 文档性质 | 不可变 run 的执行史料与当前判读 |
| 当前判读 | `FORMAL_AUTHORITY_INCOMPLETE` |
| 当前权威 run | `run-20260723T192209Z-SMM3-a003` |
| 固定 HEAD | `398f8725c770f3c36408adebe9448a890ed886fe` |
| 账本 | `U=(1188,22)`，`L=absent` |
| claim 层级 | research-only；不建立 production `CERTIFIED` |

本文件把历史尝试与当前判读分开。所有 `.artifacts` run 均保持 no-overwrite；
失败工件未被覆盖、补写或重新分类。

## 1. 历史 run

### 1.1 Bootstrap `a001`

```text
run-20260723T191600Z-SMM3-a001
status = FORMAL_AUTHORITY_INCOMPLETE
stage  = PRE_RUN_MANAGER_BOOT_AUTHORITY
```

bootstrap 收到相对 run path 后，在 canonical root 检查处失败。没有 authority
package、synthetic unit 或 formal selection。失败工件：

```text
bootstrap-failure-a001.json
size   = 672 B
sha256 = a786f60c4c04e12f6a2c242d9cbafe0cb7cc6ce39d096ef9614075e1d5d8eae4
```

### 1.2 Authority `a002`

```text
run-20260723T191700Z-SMM3-a002
authority SHA-256
  = 8883866a00db8f32ccd5c6a538a4a8db87de671b071b3fdfa29e0de3084251b7
```

q-success 完成真实 unit 生命周期，但 detached verifier 把 successful unit
在 `stop` 后已被 systemd 261 卸载、因而 `reset-failed` 返回
`Unit ... not loaded` 的规范结果误判为失败。失败 receipt：

```text
synthetic-success-a001/detached-verification.json
size   = 375 B
sha256 = d7dd3de89e38dbf44895412119a7501e0b713603e238096d0f7ed98e62b5f8ac
```

该 run 没有 formal admission 或 formal selection。a003 authority 固定的
verifier 合同只接受 exit 0，或 C-locale 下逐字匹配的 already-unloaded
exit 1，并要求后续独立 `LoadState=not-found`；其他非零结果仍拒绝。a003
固定的 verifier SHA-256 是
`d8311acabee3d31bad54fe08161f620314ac9656184bb86c703f7c0db3670a15`。

## 2. 当前权威 run `a003`

本节保存原始历史 argv，固定工作目录为：

```text
/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-sidewise-membrane-20260724
```

相同输出路径均已存在且受 no-overwrite 保护，因此这些 argv 是执行史料，不是
可直接复制重跑的 reproduction 命令。

### 2.1 Pre-run authority

执行命令：

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/run_smm3_authority_recovery_v1.py \
  --bootstrap \
  --run-dir .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003 \
  --run-nonce smm3-20260723T192209Z-a003
```

结果：exit 0，`PRE_RUN_AUTHORITY_PASS`。

```text
authority.json SHA-256
  = 4bfa5711c4f9214e7cb6ad1cd0dc5cb647667f5ced42ebf8d4ea786d3e4833e9
package_id
  = ba23501e7af6adb7dbc941065b872e6fcb8c0350ad49a01ef222bde22cf60cae
```

authority 固定了 HEAD、dirty snapshot、SMM2 上游、strict/PB/translation
输入、全部执行工具、manager/boot epoch 和 `35/39/16 GiB` 资源合同。

### 2.2 q-success

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/run_smm3_two_stage_attempt_v1.py \
  --authority .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/authority-a001/authority.json \
  --attempt-dir .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/synthetic-success-a001 \
  --attempt synthetic-success-a001 \
  --purpose synthetic_success \
  --unit b1-smm3-a003-q-success.service
```

结果：exit 0，detached `PASS`。

### 2.3 q-postseal-fail

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/run_smm3_two_stage_attempt_v1.py \
  --authority .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/authority-a001/authority.json \
  --attempt-dir .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/synthetic-postseal-fail-a001 \
  --attempt synthetic-postseal-fail-a001 \
  --purpose synthetic_postseal_failure \
  --unit b1-smm3-a003-q-postseal-fail.service
```

结果：exit 0，detached `PASS`；payload exit 7 被 keeper 与 unit terminal
保留，没有被 SEAL 掩盖。

### 2.4 Formal admission

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/run_smm3_two_stage_attempt_v1.py \
  --admit-formal \
  --authority .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/authority-a001/authority.json \
  --synthetic-success .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/synthetic-success-a001/detached-verification.json \
  --synthetic-postseal-failure .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/synthetic-postseal-fail-a001/detached-verification.json \
  --output .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/formal-admission-a001.json
```

结果：exit 0，`FORMAL_ADMISSION_PASS`。formal 前可用空间为
`32,350,146,560 B`，高于固定门槛 `15,737,418,240 B`；未发现活动的
RoundingSat、VeriPB 或 formal payload。

### 2.5 唯一 formal `a002`

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/run_smm3_two_stage_attempt_v1.py \
  --authority .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/authority-a001/authority.json \
  --attempt-dir .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/formal-attempt-a002 \
  --attempt a002 \
  --purpose formal \
  --unit b1-smm3-a003-formal-a002.service \
  --formal-admission .artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/run-20260723T192209Z-SMM3-a003/formal-admission-a001.json
```

结果：exit 2，`FORMAL_AUTHORITY_INCOMPLETE`。selection 已创建并消费 attempt。
payload 的不可变 wait receipt 保存 exit 2 与 `seal_written=false`。事后
只读 live journal 观察到：

```text
SMM3 selection semantics or argv mismatch
```

该 journal 文本没有进入 no-overwrite run，只是诊断线索。不可变工件直接建立
payload exit 2、completion seal 缺失与 attempt failure。固定 selection 与
payload 源码的只读静态核对显示一个独立充分的失败原因：selection authority
identity 与 payload 重建 identity 的字段集合不同，但代码要求整个 JSON
对象相等。该失败位于任何 solver 调用之前。

本 run 不重试、不补写 `internal_formal_receipt.json`，也不把事后 live unit
absence 当作 terminal authority。

## 3. 当前终态

```text
status = FORMAL_AUTHORITY_INCOMPLETE
formal attempt = a002_consumed_no_retry
RoundingSat invoked = false
VeriPB invoked = false
proof created = false
upper_bound_update_authorized = false
U = (1188,22)
L = absent
production CERTIFIED = false
NEXT_REQUIRED_TASK = CUTS_GATE1_V4_AUTHORITY_COMPLETION
```

任何未来修复都不得改变本节列出的 run 字节，也不得在 SMM3 内追加第二个
formal attempt。

## 4. 终态验收

聚焦验收：

```text
pytest:
  77 passed
py_compile:
  PASS
Ruff check:
  PASS
Ruff format --check:
  PASS
git diff --check:
  PASS
```

固定 Python full preflight：

```bash
PREFLIGHT_TIMEOUT_SCALE=12 \
  /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  scripts/preflight_gate.py --full
```

结果：

```text
pytest = 4680 passed, 74 skipped
preflight = PASSED
statistics = 19 passed
exit code = 0
```

终态 seal 与只读 authority replay：

```text
authority.json: OK
authority SHA-256
  = 4bfa5711c4f9214e7cb6ad1cd0dc5cb647667f5ced42ebf8d4ea786d3e4833e9
manager/boot epoch replay
  = PASS
manager executable SHA-256
  = de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953
```

验收没有启动新的 solver、formal attempt 或 cuts 工作。
