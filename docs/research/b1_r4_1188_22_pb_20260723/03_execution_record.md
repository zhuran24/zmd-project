# Track B/B1 `(1188,22)` proof-bearing 回归：执行记录

| 文档属性 | 当前值 |
|---|---|
| 文档性质 | 不可变 authority 的执行与验收记录 |
| 证据截止 | `2026-07-23` |
| 当前判读 | `VERIFIED`；`U: (1190,34) -> (1188,22)`；`L: absent` |
| Git identity | branch `codex/track-b-b0-1190-20260721`；HEAD `398f8725c770f3c36408adebe9448a890ed886fe` |
| Build | `build-a001-20260723T091353Z-398f8725` |
| Formal | `formal-a001-20260723T091800Z-398f8725` |

本文隔离执行史料；当前数学结论、信任边界与 authority 摘要以
[`README.md`](README.md) 为入口。

## 固定运行环境

```text
project root:
/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721

Python:
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13

RoundingSat:
/home/zhuran24/tools/roundingsat/build/roundingsat

RoundingSat source:
/home/zhuran24/tools/roundingsat

VeriPB:
/home/zhuran24/.cargo/bin/veripb
```

## Build authority argv

顶层 build argv 的等价可执行命令如下。`BUILD` 是本次实际 no-overwrite 目录；
该目录已经存在，命令仅用于记录，不能在原路径重放。

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -B \
  /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_r4_1188_22_pb_20260723/b1_r4_1188_22_pb_encoder_v1.py \
  build \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --gate-script /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_r4_1188_22_pb_20260723/verify_b1_r4_1188_22_pb_translation_v1.py \
  --output-dir /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725 \
  --proof-limit-bytes 5000000000
```

原始退出码为 0。Builder 输出：

```json
{"attempt":"/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725","build_record_sha256":"4f8124c582d0c4134538abd2574f2f2ebb3fb5eeb56f0aba7fb1d760fc72f886","manifest_sha256":"652a7bdf5bab1488e40fa1bce6eab18e59437f038acef0d7b3f39b197c74771a","status":"PASS"}
```

独立 post-build validator 返回 `build_status=PASS`、`payload_count=11`、
`gate_status=PASS`、20/20 checks、`corpus_errors=[]`，OPB header 为：

```text
* #variable= 2084 #constraint= 2192 #equal= 1 intsize= 64
```

## Formal authority argv

以下是本次真实顶层 argv 的完整可执行形式。`formal a001` 与 persistent
reservation 已存在，禁止再次执行。

```bash
systemd-run --user --wait --collect --pipe \
  --unit=b1-r4-1188-22-formal-a001-20260723T091800Z \
  --working-directory=/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  -p MemoryHigh=37580963840 \
  -p MemoryMax=41875931136 \
  -p MemorySwapMax=17179869184 \
  -p OOMPolicy=continue \
  -p KillMode=control-group \
  -p SendSIGKILL=yes \
  /home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
  /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/docs/research/b1_r4_1188_22_pb_20260723/run_b1_r4_1188_22_pb_toolchain_v1.py \
  --project-root /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721 \
  --opb /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/formula.opb \
  --meta /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/encoder.meta.json \
  --var-map /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/variable_map.json \
  --estimate /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/estimate.json \
  --translation-gate /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/translation_gate.json \
  --build-record /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/build_record.json \
  --build-manifest /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/build-a001-20260723T091353Z-398f8725/SHA256SUMS \
  --roundingsat /home/zhuran24/tools/roundingsat/build/roundingsat \
  --roundingsat-repo /home/zhuran24/tools/roundingsat \
  --veripb /home/zhuran24/.cargo/bin/veripb \
  --output-dir /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725 \
  --solver-time-limit 3600 \
  --solver-wall-timeout 3900 \
  --verifier-wall-timeout 3600 \
  --proof-limit-bytes 5000000000 \
  --min-free-bytes 10737418240 \
  --monitor-interval 1 \
  --expected-systemd-unit b1-r4-1188-22-formal-a001-20260723T091800Z.service \
  --require-cgroup-contract
```

`systemd-run` 底层退出码为 0，unit 结果为 success，service runtime 6.516 s，
CPU time 3.154 s，memory peak 42 MiB，swap 0 B。Runner 的最终 stdout 为：

```json
{"authority_receipt":{"path":".artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/authority_receipt.json","sha256":"0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2","size_bytes":2613},"claim":"machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas","failure_codes":[],"raw_record_claim":"none","record":"/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/toolchain_record.json","verified_result_candidate":"machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"}
```

## 原始 solver/verifier 输出

RoundingSat：

```text
c RoundingSat 2
c branch HEAD
c commit d4edbf7
c Inconsistent input constraint
...
s UNSATISFIABLE
```

其 stdout 为 2,371 B、SHA-256
`fc741e3db09b4297f880d6ebfc24bca9b1b045c0137cca9950d91c41303d01d1`；
stderr 为 0 B。Exit code 为 0，`termination_reason=null`，
`process_group_clean=true`。

VeriPB：

```text
Running VeriPB version 3.0.2
Info: Switched to proof version 2.0 (it is recommended to migrate to proof version 3.0).
s VERIFIED UNSATISFIABLE

c statistic: time total: 0.001375337 s
```

其 stdout 为 183 B、SHA-256
`e99277368076972906e135c4a443a361b6ddbdaa5c596a1118326d6b2776c09f`；
stderr 为 0 B。Exit code 为 0，`termination_reason=null`，
`process_group_clean=true`。

## Detached receipt replay

unit 退出后执行的只读 replay 命令如下：

```bash
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 -B - <<'PY'
from pathlib import Path
import importlib.util
import json
import sys

root = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b0-1190-20260721"
)
build = (
    root
    / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
    / "build-a001-20260723T091353Z-398f8725"
)
formal = (
    root
    / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
    / "formal-a001-20260723T091800Z-398f8725"
)
runner_path = (
    root
    / "docs/research/b1_r4_1188_22_pb_20260723"
    / "run_b1_r4_1188_22_pb_toolchain_v1.py"
)
spec = importlib.util.spec_from_file_location(
    "b1_detached_receipt_replay",
    runner_path,
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
identity = {
    "path": (
        ".artifacts/track_b_b1_r4_1188_22_pb_20260723/"
        "formal-a001-20260723T091800Z-398f8725/"
        "authority_receipt.json"
    ),
    "size_bytes": 2613,
    "sha256": (
        "0b3366a3e1640a13675a28d1408b9b96"
        "ede3a0e6403e71a8f9222f1f44e5b5c2"
    ),
}
result = module._replay_authority_receipt(
    formal,
    (
        root
        / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
        / "formal_attempt_a001.reservation.json"
    ),
    build / "build_record.json",
    build / "SHA256SUMS",
    root,
    identity,
)
print(
    json.dumps(
        {
            "replay_status": result["status"],
            "claim": result["claim"],
            "receipt": result["receipt"],
            "proof_status": result["payload"]["proof_status"],
            "upper_bound_update_authorized": (
                result["payload"]["upper_bound_update_authorized"]
            ),
            "production_certified": (
                result["payload"]["production_certified"]
            ),
        },
        sort_keys=True,
    )
)
PY
```

退出码为 0，结果为：

```json
{"claim":"machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas","production_certified":false,"proof_status":"VERIFIED UNSATISFIABLE","receipt":{"path":".artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/authority_receipt.json","sha256":"0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2","size_bytes":2613},"replay_status":"VERIFIED","upper_bound_update_authorized":true}
```

## 验收记录

终态验收使用以下完整命令：

```bash
PY=/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13

"$PY" -B -m pytest -q \
  src/tests/test_b1_r4_1188_22_pb_v1.py

"$PY" -B -m pytest -q \
  src/tests/test_r3_upper_bound_pb_v1.py \
  src/tests/test_r4_external_brain_handoff_v1.py \
  src/tests/test_r4_response_review_v2.py \
  src/tests/test_r4_response_authority_chain_v2.py \
  src/tests/test_preflight_gate.py \
  src/tests/test_r1_upper_bound_pb_v1.py

"$PY" -m ruff check \
  docs/research/b1_r4_1188_22_pb_20260723/b1_r4_1188_22_pb_encoder_v1.py \
  docs/research/b1_r4_1188_22_pb_20260723/verify_b1_r4_1188_22_pb_translation_v1.py \
  docs/research/b1_r4_1188_22_pb_20260723/run_b1_r4_1188_22_pb_toolchain_v1.py \
  src/tests/test_b1_r4_1188_22_pb_v1.py

"$PY" -m ruff format --check \
  docs/research/b1_r4_1188_22_pb_20260723/b1_r4_1188_22_pb_encoder_v1.py \
  docs/research/b1_r4_1188_22_pb_20260723/verify_b1_r4_1188_22_pb_translation_v1.py \
  docs/research/b1_r4_1188_22_pb_20260723/run_b1_r4_1188_22_pb_toolchain_v1.py \
  src/tests/test_b1_r4_1188_22_pb_v1.py

git diff --check -- \
  docs/research/b1_r4_1188_22_pb_20260723 \
  src/tests/test_b1_r4_1188_22_pb_v1.py

"$PY" -B scripts/check_external_artifacts.py \
  --require candidate_placements
"$PY" -B scripts/check_repo_secrets.py

PREFLIGHT_TIMEOUT_SCALE=12 \
  "$PY" -B scripts/preflight_gate.py --full
```

终态结果为：

```text
pytest -q src/tests/test_b1_r4_1188_22_pb_v1.py
29 passed in 108.87s

related authority/preflight pytest
189 passed in 14.62s

scripts/check_external_artifacts.py --require candidate_placements
external artifact check passed
exit 0

scripts/check_repo_secrets.py
repo secret scan passed: 39786 candidate text paths checked
exit 0

PREFLIGHT_TIMEOUT_SCALE=12 scripts/preflight_gate.py --full
19 passed
pytest: 4864 passed, 74 skipped
exit 0

Ruff check
All checks passed
exit 0

Ruff format --check
4 files already formatted
exit 0

git diff --check
exit 0
```

正式 run 前的同配置 cgroup preflight 还独立返回：

```json
{"a004":"PASS","build":"PASS","cgroup_contract_pass":true,"gate":"PASS","preflight_free_bytes":34007539712,"proof_bound_bytes":536870912,"status":"PASS"}
```

定向测试、相关回归、Ruff check/format、`git diff --check`、full preflight 与
detached receipt replay 均已通过。上述 formal authority 没有因文档验收而改写。

## 不可变与失败边界

Build、formal、persistent reservation、raw manifest、record、proof 与 receipt 均
为 no-overwrite authority。任何 path/size/SHA、source/tool identity、strict/a004
identity、translation multiset、cgroup、OOM、timeout、proof cap、df low-water、
process-group cleanup 或原始状态行漂移都会关闭 receipt replay。

本记录不宣称 witness、feasible lower bound、attainability、global optimality、
whole-instance infeasibility 或 production `CERTIFIED`。
