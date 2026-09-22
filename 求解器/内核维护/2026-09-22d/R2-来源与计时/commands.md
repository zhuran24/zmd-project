# A/A 完整命令与原始输出索引

每组 a、b 的 argv、cwd、环境和目标路径相同，按 a 完成后 b 开始的次序执行。结果写入同一个自有目标路径，再分别保存其原始字节；没有路径映射或字段过滤。环境、二进制身份见 [baseline.json](baseline.json)。

**seed**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' seed '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/seed/a.command.json) · [a stdout](aa/seed/a.stdout.log) · [a stderr](aa/seed/a.stderr.log) · [b 命令](aa/seed/b.command.json) · [b stdout](aa/seed/b.stdout.log) · [b stderr](aa/seed/b.stderr.log)

**seed-out**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' seed '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/seed.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/seed-out/a.command.json) · [a stdout](aa/seed-out/a.stdout.log) · [a stderr](aa/seed-out/a.stderr.log) · [b 命令](aa/seed-out/b.command.json) · [b stdout](aa/seed-out/b.stdout.log) · [b stderr](aa/seed-out/b.stderr.log)

产物 `seed`：[a](aa/seed-out/a.seed.json) · [b](aa/seed-out/b.seed.json)

**check**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' check '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/check/a.command.json) · [a stdout](aa/check/a.stdout.log) · [a stderr](aa/check/a.stderr.log) · [b 命令](aa/check/b.command.json) · [b stdout](aa/check/b.stdout.log) · [b stderr](aa/check/b.stderr.log)

**check-cycle-domain**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' check '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --cycle-domain
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/check-cycle-domain/a.command.json) · [a stdout](aa/check-cycle-domain/a.stdout.log) · [a stderr](aa/check-cycle-domain/a.stderr.log) · [b 命令](aa/check-cycle-domain/b.command.json) · [b stdout](aa/check-cycle-domain/b.stdout.log) · [b stderr](aa/check-cycle-domain/b.stderr.log)

**request-fixed**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' request time.domain --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/request-fixed/a.command.json) · [a stdout](aa/request-fixed/a.stdout.log) · [a stderr](aa/request-fixed/a.stderr.log) · [b 命令](aa/request-fixed/b.command.json) · [b stdout](aa/request-fixed/b.stdout.log) · [b stderr](aa/request-fixed/b.stderr.log)

**request-stop**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' request damping.no_terminal --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/request-stop/a.command.json) · [a stdout](aa/request-stop/a.stdout.log) · [a stderr](aa/request-stop/a.stderr.log) · [b 命令](aa/request-stop/b.command.json) · [b stdout](aa/request-stop/b.stdout.log) · [b stderr](aa/request-stop/b.stderr.log)

**request-invalid**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' request r2.unknown.axis --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/request-invalid/a.command.json) · [a stdout](aa/request-invalid/a.stdout.log) · [a stderr](aa/request-invalid/a.stderr.log) · [b 命令](aa/request-invalid/b.command.json) · [b stdout](aa/request-invalid/b.stdout.log) · [b stderr](aa/request-invalid/b.stderr.log)

**run-full**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 12 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-full.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/run-full/a.command.json) · [a stdout](aa/run-full/a.stdout.log) · [a stderr](aa/run-full/a.stderr.log) · [b 命令](aa/run-full/b.command.json) · [b stdout](aa/run-full/b.stdout.log) · [b stderr](aa/run-full/b.stderr.log)

产物 `record`：[a](aa/run-full/a.record.json) · [b](aa/run-full/b.record.json)

**run-grinder**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/混做粉碎机两下游.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 4 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-grinder.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/run-grinder/a.command.json) · [a stdout](aa/run-grinder/a.stdout.log) · [a stderr](aa/run-grinder/a.stderr.log) · [b 命令](aa/run-grinder/b.command.json) · [b stdout](aa/run-grinder/b.stdout.log) · [b stderr](aa/run-grinder/b.stderr.log)

产物 `record`：[a](aa/run-grinder/a.record.json) · [b](aa/run-grinder/b.record.json)

**run-splitter**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/分流器三路轮询.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 12 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-splitter.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/run-splitter/a.command.json) · [a stdout](aa/run-splitter/a.stdout.log) · [a stderr](aa/run-splitter/a.stderr.log) · [b 命令](aa/run-splitter/b.command.json) · [b stdout](aa/run-splitter/b.stdout.log) · [b stderr](aa/run-splitter/b.stderr.log)

产物 `record`：[a](aa/run-splitter/a.record.json) · [b](aa/run-splitter/b.record.json)

**run-delta**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 12 --format checkpoint_delta --checkpoint-interval 3 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-delta.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/run-delta/a.command.json) · [a stdout](aa/run-delta/a.stdout.log) · [a stderr](aa/run-delta/a.stderr.log) · [b 命令](aa/run-delta/b.command.json) · [b stdout](aa/run-delta/b.stdout.log) · [b stderr](aa/run-delta/b.stderr.log)

产物 `record`：[a](aa/run-delta/a.record.json) · [b](aa/run-delta/b.record.json)

**run-no-cache**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 12 --no-cache --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-no-cache.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/run-no-cache/a.command.json) · [a stdout](aa/run-no-cache/a.stdout.log) · [a stderr](aa/run-no-cache/a.stderr.log) · [b 命令](aa/run-no-cache/b.command.json) · [b stdout](aa/run-no-cache/b.stdout.log) · [b stderr](aa/run-no-cache/b.stderr.log)

产物 `record`：[a](aa/run-no-cache/a.record.json) · [b](aa/run-no-cache/b.record.json)

**run-no-output**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 20 --no-output
```

退出码 a/b：0/0；不稳定路径：stdout.$["elapsed_ns"]。

[a 命令](aa/run-no-output/a.command.json) · [a stdout](aa/run-no-output/a.stdout.log) · [a stderr](aa/run-no-output/a.stderr.log) · [b 命令](aa/run-no-output/b.command.json) · [b stdout](aa/run-no-output/b.stdout.log) · [b stderr](aa/run-no-output/b.stderr.log)

**run-no-output-no-cache**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 20 --no-output --no-cache
```

退出码 a/b：0/0；不稳定路径：stdout.$["elapsed_ns"]。

[a 命令](aa/run-no-output-no-cache/a.command.json) · [a stdout](aa/run-no-output-no-cache/a.stdout.log) · [a stderr](aa/run-no-output-no-cache/a.stderr.log) · [b 命令](aa/run-no-output-no-cache/b.command.json) · [b stdout](aa/run-no-output-no-cache/b.stdout.log) · [b stderr](aa/run-no-output-no-cache/b.stderr.log)

**run-no-output-zero**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 0 --no-output
```

退出码 a/b：0/0；不稳定路径：stdout.$["elapsed_ns"]。

[a 命令](aa/run-no-output-zero/a.command.json) · [a stdout](aa/run-no-output-zero/a.stdout.log) · [a stderr](aa/run-no-output-zero/a.stderr.log) · [b 命令](aa/run-no-output-zero/b.command.json) · [b stdout](aa/run-no-output-zero/b.stdout.log) · [b stderr](aa/run-no-output-zero/b.stderr.log)

**run-no-output-stop**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 20 --max-sweeps 1 --no-output
```

退出码 a/b：2/2；不稳定路径：stdout.$["elapsed_ns"]。

[a 命令](aa/run-no-output-stop/a.command.json) · [a stdout](aa/run-no-output-stop/a.stdout.log) · [a stderr](aa/run-no-output-stop/a.stderr.log) · [b 命令](aa/run-no-output-stop/b.command.json) · [b stdout](aa/run-no-output-stop/b.stdout.log) · [b stderr](aa/run-no-output-stop/b.stderr.log)

**run-no-output-out**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 20 --no-output --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-no-output-out.json'
```

退出码 a/b：0/0；不稳定路径：measurement.$["elapsed_ns"]。

[a 命令](aa/run-no-output-out/a.command.json) · [a stdout](aa/run-no-output-out/a.stdout.log) · [a stderr](aa/run-no-output-out/a.stderr.log) · [b 命令](aa/run-no-output-out/b.command.json) · [b stdout](aa/run-no-output-out/b.stdout.log) · [b stderr](aa/run-no-output-out/b.stderr.log)

产物 `measurement`：[a](aa/run-no-output-out/a.measurement.json) · [b](aa/run-no-output-out/b.measurement.json)

**run-stopped**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 20 --max-sweeps 1 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-stopped.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/run-stopped/a.command.json) · [a stdout](aa/run-stopped/a.stdout.log) · [a stderr](aa/run-stopped/a.stderr.log) · [b 命令](aa/run-stopped/b.command.json) · [b stdout](aa/run-stopped/b.stdout.log) · [b stderr](aa/run-stopped/b.stderr.log)

产物 `record`：[a](aa/run-stopped/a.record.json) · [b](aa/run-stopped/b.record.json)

**verify-record-full**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-record '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-full.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-record-full/a.command.json) · [a stdout](aa/verify-record-full/a.stdout.log) · [a stderr](aa/verify-record-full/a.stderr.log) · [b 命令](aa/verify-record-full/b.command.json) · [b stdout](aa/verify-record-full/b.stdout.log) · [b stderr](aa/verify-record-full/b.stderr.log)

**verify-record-delta**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-record '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-delta.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-record-delta/a.command.json) · [a stdout](aa/verify-record-delta/a.stdout.log) · [a stderr](aa/verify-record-delta/a.stderr.log) · [b 命令](aa/verify-record-delta/b.command.json) · [b stdout](aa/verify-record-delta/b.stdout.log) · [b stderr](aa/verify-record-delta/b.stderr.log)

**checkpoint-record**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' checkpoint '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/run-full.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/checkpoint-record.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/checkpoint-record/a.command.json) · [a stdout](aa/checkpoint-record/a.stdout.log) · [a stderr](aa/checkpoint-record/a.stderr.log) · [b 命令](aa/checkpoint-record/b.command.json) · [b stdout](aa/checkpoint-record/b.stdout.log) · [b stderr](aa/checkpoint-record/b.stderr.log)

产物 `seed`：[a](aa/checkpoint-record/a.seed.json) · [b](aa/checkpoint-record/b.seed.json)

**cycle-referenced**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 20 --search-checkpoint-interval 3 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-referenced/a.command.json) · [a stdout](aa/cycle-referenced/a.stdout.log) · [a stderr](aa/cycle-referenced/a.stderr.log) · [b 命令](aa/cycle-referenced/b.command.json) · [b stdout](aa/cycle-referenced/b.stdout.log) · [b stderr](aa/cycle-referenced/b.stderr.log)

产物 `certificate`：[a](aa/cycle-referenced/a.certificate.json) · [b](aa/cycle-referenced/b.certificate.json)

产物 `record`：[a](aa/cycle-referenced/a.record.json) · [b](aa/cycle-referenced/b.record.json)

**cycle-no-record**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 20 --no-record
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-no-record/a.command.json) · [a stdout](aa/cycle-no-record/a.stdout.log) · [a stderr](aa/cycle-no-record/a.stderr.log) · [b 命令](aa/cycle-no-record/b.command.json) · [b stdout](aa/cycle-no-record/b.stdout.log) · [b stderr](aa/cycle-no-record/b.stderr.log)

**cycle-budget**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 1 --no-record
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-budget/a.command.json) · [a stdout](aa/cycle-budget/a.stdout.log) · [a stderr](aa/cycle-budget/a.stderr.log) · [b 命令](aa/cycle-budget/b.command.json) · [b stdout](aa/cycle-budget/b.stdout.log) · [b stderr](aa/cycle-budget/b.stderr.log)

**cycle-sweep-stop**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 20 --max-sweeps 1 --no-record
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-sweep-stop/a.command.json) · [a stdout](aa/cycle-sweep-stop/a.stdout.log) · [a stderr](aa/cycle-sweep-stop/a.stderr.log) · [b 命令](aa/cycle-sweep-stop/b.command.json) · [b stdout](aa/cycle-sweep-stop/b.stdout.log) · [b stderr](aa/cycle-sweep-stop/b.stderr.log)

**verify-cycle**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-cycle '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-cycle/a.command.json) · [a stdout](aa/verify-cycle/a.stdout.log) · [a stderr](aa/verify-cycle/a.stderr.log) · [b 命令](aa/verify-cycle/b.command.json) · [b stdout](aa/verify-cycle/b.stdout.log) · [b stderr](aa/verify-cycle/b.stderr.log)

**checkpoint-cycle**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' checkpoint '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/checkpoint-cycle.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/checkpoint-cycle/a.command.json) · [a stdout](aa/checkpoint-cycle/a.stdout.log) · [a stderr](aa/checkpoint-cycle/a.stderr.log) · [b 命令](aa/checkpoint-cycle/b.command.json) · [b stdout](aa/checkpoint-cycle/b.stdout.log) · [b stderr](aa/checkpoint-cycle/b.stderr.log)

产物 `seed`：[a](aa/checkpoint-cycle/a.seed.json) · [b](aa/checkpoint-cycle/b.seed.json)

**verify-batch**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-batch '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-batch/a.command.json) · [a stdout](aa/verify-batch/a.stdout.log) · [a stderr](aa/verify-batch/a.stderr.log) · [b 命令](aa/verify-batch/b.command.json) · [b stdout](aa/verify-batch/b.stdout.log) · [b stderr](aa/verify-batch/b.stderr.log)

**seed-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' seed '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/seed-invalid-input/a.command.json) · [a stdout](aa/seed-invalid-input/a.stdout.log) · [a stderr](aa/seed-invalid-input/a.stderr.log) · [b 命令](aa/seed-invalid-input/b.command.json) · [b stdout](aa/seed-invalid-input/b.stdout.log) · [b stderr](aa/seed-invalid-input/b.stderr.log)

**check-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' check '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/check-invalid-input/a.command.json) · [a stdout](aa/check-invalid-input/a.stdout.log) · [a stderr](aa/check-invalid-input/a.stderr.log) · [b 命令](aa/check-invalid-input/b.command.json) · [b stdout](aa/check-invalid-input/b.stdout.log) · [b stderr](aa/check-invalid-input/b.stderr.log)

**run-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' run '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --ticks 1 --no-output
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/run-invalid-input/a.command.json) · [a stdout](aa/run-invalid-input/a.stdout.log) · [a stderr](aa/run-invalid-input/a.stderr.log) · [b 命令](aa/run-invalid-input/b.command.json) · [b stdout](aa/run-invalid-input/b.stdout.log) · [b stderr](aa/run-invalid-input/b.stderr.log)

**cycle-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 1 --no-record
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/cycle-invalid-input/a.command.json) · [a stdout](aa/cycle-invalid-input/a.stdout.log) · [a stderr](aa/cycle-invalid-input/a.stderr.log) · [b 命令](aa/cycle-invalid-input/b.command.json) · [b stdout](aa/cycle-invalid-input/b.stdout.log) · [b stderr](aa/cycle-invalid-input/b.stderr.log)

**verify-record-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-record '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/verify-record-invalid-input/a.command.json) · [a stdout](aa/verify-record-invalid-input/a.stdout.log) · [a stderr](aa/verify-record-invalid-input/a.stderr.log) · [b 命令](aa/verify-record-invalid-input/b.command.json) · [b stdout](aa/verify-record-invalid-input/b.stdout.log) · [b stderr](aa/verify-record-invalid-input/b.stderr.log)

**verify-cycle-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-cycle '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/verify-cycle-invalid-input/a.command.json) · [a stdout](aa/verify-cycle-invalid-input/a.stdout.log) · [a stderr](aa/verify-cycle-invalid-input/a.stderr.log) · [b 命令](aa/verify-cycle-invalid-input/b.command.json) · [b stdout](aa/verify-cycle-invalid-input/b.stdout.log) · [b stderr](aa/verify-cycle-invalid-input/b.stderr.log)

**checkpoint-invalid-input**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' checkpoint '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/checkpoint-invalid-input/a.command.json) · [a stdout](aa/checkpoint-invalid-input/a.stdout.log) · [a stderr](aa/checkpoint-invalid-input/a.stderr.log) · [b 命令](aa/checkpoint-invalid-input/b.command.json) · [b stdout](aa/checkpoint-invalid-input/b.stdout.log) · [b stderr](aa/checkpoint-invalid-input/b.stderr.log)

**cli-no-args**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/cli-no-args/a.command.json) · [a stdout](aa/cli-no-args/a.stdout.log) · [a stderr](aa/cli-no-args/a.stderr.log) · [b 命令](aa/cli-no-args/b.command.json) · [b stdout](aa/cli-no-args/b.stdout.log) · [b stderr](aa/cli-no-args/b.stderr.log)

**cli-unknown-command**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' r2-unknown '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/cli-unknown-command/a.command.json) · [a stdout](aa/cli-unknown-command/a.stdout.log) · [a stderr](aa/cli-unknown-command/a.stderr.log) · [b 命令](aa/cli-unknown-command/b.command.json) · [b stdout](aa/cli-unknown-command/b.stdout.log) · [b stderr](aa/cli-unknown-command/b.stderr.log)

**topology-contract**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/topology-baseline' '/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/contract.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/topology-contract/a.command.json) · [a stdout](aa/topology-contract/a.stdout.log) · [a stderr](aa/topology-contract/a.stderr.log) · [b 命令](aa/topology-contract/b.command.json) · [b stdout](aa/topology-contract/b.stdout.log) · [b stderr](aa/topology-contract/b.stderr.log)

**topology-invalid**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/topology-baseline' '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/bad-input.json'
```

退出码 a/b：2/2；不稳定路径：无。

[a 命令](aa/topology-invalid/a.command.json) · [a stdout](aa/topology-invalid/a.stdout.log) · [a stderr](aa/topology-invalid/a.stderr.log) · [b 命令](aa/topology-invalid/b.command.json) · [b stdout](aa/topology-invalid/b.stdout.log) · [b stderr](aa/topology-invalid/b.stderr.log)

**cycle-found-referenced**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 50 --search-checkpoint-interval 3 --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle-found.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-found-referenced/a.command.json) · [a stdout](aa/cycle-found-referenced/a.stdout.log) · [a stderr](aa/cycle-found-referenced/a.stderr.log) · [b 命令](aa/cycle-found-referenced/b.command.json) · [b stdout](aa/cycle-found-referenced/b.stdout.log) · [b stderr](aa/cycle-found-referenced/b.stderr.log)

产物 `certificate`：[a](aa/cycle-found-referenced/a.certificate.json) · [b](aa/cycle-found-referenced/b.certificate.json)

产物 `record`：[a](aa/cycle-found-referenced/a.record.json) · [b](aa/cycle-found-referenced/b.record.json)

**cycle-found-no-record**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' cycle '/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --max-ticks 50 --no-record
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/cycle-found-no-record/a.command.json) · [a stdout](aa/cycle-found-no-record/a.stdout.log) · [a stderr](aa/cycle-found-no-record/a.stderr.log) · [b 命令](aa/cycle-found-no-record/b.command.json) · [b stdout](aa/cycle-found-no-record/b.stdout.log) · [b stderr](aa/cycle-found-no-record/b.stderr.log)

**verify-cycle-found**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-cycle '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle-found.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-cycle-found/a.command.json) · [a stdout](aa/verify-cycle-found/a.stdout.log) · [a stderr](aa/verify-cycle-found/a.stderr.log) · [b 命令](aa/verify-cycle-found/b.command.json) · [b stdout](aa/verify-cycle-found/b.stdout.log) · [b stderr](aa/verify-cycle-found/b.stderr.log)

**checkpoint-cycle-found**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' checkpoint '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch/cycle-found.json' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json' --out '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/artifacts/checkpoint-cycle-found.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/checkpoint-cycle-found/a.command.json) · [a stdout](aa/checkpoint-cycle-found/a.stdout.log) · [a stderr](aa/checkpoint-cycle-found/a.stderr.log) · [b 命令](aa/checkpoint-cycle-found/b.command.json) · [b stdout](aa/checkpoint-cycle-found/b.stdout.log) · [b stderr](aa/checkpoint-cycle-found/b.stderr.log)

产物 `seed`：[a](aa/checkpoint-cycle-found/a.seed.json) · [b](aa/checkpoint-cycle-found/b.seed.json)

**verify-batch-with-cycle-found**

```sh
'/home/zhuran24/zmd-research-fresh/求解器/target/r2-source-timing-20260922/kernel-baseline' verify-batch '/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22d/R2-来源与计时/aa/batch' --config '/home/zhuran24/zmd-research-fresh/求解器/规格/内核配置-v1.json'
```

退出码 a/b：0/0；不稳定路径：无。

[a 命令](aa/verify-batch-with-cycle-found/a.command.json) · [a stdout](aa/verify-batch-with-cycle-found/a.stdout.log) · [a stderr](aa/verify-batch-with-cycle-found/a.stderr.log) · [b 命令](aa/verify-batch-with-cycle-found/b.command.json) · [b stdout](aa/verify-batch-with-cycle-found/b.stdout.log) · [b stderr](aa/verify-batch-with-cycle-found/b.stderr.log)
