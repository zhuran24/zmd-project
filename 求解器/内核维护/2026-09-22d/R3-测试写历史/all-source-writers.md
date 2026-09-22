# 静态写点与路径表达式台账

源码只读扫描；未执行列出的程序。`sinks` 包括创建目录、覆盖、删除和移动；`calls` 为间接写出链定位，不能仅凭命名认定实际写入。历史快照不是当前测试入口。

## crates/kernel/evidence/round6/final_audit.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[4]
4: E = Path(__file__).resolve().parent
4: BASE = ROOT / '数据/样例'
sinks
6: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
90: (E / '实施与验证.md').write_text(report)
98: p.write_text(text)
calls
30: save(E / 'coverage.json', dict(axis_count=len(coverage), exercised=sum(('exercised' in v for v in coverage.values())), without_exercised={a: v for a, v in coverage.items() if 'exercised' not in v}, all_axes=coverage, scope='当前保留的有限记录覆盖并集；输入检查、停止未触发和未决不能冒称实际执行，不替代种子/参数/读法全称。'))
36: save(E / 'storage-final.json', sizes)
39: save(E / 'final-audit.json', summary)
107: save(E / 'files.json', dict(files=files, modified=changed, added=added, deleted=deleted, scope='绝对路径；新增/修改交付及已有文件删除。target编译产物不列入交付，写权外源文件仅只读引用。'))
```

## crates/kernel/evidence/round6/final_validation.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[4]
4: E = Path(__file__).resolve().parent
5: ENV = dict(os.environ, CARGO_HOME=str(ROOT / '.cargo-home'), CARGO_TARGET_DIR=str(ROOT / 'target'), PYTHONDONTWRITEBYTECODE='1')
21: dest = E / (name + '-cycle.json')
sinks
11: (E / 'validation-commands.json').write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n')
calls
9: subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
13: run('clippy', ['cargo', 'clippy', '--locked', '--offline', '--all-targets', '--', '-D', 'warnings'])
14: run('build', ['cargo', 'build', '--release', '--locked', '--offline', '-p', 'kernel'])
15: run('migration-final', [sys.executable, '-B', ROOT / 'crates/kernel/tests/refresh_round6.py', '--certificates', '--records'])
16: run('K6', [sys.executable, '-B', ROOT / 'crates/kernel/tests/production_attempt_round6.py'])
17: run('benchmark-final', [sys.executable, '-B', ROOT / 'crates/kernel/tests/benchmark_round6.py', 'final'])
18: run('cli', [sys.executable, '-B', ROOT / 'crates/kernel/tests/round6_cli.py'])
19: run('verify-readonly', [sys.executable, '-B', E / 'verify_readonly.py'])
22: run(name + '-cycle', [ROOT / 'target/release/kernel', 'cycle', ROOT / '数据/样例' / (name + '.json'), '--config', ROOT / '规格/内核配置-v1.json', '--max-ticks', ticks, '--no-record', '--out', dest])
23: run(name + '-verify', [ROOT / 'target/release/kernel', 'verify-cycle', dest, '--config', ROOT / '规格/内核配置-v1.json'])
24: run('reduction-after', [sys.executable, '-B', ROOT / '规格/复核/约减/count_classes.py', '--check'])
```

## crates/kernel/evidence/round6/relock_reduction.py

```text
assignments
6: ROOT = Path(__file__).resolve().parents[4]
6: E = Path(__file__).resolve().parent
7: target = script.parent / '等价类计数.json'
sinks
10: (E / (label + '.log')).write_text(p.stdout + p.stderr)
19: target.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n')
22: (E / 'reduction-lock.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
9: subprocess.run([sys.executable, '-B', str(script), '--check'], capture_output=True, text=True, cwd=ROOT)
```

## crates/kernel/evidence/round6/revision-r5/final_audit.py

```text
assignments
7: E = Path(__file__).resolve().parent
8: ROOT = E.parents[4]
9: BASE = ROOT / '数据/样例'
59: source = (ROOT / 'crates/kernel/src' / name).read_text()
sinks
14: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
65: save(E / 'reader-review.json', dict(status='pass', documents=list(map(str, documents)), checks={'陌生读者上下文': '三发现及条款、接口和试样均自包含', '终态与史料': 'README及本报告为现状，原round6报告明确标成执行存档', '头部状态': '报告与最终机械验收一致', '指令回声': '未把写作指令写进正文', '数字口径': '141项测试、52次CLI、29份记录和11份循环；旧数字均在历史区', '命名': '沿用发现ID、KQ编号及revision-r5路径', '交叉引用': '本次四份文档全部本地链接目标存在'}))
82: save(E / 'final-audit.json', summary)
90: save(E / 'files.json', dict(files=files, changed_from_baseline=sorted(changed), deleted=deleted, scope='所有本次修改/新增/重跑写入的交付文件；既有证据写入按开工时间核，源码及样例按字节核。target编译产物不列入。'))
```

## crates/kernel/evidence/round6/revision-r5/refresh_samples.py

```text
assignments
9: E = Path(__file__).resolve().parent
10: ROOT = E.parents[4]
11: BASE = ROOT / '数据/样例'
12: BIN = ROOT / 'target/release/kernel'
13: CFG = ROOT / '规格/内核配置-v1.json'
38: source = path.parent / previous['replay_input_ref']['path']
47: source = next((path.parent / r['path'] for r in previous['fingerprints'] if r['role'] == 'input'))
sinks
21: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
30: stage.mkdir(exist_ok=True)
64: temporary.replace(path)
calls
23: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
40: run('cycle', source, '--max-ticks', budget['max_ticks'], '--max-sweeps', budget['max_sweeps'], '--no-record', '--out', temporary)
41: run('verify-cycle', temporary)
50: run('run', source, '--ticks', len(previous['trace']['ticks']), '--format', previous['trace']['format'], '--checkpoint-interval', previous['trace'].get('checkpoint_interval', 10), '--out', temporary)
52: run('verify-record', temporary)
59: save(temporary, current)
68: save(E / 'sample-regeneration.json', dict(status='running', files=rows))
69: save(E / 'sample-regeneration.json', dict(status='pass', files=rows, records=sum(('运行记录' in r['path'] for r in rows)), cycles=sum(('周期证书' in r['path'] for r in rows)), scope='保持输入、预算、完整轨迹/周期及结论；按当前实现从源重跑，非刷新旧哈希'))
```

## crates/kernel/evidence/round6/revision-r5/relock_reduction.py

```text
assignments
6: ROOT = Path(__file__).resolve().parents[5]
6: E = Path(__file__).resolve().parent
7: target = script.parent / '等价类计数.json'
sinks
10: (E / (label + '.log')).write_text(p.stdout + p.stderr)
19: target.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n')
22: (E / 'reduction-lock.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
9: subprocess.run([sys.executable, '-B', str(script), '--check'], capture_output=True, text=True, cwd=ROOT)
```

## crates/kernel/evidence/round6/revision-r5/validate.py

```text
assignments
9: E = Path(__file__).resolve().parent
10: ROOT = E.parents[4]
11: ENV = dict(os.environ, CARGO_HOME=str(ROOT / '.cargo-home'), CARGO_TARGET_DIR=str(ROOT / 'target'), PYTHONDONTWRITEBYTECODE='1')
14: STEPS = json.loads((E / 'validation-commands.json').read_text()) if FINISH_ONLY else []
sinks
25: (E / 'validation-commands.json').write_text(json.dumps(STEPS, ensure_ascii=False, indent=2) + '\n')
calls
21: subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
31: run('cargo-test', ['cargo', 'test', '--locked', '--offline'])
32: run('clippy', ['cargo', 'clippy', '--locked', '--offline', '--all-targets', '--', '-D', 'warnings'])
33: run('build', ['cargo', 'build', '--release', '--locked', '--offline', '-p', 'kernel'])
34: run('release-cli', [sys.executable, '-B', ROOT / 'crates/kernel/tests/revision_r5_cli.py'])
35: run('regenerate', [sys.executable, '-B', E / 'refresh_samples.py'])
36: run('benchmark', [sys.executable, '-B', ROOT / 'crates/kernel/tests/benchmark_round6.py', 'final', '--out-dir', E / 'benchmark'])
37: run('verify-readonly', [sys.executable, '-B', E / 'verify_readonly.py'])
38: run('spec-selfcheck', [sys.executable, '-B', E / 'spec_selfcheck.py'])
39: run('reduction-lock', [sys.executable, '-B', E / 'relock_reduction.py'])
```

## crates/kernel/evidence/round6/revision-r5/verify_readonly.py

```text
assignments
7: E = Path(__file__).resolve().parent
8: ROOT = E.parents[4]
9: BIN = ROOT / 'target/release/kernel'
sinks
23: (E / (name + '.log')).write_text(checked.stderr)
29: (E / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
21: subprocess.run([str(BIN), 'verify-batch', str(directory)], capture_output=True, text=True, cwd=ROOT.parent)
```

## crates/kernel/evidence/round6/verify_readonly.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[4]
4: E = Path(__file__).resolve().parent
4: BIN = ROOT / 'target/release/kernel'
sinks
10: (E / (name + '.log')).write_text(p.stderr)
15: (E / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
9: subprocess.run([str(BIN), 'verify-batch', str(directory)], capture_output=True, text=True, cwd=ROOT)
```

## crates/kernel/src/catalog.rs

```text
assignments
sinks
49:     let out = Command::new("sha256sum")
calls
```

## crates/kernel/src/cycle_io.rs

```text
assignments
sinks
13:     std::fs::write(
calls
```

## crates/kernel/src/main.rs

```text
assignments
sinks
12:         return Err(Stop::invalid("cli","用法：kernel run <input.json> --config <配置.json> --ticks N --out <记录.json> [--format full_state_each_instant|checkpoint_delta] [--checkpoint-interval K]；输出关闭用 --no-output"));
19:         let mut child = std::process::Command::new("python");
101:             "--out" => out = Some(PathBuf::from(value)),
231:                     Stop::invalid("cli.cycle", "有记录模式须给 --out；无记录用 --no-record")
323:         std::fs::write(&path, text)
332:             "记录输出须指定 --out；性能运行用 --no-output",
calls
```

## crates/kernel/tests/audit_dense_round5.py

```text
assignments
8: ROOT = Path(__file__).resolve().parents[3]
9: BASE = ROOT / '数据/样例'
10: E = ROOT / 'crates/kernel/evidence/round5'
sinks
132: (E / 'dense-manufacturing-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
138: main()
```

## crates/kernel/tests/audit_revision_r3.py

```text
assignments
8: ROOT = Path(__file__).resolve().parents[3]
9: OUT = ROOT / 'crates/kernel/evidence/revision-r3'
sinks
44: (OUT / 'cli-schema-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
49: main()
```

## crates/kernel/tests/audit_round5.py

```text
assignments
5: ROOT = Path(__file__).resolve().parents[3]
5: BASE = ROOT / '数据/样例'
5: E = ROOT / 'crates/kernel/evidence/round5'
10: SCHEMA = json.loads((ROOT / '规格/内核输出.schema.json').read_text())
11: BIN = ROOT / 'target/release/kernel'
11: CFG = ROOT / '规格/内核配置-v1.json'
135: path = BASE / (name + '-周期证书-kernel.json')
176: record = read(BASE / (name + '-运行记录-v3-kernel.json'))
sinks
14: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
79: subprocess.run([str(BIN), 'verify-record', str(path), '--config', str(CFG)], capture_output=True, text=True)
161: subprocess.run([str(BIN), 'verify-cycle', str(path), '--config', str(CFG)], capture_output=True, text=True)
181: write(E / 'bridge-first-contact-audit.json', dict(status='pass', cases=bridge_audit, missing_reason=reasons['connection.bridge_first_contact']))
185: write(E / 'polling-six-orders.json', dict(status='pass', cases=variants, scope='当前来源下六局部顺序的实际回放，不代替全局全序约减'))
191: write(E / 'audit-results.json', result)
192: main()
```

## crates/kernel/tests/benchmark_round5.py

```text
assignments
8: E = ROOT / 'crates/kernel/evidence/round5'
26: source = b.OUT / (name + '.json')
37: source = b.OUT / 'benchmark_brick_60.json'
54: output = dict(stage=stage, platform=platform.platform(), binary_sha256=binary_digest, reports=reports, scope='合成物流压力测试；砖档57单位/97PC，另保留81单位/100PC的纵向送料对照；候选B档219制造台/315逻辑段/630PC，未声称真实候选B布置可行或制造满载。')
sinks
calls
17: b.generate(name, units)
26: save(source, d)
30: b.generate('benchmark_brick_60', units)
37: save(source, d)
45: generate(name, m, l, c)
46: subprocess.run([str(binary), 'seed', str(source), '--config', str(config), '--out', str(source)], capture_output=True, text=True)
49: subprocess.run(command, capture_output=True, text=True)
55: save(E / f'benchmark-{stage}.json', output)
58: run(sys.argv[1] if len(sys.argv) > 1 else 'before')
```

## crates/kernel/tests/benchmark_round6.py

```text
assignments
11: E = ROOT / 'crates/kernel/evidence/round6'
11: BASE = ROOT / '数据/样例'
11: BIN = ROOT / 'target/release/kernel'
11: CFG = ROOT / '规格/内核配置-v1.json'
32: path = BASE / '双成品制造砖.json'
37: E = args.out_dir.resolve()
45: dest = E / (path.stem + '-benchmark-cycle.json')
60: path = BASE / '双成品制造砖.json'
60: record = BASE / '双成品制造砖-运行记录-v3-kernel.json'
66: output = dict(status='pass', stage=args.stage, platform=platform.platform(), binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), reports=reports, production_audit=dict(record=str(record), completed_batches=data['validation_scope']['manufacturing_cycles_completed'], actual_inbound=totals, cache_differential='逐字段相同' if args.stage == 'final' else '留最终验证'), historical_benchmark_brick_ms_per_tick=2.74, historical_target_met=False, scope='目标达标位与基准执行通过分开；cycle墙钟包含装载、指纹、搜索和写小证书，run engine只含转移；条件预装原料不证明闭环或任务可达性。')
sinks
37: E.mkdir(parents=True, exist_ok=True)
49: rss.write_text(json.dumps(measured, ensure_ascii=False) + '\n')
65: other.unlink()
calls
14: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
24: b.generate('双成品制造砖', units)
32: save(path, migrate(d))
32: call(['seed', path, '--out', path])
36: parser.add_argument('--out-dir', type=Path)
38: generate()
48: subprocess.run([sys.executable, '-B', str(ROOT / 'crates/kernel/tests/measure_command.py'), *cmd], capture_output=True, text=True, check=True)
61: call(['run', path, '--ticks', 12, '--out', record])
61: call(['verify-record', record])
65: call(['run', path, '--ticks', 12, '--no-cache', '--out', other])
67: save(E / f'benchmark-{args.stage}.json', output)
68: main()
```

## crates/kernel/tests/build_fixtures.py

```text
assignments
8: ROOT = Path(__file__).resolve().parents[3]
15: OUT = Path(__file__).parent / 'fixtures'
16: CATALOG = checker.load_json(ROOT / '数据/正式静态目录.json')
17: BASE = checker.load_json(ROOT / '数据/样例/混做粉碎机两下游.json')
sinks
74: (OUT / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
80: OUT.mkdir(exist_ok=True)
92: (OUT / 'benchmark_1000.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
81: generate('bridge', [unit('south_box', '协议储存箱', 10, 7), unit('bridge', '桥接器', 12, 10), unit('north_box', '协议储存箱', 12, 11), unit('west_box', '协议储存箱', 9, 10, 'r270'), unit('east_box', '协议储存箱', 13, 8, 'r270'), unit('power', '供电桩', 16, 10)])
82: generate('priority', [unit('source', '协议储存箱', 10, 10), unit('merger', '汇流器', 10, 13), unit('gate', '物品准入口', 10, 14), unit('sink_a', '协议储存箱', 10, 15), unit('sink_b', '协议储存箱', 13, 14), unit('belt_1', '传送带', 12, 13, port_layout=1), unit('belt_2', '传送带', 13, 13, 'r270', 2)])
83: generate('core_inbound', [unit('box', '协议储存箱', 50, 46), unit('belt', '传送带', 51, 49)])
96: main()
```

## crates/kernel/tests/cleanup_revision_r3.py

```text
assignments
8: KERNEL = Path(__file__).resolve().parents[1]
9: OUT = KERNEL / 'evidence/revision-r3'
36: report_path = OUT / 'cleanup.json'
64: path = Path(row['path'])
sinks
56: new.parent.mkdir(parents=True, exist_ok=True)
57: old.rename(new)
59: manifest.read_text().replace('../snapshot/求解器/crates/kernel', '../../..')
60: manifest.write_text(text)
66: path.unlink()
68: shutil.rmtree(snapshot)
75: report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
81: main()
```

## crates/kernel/tests/dense_cycle_round5.py

```text
assignments
8: BASE = s.OUT
sinks
calls
50: s.b.generate('密集结点闭环核验', units)
```

## crates/kernel/tests/dense_manufacturing_round5.py

```text
assignments
8: BASE = s.OUT
65: source = BASE / (name + '.json')
70: out = BASE / (name + '-周期证书-kernel.json')
83: record = BASE / (name + '-运行记录-v3-kernel.json')
sinks
69: source.write_bytes(normalized.read_bytes())
69: normalized.unlink()
83: record.write_text(json.dumps(result['run_record'], ensure_ascii=False, separators=(',', ':')) + '\n')
83: out.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
84: (ROOT / 'crates/kernel/evidence/round5/dense-manufacturing-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
calls
34: s.b.generate('密集制造闭环基础', units)
65: save(source, d)
67: subprocess.run([str(BIN), 'seed', str(source), '--config', str(CFG), '--out', str(normalized)], capture_output=True, text=True)
71: subprocess.run([str(BIN), 'cycle', str(source), '--config', str(CFG), '--max-ticks', '1000', '--out', str(out)], capture_output=True, text=True)
```

## crates/kernel/tests/final_audit.py

```text
assignments
10: ROOT = Path(__file__).resolve().parents[3]
11: KERNEL = ROOT / 'crates/kernel'
sinks
29: (KERNEL / 'evidence/periodic-stop.json').write_text(json.dumps(stopped, ensure_ascii=False, indent=2) + '\n')
43: manifest_path.write_text('{}\n')
53: (KERNEL / 'evidence/final-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
56: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
23: subprocess.run([str(ROOT / 'target/release/kernel'), 'check', str(ROOT / '数据/样例/桥接器双通路.json'), '--config', str(ROOT / '规格/内核配置-v1.json')], capture_output=True, text=True)
25: subprocess.run([str(ROOT / 'target/release/kernel'), 'request', 'warehouse.periodic_lift', '--config', str(ROOT / '规格/内核配置-v1.json')], capture_output=True, text=True)
61: main()
```

## crates/kernel/tests/final_audit_round5.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[3]
4: K = ROOT / 'crates/kernel'
4: E = K / 'evidence/round5'
4: BASE = ROOT / '数据/样例'
67: path = (doc.parent / target.split('#')[0]).resolve()
sinks
6: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
22: legacy.write_bytes(old.read_bytes())
58: revision.write_text(text + suffix)
calls
24: write(old, final_bench)
34: write(E / '交付结果.json', result)
71: write(E / '范围审计.json', scope)
82: write(E / '交付清单.json', manifest)
84: write(E / '最终回复.json', dict(files=[str(p) for p in paths] + [str(E / '交付清单.json'), str(E / 'final-audit.log')], summary=summary, open_items=open_items))
```

## crates/kernel/tests/finalize_revision_r3.py

```text
assignments
7: ROOT = Path(__file__).resolve().parents[3]
8: KERNEL = ROOT / 'crates/kernel'
9: OUT = KERNEL / 'evidence/revision-r3'
10: ROUND5 = KERNEL / 'evidence/round5'
sinks
106: (OUT / '修订与验证.md').write_text(report)
108: revision.read_text().replace('截止日期：2026-09-19。', '截止日期：2026-09-20。')
124: revision.write_text(text)
130: (OUT / '交付结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
135: main()
```

## crates/kernel/tests/finalize_revision_r4.py

```text
assignments
10: ROOT = Path(__file__).resolve().parents[3]
11: KERNEL = ROOT / 'crates/kernel'
12: OUT = KERNEL / 'evidence/revision-r4'
184: path = (doc.parent / target.split('#')[0]).resolve()
sinks
24: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
137: (OUT / '修订与验证.md').write_text(report)
153: revision.write_text(text)
calls
52: write(OUT / 'benchmark-final.json', bench)
58: write(KERNEL / 'evidence/benchmark.json', benchmark)
59: write(KERNEL / 'evidence/round5/benchmark-final.json', bench)
83: write(OUT / '交付结果.json', result)
84: write(KERNEL / 'evidence/round5/交付结果.json', {**result, 'current_report': str(OUT / '修订与验证.md')})
196: write(OUT / '范围审计.json', scope)
202: write(OUT / '交付清单.json', dict(schema='kernel-revision-r4-files-v1', changes=changes, nonrecursive_files=sorted(excluded)))
205: write(OUT / '最终回复.json', dict(files=files, summary=summary, open_items=open_items))
210: main()
```

## crates/kernel/tests/finalize_round5.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[3]
4: BASE = ROOT / '数据/样例'
4: E = ROOT / 'crates/kernel/evidence/round5'
4: BIN = ROOT / 'target/release/kernel'
4: CFG = ROOT / '规格/内核配置-v1.json'
13: source = BASE / (name + '.json')
13: out = BASE / (name + '-运行记录-v3-kernel.json')
19: source = BASE / (name + '.json')
19: out = BASE / (name + '-运行记录-checkpoint_delta-v3-kernel.json')
26: out = BASE / (name + '-周期证书-kernel.json')
32: out = BASE / (name + '-周期证书-kernel.json')
35: record = BASE / (name + '-运行记录-v3-kernel.json')
sinks
24: (BASE / (name + '-运行记录-v3.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
36: record.write_text(json.dumps(value['run_record'], ensure_ascii=False, separators=(',', ':')) + '\n')
38: (E / 'regeneration.json').write_text(json.dumps(dict(config_revision=json.loads(CFG.read_text())['revision'], config_sha256=hashlib.sha256(CFG.read_bytes()).hexdigest(), binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), results=reports), ensure_ascii=False, indent=2) + '\n')
41: path.write_text(json.dumps(json.loads(path.read_text()), ensure_ascii=False, separators=(',', ':')) + '\n')
43: path.write_text(json.dumps(json.loads(path.read_text()), ensure_ascii=False, separators=(',', ':')) + '\n')
calls
15: subprocess.run(command, capture_output=True, text=True)
21: subprocess.run(command, capture_output=True, text=True)
22: g.run(data)
27: subprocess.run([str(BIN), 'cycle', str(BASE / (name + '.json')), '--config', str(CFG), '--max-ticks', str(names[name]), '--out', str(out)], capture_output=True, text=True)
33: subprocess.run([str(BIN), 'cycle', str(BASE / (name + '.json')), '--config', str(CFG), '--max-ticks', '1000', '--out', str(out)], capture_output=True, text=True)
```

## crates/kernel/tests/legacy_probes/r2_engineering/src/main.rs

```text
assignments
sinks
17:     std::fs::write(&forged, serde_json::to_string_pretty(&raw).unwrap()+"\n").unwrap();
23:     std::fs::write(out.join("movement-future-id-tick.json"),serde_json::to_string_pretty(&tick).unwrap()+"\n").unwrap();
34:     std::fs::write(out.join("library-probes.json"),text.clone()+"\n").unwrap();
calls
```

## crates/kernel/tests/measure_command.py

```text
assignments
sinks
calls
4: subprocess.run(sys.argv[1:], capture_output=True, text=True)
```

## crates/kernel/tests/migrate_round5.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[3]
5: SAMPLES = ROOT / '数据/样例'
sinks
7: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
43: save(p, migrate(load(p)))
47: save(SAMPLES / (out + '.json'), profile_projection(load(SAMPLES / (name + '.json'))))
```

## crates/kernel/tests/production_attempt_round6.py

```text
assignments
10: BASE = ROOT / '数据/样例'
10: E = ROOT / 'crates/kernel/evidence/round6'
10: BIN = ROOT / 'target/release/kernel'
10: CFG = ROOT / '规格/内核配置-v1.json'
46: path = BASE / (name + '.json')
sinks
calls
12: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
35: b.generate(name, units)
46: save(path, migrate(d))
46: call(['seed', path, '--out', path])
48: generate()
48: call(['check', path, '--cycle-domain'])
48: save(E / 'K6-domain.json', static)
49: call(['run', path, '--no-output', '--ticks', 512])
49: save(E / 'K6-run.json', run)
50: call(['cycle', path, '--no-record', '--max-ticks', 512, '--out', cert], True)
50: save(E / 'K6-search.json', search)
51: call(['verify-cycle', cert])
51: save(E / 'K6-verify.json', verification)
54: save(E / 'K6-result.json', report)
```

## crates/kernel/tests/reference.rs

```text
assignments
sinks
73:     let output = std::process::Command::new("python")
calls
```

## crates/kernel/tests/refresh_round6.py

```text
assignments
4: ROOT = Path(__file__).resolve().parents[3]
4: BASE = ROOT / '数据/样例'
4: E = ROOT / 'crates/kernel/evidence/round6'
5: BIN = ROOT / 'target/release/kernel'
5: CFG = ROOT / '规格/内核配置-v1.json'
13: path = E / 'migration-plan.json'
17: source = BASE / p.name.replace('-周期证书-kernel', '')
28: dest = Path(row['path'])
46: record = build_record(raw, ticks, read(BASE / '混做粉碎机两下游-黄金轨迹.json') if name.startswith('混做') else None)
sinks
7: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
17: p.name.replace('-周期证书-kernel', '')
34: temp.replace(dest)
calls
9: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
22: save(path, d)
30: run(['cycle', row['input'], '--max-ticks', row['budget']['max_ticks'], '--max-sweeps', row['budget']['max_sweeps'], '--search-checkpoint-interval', 32, '--no-record', '--out', temp])
31: run(['verify-cycle', temp])
33: run(['run', row['input'], '--ticks', row['ticks'], '--format', row['format'], '--checkpoint-interval', row['interval'], '--out', temp])
33: run(['verify-record', temp])
37: save(E / f'migration-{kind}.json', dict(status='pass', results=results))
47: save(BASE / (name + '-运行记录-v3.json'), record)
```

## crates/kernel/tests/revision_audit.py

```text
assignments
9: ROOT = Path(__file__).resolve().parents[3]
10: KERNEL = ROOT / 'crates/kernel'
11: EVIDENCE = KERNEL / 'evidence/revision-r1'
31: path = ROOT / f'数据/样例/{name}-{suffix}.json'
88: path = (doc.parent / target.split('#')[0]).resolve()
sinks
21: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
29: verifier.run(data)
64: write(EVIDENCE / 'record-validation.json', {'status': '通过', 'records': records})
100: write(EVIDENCE / 'final-audit.json', {'status': '通过', 'baseline_files': len(baseline), 'protected_files_unchanged': len(baseline) - len(changes), 'changed_existing_files': changes, 'outside_allowed_changes': [], 'workspace_tests_passed': 93, 'workspace_tests_failed': 0, 'rust_functions_with_section_comments': function_count, 'documentation_links_checked': links, 'reader_audit': '修订记录、README与规格疑问的范围、时点、数字及交叉引用已重读核对', 'golden_and_reference_tests_unchanged': True, 'formal_sources_and_candidate_unchanged': True, 'open_items': ['KQ-02：after_closure记录起点契约待规格线澄清；当前输出入口明确unresolved']})
112: write(manifest, {'scope': '第1轮修订新增或修改的源文件、文档、运行记录和验证证据；不含构建缓存与已清理临时文件', 'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(files)], 'manifest_path': str(manifest)})
120: main()
```

## crates/kernel/tests/revision_cli.py

```text
assignments
11: ROOT = Path(__file__).resolve().parents[3]
12: EVIDENCE = ROOT / 'crates/kernel/evidence/revision-r2'
13: OUT = EVIDENCE / 'tmp'
14: CONFIG = ROOT / '规格/内核配置-v1.json'
15: BIN = Path(sys.argv[1]).resolve()
25: path = OUT / (name + '-record.json')
41: source = ROOT / f'数据/样例/{sample}.json'
73: source = ROOT / '数据/样例/混做粉碎机两下游.json'
102: OUT = Path(directory)
sinks
20: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
38: OUT.mkdir(parents=True, exist_ok=True)
100: OUT.mkdir(parents=True, exist_ok=True)
calls
28: subprocess.run(command, capture_output=True, text=True, timeout=30)
43: verifier.run(data)
46: invoke(source, name, ticks, format_name)
65: write(bad_path, bad)
82: invoke(source, 'restart-source', 2)
89: write(input_path, data)
90: invoke(input_path, name, 2)
95: write(EVIDENCE / 'prior-regression-results.json', result)
103: main()
```

## crates/kernel/tests/revision_cli.rs

```text
assignments
sinks
8:     let output = Command::new("python")
calls
```

## crates/kernel/tests/revision_r2_audit.py

```text
assignments
8: ROOT = Path(__file__).resolve().parents[3]
9: KERNEL = ROOT / 'crates/kernel'
10: OUT = KERNEL / 'evidence/revision-r2'
80: path = (doc.parent / target.split('#')[0]).resolve()
sinks
20: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
52: verifier.run(data)
95: write('final-audit.json', {'status': '通过', 'baseline_files': len(baseline), 'protected_files_unchanged': len(protected), 'changed_existing_files': [str(p) for p in sorted(changed)], 'outside_allowed_changes': [], 'workspace_tests_passed': 102, 'workspace_tests_failed': 0, 'original_golden_and_reference_bytes_unchanged': True, 'formal_sources_and_candidate_bytes_unchanged': True, 'prior_review_and_evidence_bytes_unchanged': True, 'records_recomputed_and_verified': len(records), 'python_metadata_negatives': 60, 'python_summary_controls': 4, 'rust_metadata_negatives': 32, 'findings_addressed': findings, 'rust_functions_with_section_comments': functions, 'documentation_links_checked': links, 'reader_audit': '已重读README、按轮追记的修订记录与规格疑问；现行数字、历史时点、条件论证、停止范围及交叉引用一致。', 'open_items': ['KQ-06：固定分支失活后的绑定及后继机制未定；当前明确unresolved，不交付不闭合后态。', '既有KQ-01至KQ-05继续保留；尤其KQ-02的after_closure输出仍unresolved。']})
112: write('deliverables.json', {'scope': '第2轮新增/修改的源码、测试、夹具、文档、运行记录与证据；不含构建缓存、已清理临时文件，清单不自哈希。', 'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(deliverables)], 'manifest_path': str(manifest)})
121: main()
```

## crates/kernel/tests/revision_r2_cli.py

```text
assignments
10: ROOT = Path(__file__).resolve().parents[3]
11: EVIDENCE = ROOT / 'crates/kernel/evidence/revision-r2'
12: CONFIG = ROOT / '规格/内核配置-v1.json'
13: BIN = Path(sys.argv[1]).resolve()
48: source = ROOT / f'数据/样例/{name}.json'
52: path = out / f'{name}-{format_name}.json'
91: source = ROOT / '数据/样例/混做粉碎机两下游.json'
129: path = out / f'{name}-input.json'
sinks
18: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
145: EVIDENCE.mkdir(exist_ok=True)
calls
28: subprocess.run(command, text=True, capture_output=True, timeout=30)
50: verifier.run(data)
53: invoke(source, path, ticks, format_name)
82: write(bad_path, bad)
93: invoke(source, out / 'restart.json', 2)
130: write(path, data)
131: invoke(path, out / f'{name}-record.json', 2, no_output=no_output)
139: write(EVIDENCE / 'regression-results.json', result)
147: main(Path(directory))
```

## crates/kernel/tests/revision_r2_cli.rs

```text
assignments
sinks
8:     let output = Command::new("python")
calls
```

## crates/kernel/tests/revision_r3_cli.py

```text
assignments
11: ROOT = Path(__file__).resolve().parents[3]
12: OUT = ROOT / 'crates/kernel/evidence/round6/regressions/revision-r3'
13: BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
14: CFG = ROOT / '规格/内核配置-v1.json'
23: path = OUT / (name + '.json')
29: path = ROOT / '数据/样例' / (name + '.json')
37: out = OUT / (name + '-result.json')
sinks
24: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
38: out.unlink(missing_ok=True)
66: OUT.mkdir(parents=True, exist_ok=True)
98: value.replace('/', '_')
calls
42: subprocess.run(command, capture_output=True, text=True, timeout=90)
57: save(name + '-input', raw)
60: invoke(name + '-' + mode, mode, path, expected)
68: invoke('bridge-control', 'run', save('bridge-input', original), 'completed', ticks=7)
68: save('bridge-input', original)
71: save('checkpoint-control', checkpoint)
72: invoke('checkpoint-seed', 'seed', path, 'kernel-input-v3')
74: invoke('checkpoint-run', 'run', path, 'completed', ticks=1)
75: invoke('checkpoint-derived-run', 'run', OUT / 'checkpoint-seed-result.json', 'completed', ticks=1)
123: save('age-overflow-input', raw)
124: invoke('age-overflow-run', 'run', path, 'inconclusive')
125: invoke('age-overflow-cycle', 'cycle', path, 'inconclusive')
133: invoke('legacy-late-window-cycle', 'verify-cycle', legacy, 'invalid_input')
136: save('legacy-late-window-record', read(legacy)['run_record'])
137: invoke('legacy-late-window-record', 'verify-record', embedded, 'invalid_input')
140: save('results', result)
145: main()
```

## crates/kernel/tests/revision_r3_cli.rs

```text
assignments
sinks
6:     let output = Command::new("python")
calls
```

## crates/kernel/tests/revision_r4_cli.py

```text
assignments
10: ROOT = Path(__file__).resolve().parents[3]
11: OUT = ROOT / 'crates/kernel/evidence/revision-r4/cli'
12: BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
13: CFG = ROOT / '规格/内核配置-v1.json'
21: path = OUT / (name + '.json')
27: path = ROOT / f'数据/样例/{name}.json'
39: output = OUT / (name + '-result.json')
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
35: OUT.mkdir(parents=True, exist_ok=True)
calls
43: subprocess.run(command, capture_output=True, text=True, timeout=90)
60: invoke('age-cohorts-seed', 'seed', save('age-cohorts-input', raw), 'kernel-input-v3')
60: save('age-cohorts-input', raw)
62: invoke('age-cohorts-run', 'run', path, 'completed', '--ticks', '3')
69: invoke('empty-branch-seed', 'seed', save('empty-branch-input', raw), 'kernel-input-v3')
69: save('empty-branch-input', raw)
70: invoke('empty-branch-run', 'run', path, 'completed', '--ticks', '12')
71: invoke('full-branch-run', 'run', save('full-branch-input', source('分流器三路轮询')), 'completed', '--ticks', '12')
71: save('full-branch-input', source('分流器三路轮询'))
79: invoke('working-prefix', 'run', save('working-input', original), 'completed', '--ticks', '12')
79: save('working-input', original)
83: save('extra-trigger-input', original)
85: invoke('extra-trigger-' + mode, mode, path, 'invalid_input')
88: invoke('closed-prefix', 'run', save('closed-input', source('混做粉碎机两下游')), 'completed', '--ticks', '2')
88: save('closed-input', source('混做粉碎机两下游'))
92: invoke('closed-seed', 'seed', save('closed-checkpoint-input', raw), 'kernel-input-v3')
92: save('closed-checkpoint-input', raw)
95: invoke('closed-stop-' + fmt, 'run', path, 'inconclusive', '--ticks', '1', '--max-sweeps', '1', '--format', fmt)
101: invoke('path-runs', 'run', save('path-runs-input', source('阻尼连续带核验')), 'completed', '--ticks', '3')
101: save('path-runs-input', source('阻尼连续带核验'))
104: subprocess.run([str(BIN), 'verify-record', str(path), '--config', str(CFG)], capture_output=True, text=True)
107: subprocess.run([str(BIN), 'verify-record', str(save('forged-adjacency', record)), '--config', str(CFG)], capture_output=True, text=True)
107: save('forged-adjacency', record)
113: invoke('age-overflow-cycle', 'cycle', save('age-overflow-input', raw), 'inconclusive')
113: save('age-overflow-input', raw)
124: subprocess.run(['node', '-e', script, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], input=json.dumps(dict(schema=read(schema_path), documents=documents)), capture_output=True, text=True, check=True)
134: save('results', report)
139: main()
```

## crates/kernel/tests/revision_r4_cli.rs

```text
assignments
sinks
6:     let result = Command::new("python")
calls
```

## crates/kernel/tests/revision_r5_cli.py

```text
assignments
16: ROOT = Path(__file__).resolve().parents[3]
17: BASE = ROOT / '数据/样例'
18: E = ROOT / 'crates/kernel/evidence/round6/revision-r5/cli'
19: BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
20: CFG = ROOT / '规格/内核配置-v1.json'
57: source = BASE / '生产循环环带.json'
61: record = read(Path(cycle['run_record_ref']['path']))
sinks
29: path.parent.mkdir(parents=True, exist_ok=True)
30: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
37: (E / (name + '.log')).write_text(json.dumps(dict(command=command, cwd=str(cwd), exit=result.returncode), ensure_ascii=False) + '\n' + result.stdout + result.stderr)
55: E.mkdir(parents=True, exist_ok=True)
118: (E / 'bounded-reference-batch-unsupported.log').write_text(rejected.stderr)
calls
36: subprocess.run(command, cwd=cwd, capture_output=True, text=True)
59: call('generate-cycle', 'cycle', source, '--max-ticks', 50, '--out', certificate)
69: save(directory / 'record.json', relative_record(given, directory))
72: call(encoding + '-verify-' + label, 'verify-record', relative, cwd=cwd)
74: call(encoding + '-checkpoint', 'checkpoint', relative, '--out', resumed, cwd=ROOT.parent)
77: call(encoding + '-continue', 'run', resumed, '--ticks', 2, '--out', continuation)
91: save(cert_dir / 'cycle.json', cert)
93: call(encoding + '-cycle-verify', 'verify-cycle', cert_path, cwd=ROOT.parent)
94: call(encoding + '-cycle-checkpoint', 'checkpoint', cert_path, '--out', E / (encoding + '-cycle-input.json'))
95: call('relative-production-batch', 'verify-batch', package, cwd=ROOT.parent)
103: call(name + '-finite', 'run', BASE / (name + '.json'), '--ticks', len(expected), '--out', generated)
107: save(reference_dir / (name + '-' + encoding + '.json'), relative_record(given, reference_dir))
109: call(name + '-' + encoding, 'verify-record', p, cwd=ROOT.parent)
111: save(E / 'bounded-reference-package' / (name + '-reference.json'), relative_record(bounded, E / 'bounded-reference-package'))
113: call('relative-reference-batch', 'verify-batch', reference_dir, cwd=ROOT.parent)
114: subprocess.run([str(BIN), 'verify-batch', str(E / 'bounded-reference-package'), '--config', str(CFG)], cwd=ROOT.parent, capture_output=True, text=True)
133: save(E / f'ore-{quantity}-raw.json', raw)
135: call(f'ore-{quantity}-seed', 'seed', raw_path, '--out', seed_path)
137: call(f'ore-{quantity}-finite', 'run', seed_path, '--ticks', 2, '--out', E / f'ore-{quantity}-finite.json')
142: save(E / 'ore-crossed-seed.json', crossed)
146: call(f'ore-{label}-domain', 'check', seed_path, '--cycle-domain', code=2)
151: call(f'ore-{label}-cycle', 'cycle', seed_path, '--max-ticks', 2, '--no-record', '--out', shell, code=2)
153: call(f'ore-{label}-verify', 'verify-cycle', shell)
156: save(E / 'ore-memory-comparison.json', dict(finite_memory_equal=False, memories=memories, production_stop='cycle.domain.D2', scope='两种有限容量与交叉游标；生产装载先于可动级校验停止'))
172: save(E / (kind + '-input.json'), bad)
174: call(kind + '-shell-generate', 'cycle', bad_path, '--max-ticks', 2, '--out', shell, code=2)
175: call(kind + '-diagnostic', 'verify-cycle', shell)
178: call(kind + '-checkpoint', 'checkpoint', shell, '--out', rejected, code=2)
185: call('zero-generate', 'cycle', source, '--max-ticks', 2, '--max-sweeps', 1, '--no-record', '--out', zero)
187: call('zero-checkpoint', 'checkpoint', zero, '--out', checkpoint)
200: save(E / 'negative' / (name + '.json'), bad)
201: call('reject-' + name, 'verify-record', p, code=2, cwd=ROOT.parent)
203: save(E / 'results.json', dict(status='pass', cases=CASES, positive_schema_documents=len(positives)))
208: main()
```

## crates/kernel/tests/revision_r5_cli.rs

```text
assignments
sinks
6:     let result = Command::new("python")
calls
```

## crates/kernel/tests/round5_cli.rs

```text
assignments
sinks
15:     std::fs::create_dir_all(&out).unwrap();
17:     let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
22:         .arg("--out")
31:     let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
48:     let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
61:     std::fs::write(
68:     std::fs::write(&input, json!({"schema":"kernel-input-v3"}).to_string()).unwrap();
69:     let process = Command::new(env!("CARGO_BIN_EXE_kernel"))
74:         .args(["--max-ticks", "2", "--out"])
calls
```

## crates/kernel/tests/round5_scenarios.py

```text
assignments
6: OUT = ROOT / '数据/样例'
9: BIN = ROOT / 'target/release/kernel'
9: CONFIG = ROOT / '规格/内核配置-v1.json'
17: source = OUT / (name + '.json')
23: record = OUT / (name + '-运行记录-v3-kernel.json')
sinks
22: source.write_bytes(canonical.read_bytes())
22: canonical.unlink()
calls
17: save(source, d)
20: subprocess.run(cmd, capture_output=True, text=True)
24: subprocess.run([str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(record)], capture_output=True, text=True)
29: subprocess.run([str(BIN), 'cycle', str(source), '--config', str(CONFIG), '--max-ticks', str(ticks), '--out', str(cert)], capture_output=True, text=True)
45: b.generate('研磨混做核验', [unit('grinder', '研磨机', 10, 10), unit('feed_a', '协议储存箱', 9, 6), unit('feed_b', '协议储存箱', 13, 6), unit('belt_a', '传送带', 10, 9), unit('belt_b', '传送带', 14, 9), unit('belt_out', '传送带', 10, 14), unit('sink', '协议储存箱', 10, 15), unit('power', '供电桩', 17, 12)])
56: b.generate('生产循环环带', [unit('a', '传送带', 10, 10, 'r90', 1), unit('b', '传送带', 10, 11, 'r0', 1), unit('c', '传送带', 11, 11, 'r270', 1), unit('d', '传送带', 11, 10, 'r180', 1), unit('box', '协议储存箱', 15, 10), unit('power', '供电桩', 19, 10)])
66: b.generate('轮询均分核验', units)
87: b.generate('密集结点核验', units)
91: main()
```

## crates/kernel/tests/round6_cli.py

```text
assignments
7: ROOT = Path(__file__).resolve().parents[3]
7: E = ROOT / 'crates/kernel/evidence/round6/cli'
8: BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
8: CFG = ROOT / '规格/内核配置-v1.json'
8: BASE = ROOT / '数据/样例'
52: record = read(Path(r['run_record_ref']['path']))
62: record = read(Path(zero['run_record_ref']['path']))
73: source = save(E / 'overflow-input.json', raw)
sinks
7: E.mkdir(parents=True, exist_ok=True)
10: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
54: changed.unlink()
56: mutated.write_bytes(original.read_bytes() + b' ')
83: (E / 'tamper.json').unlink()
83: (E / 'mutated-input.json').unlink()
calls
12: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True, cwd=cwd)
18: call('cycle', BASE / '生产循环环带.json', '--max-ticks', 50, '--out', cert, *flags)
20: call('verify-cycle', cert, cwd=ROOT.parent)
29: save(E / (mode + '-relative.json'), relative)
29: call('verify-cycle', p, cwd=ROOT.parent)
50: call('verify-cycle', save(E / 'tamper.json', bad), ok=False)
50: save(E / 'tamper.json', bad)
53: save(E / 'tampered-record.json', record)
54: call('verify-cycle', save(E / 'tamper.json', bad), ok=False)
54: save(E / 'tamper.json', bad)
57: call('verify-cycle', save(E / 'tamper.json', bad), ok=False)
57: save(E / 'tamper.json', bad)
59: call('cycle', BASE / '生产循环环带.json', '--max-ticks', 2, '--max-sweeps', 1, '--out', p, *flags)
60: call('verify-cycle', p)
65: call('checkpoint', E / 'none.json', '--out', checkpoint)
67: call('cycle', checkpoint, '--no-record', '--max-ticks', 25, '--out', continued)
67: call('verify-cycle', continued)
73: save(E / 'overflow-input.json', raw)
73: call('cycle', source, '--max-ticks', 2, '--out', shell, ok=False)
75: call('verify-cycle', shell)
79: call('verify-cycle', save(E / 'tamper.json', forged), ok=False)
79: save(E / 'tamper.json', forged)
81: call('check', BASE / '生产循环环带.json', '--cycle-domain')
81: save(E / 'domain-static.json', static)
85: save(E / 'results.json', report)
```

## crates/kernel/tests/round6_cli.rs

```text
assignments
sinks
5:     let result = Command::new("python")
calls
```

## crates/kernel/tests/scope_revision_r3.py

```text
assignments
10: ROOT = Path(__file__).resolve().parents[4]
11: SOLVER = ROOT / '求解器'
12: KERNEL = SOLVER / 'crates/kernel'
13: OUT = KERNEL / 'evidence/revision-r3'
55: path = ROOT / relative
87: path = (doc.parent / target.split('#')[0]).resolve()
97: path = SOLVER / name
111: path = OUT / name
sinks
25: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
109: write('范围审计.json', scope)
116: write('交付清单.json', dict(schema='kernel-revision-r3-files-v1', changes=changes, nonrecursive_files=sorted(map(str, nonrecursive)), cleanup_manifest=str(OUT / 'cleanup.json'), counts={action: sum((c['action'] == action for c in changes)) for action in ['added', 'modified', 'deleted']}))
124: main()
```

## crates/kernel/tests/variants_round5.py

```text
assignments
5: base = read(s.OUT / '轮询均分核验.json')
sinks
calls
13: write(s.ROOT / 'crates/kernel/evidence/round5/polling-six-orders.json', dict(status='pass', cases=results, scope='同一已核前件下六种局部顺序；没有替代judgment.order全域约减'))
```

## crates/kernel/tests/verify_all.py

```text
assignments
7: ROOT = Path(__file__).resolve().parents[3]
10: BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
11: AJV = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
50: source = next(((path.parent / row['path']).resolve() for row in data['fingerprints'] if row['role'] == 'input'))
sinks
calls
15: subprocess.run(['node', '-e', script, AJV], input=json.dumps(dict(schema=str(ROOT / '规格/内核输出.schema.json'), paths=[str(p) for p in paths])), capture_output=True, text=True)
33: subprocess.run([str(BIN), 'verify-cycle', str(path.resolve()), '--config', str(args.config.resolve())], capture_output=True, text=True)
47: subprocess.run([str(BIN), mode, str(path.resolve()), '--config', str(args.config.resolve())], capture_output=True, text=True)
58: main()
```

## crates/kernel/tests/verify_outputs.py

```text
assignments
9: ROOT = Path(__file__).resolve().parents[3]
70: path = (base / row['path']).resolve(strict=True)
84: record = canonical_record_paths(record, path.parent)
sinks
133: (ROOT / 'crates/kernel/evidence/round5/record-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
126: run(data)
138: main()
```

## crates/kernel/复核/probe/tamper.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
sinks
17: tmp.parent.mkdir(parents=True, exist_ok=True)
21: tmp.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
calls
13: run(data)
```

## crates/kernel/复核/r1-工程-evidence/reproduce.py

```text
assignments
14: OUT = Path(__file__).resolve().parent
15: ROOT = OUT.parents[3]
16: BIN = OUT / 'target/release/kernel'
17: CONFIG = ROOT / '规格/内核配置-v1.json'
18: SAMPLES = ROOT / '数据/样例'
25: path = OUT / name
41: record = OUT / (name + '-record.json')
86: path = SAMPLES / (name + '-' + suffix + '.json')
sinks
26: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
40: save(name + '-input.json', data)
43: subprocess.run(args, capture_output=True, text=True, timeout=30)
76: save('input-probes.json', cases)
84: module.run(original)
95: save(name + '-' + mutation + '.json', altered)
101: save('record-verifier-probes.json', checks)
105: subprocess.run(args, capture_output=True, text=True, timeout=60)
107: save('benchmark.json', {'classification': '实测', 'command': args, 'returncode': p.returncode, 'process_elapsed_ns': duration, 'result': json.loads(p.stdout), 'stderr': p.stderr, 'platform': platform.platform(), 'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(), 'binary_sha256': hashlib.sha256(BIN.read_bytes()).hexdigest(), 'input_sha256': hashlib.sha256(Path(args[2]).read_bytes()).hexdigest(), 'scope': '单次 release 1000 时刻，输出关闭，编译不计；后段阻塞，不是满载基准'})
112: main()
```

## crates/kernel/复核/r1-测试与证据/audit.py

```text
assignments
11: OUT = Path(__file__).resolve().parent
12: ROOT = OUT.parents[3]
13: KERNEL = ROOT / 'crates/kernel'
14: CONFIG = ROOT / '规格/内核配置-v1.json'
15: BINARY = OUT / 'target/debug/kernel'
27: path = OUT / name
38: target = OUT / (name + '-record.json')
61: path = ROOT / f'数据/样例/{name}-{suffix}.json'
64: base = read(ROOT / f'数据/样例/{name}-运行记录-kernel.json')
158: path = OUT / ('排列-' + name + '-record.json')
sinks
28: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
37: write(name + '-input.json', data)
40: subprocess.run(command, capture_output=True, text=True)
41: write(name + '-process.json', {'command': command, 'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
59: verify.run(data)
78: write(name + '-' + label + '.json', value)
106: write('手推同种桥接-expected.json', expected)
174: write('独立检查结果.json', report)
179: main()
```

## crates/kernel/复核/r1-规格保真-证据/probe_inputs.py

```text
assignments
8: OUT = Path(__file__).resolve().parent
9: ROOT = OUT.parents[3]
10: BASE = json.loads((ROOT / '数据/样例/混做粉碎机两下游.json').read_text())
37: source = OUT / f'{name}-input.json'
38: record = OUT / f'{name}-record.json'
sinks
39: source.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
85: (OUT / 'input-probe-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
calls
41: subprocess.run(command, capture_output=True, text=True)
90: main()
```

## crates/kernel/复核/r1-规格保真-证据/review_probes.rs

```text
assignments
sinks
59:     std::fs::write(&path, serde_json::to_string_pretty(&raw).unwrap()).unwrap();
89:     std::fs::write(&input_path, serde_json::to_string_pretty(&raw).unwrap()).unwrap();
96:     std::fs::write(dir.join("fixed-branch-dynamic-tick.json"), serde_json::to_string_pretty(&tick).unwrap()).unwrap();
calls
```

## crates/kernel/复核/r2-工程证据/probes.py

```text
assignments
4: ROOT = pathlib.Path(__file__).resolve().parents[4]
5: OUT = pathlib.Path(__file__).resolve().parent
6: BIN = OUT / 'target/release/kernel'
20: path = OUT / (name + '-input.json')
20: output = OUT / (name + '-record.json')
35: base = verifier.checker.load_json(ROOT / '数据/样例/混做粉碎机两下游.json')
sinks
12: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
20: write(path, data)
23: subprocess.run(command, capture_output=True, text=True, timeout=30)
36: invoke('control', base)
38: invoke(name, data)
39: invoke('initial-unlisted-missing', data)
40: invoke('initial-unlisted-filled', data)
44: invoke('restart-control', restart, no_output=True)
47: invoke(name, data, no_output=True)
48: write(OUT / 'input-probes.json', results)
50: subprocess.run(command, capture_output=True, text=True, timeout=30)
51: write(OUT / 'benchmark.json', {'command': command, 'platform': platform.platform(), 'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(), 'process_ns': elapsed, 'exit_code': process.returncode, 'stdout': json.loads(process.stdout), 'stderr': process.stderr, 'binary_sha256': hashlib.sha256(BIN.read_bytes()).hexdigest(), 'input_sha256': hashlib.sha256((ROOT / 'crates/kernel/tests/fixtures/benchmark_1000.json').read_bytes()).hexdigest()})
54: main()
```

## crates/kernel/复核/r2-工程证据/replay_cli.py

```text
assignments
6: ROOT = Path(__file__).resolve().parents[4]
7: OUT = Path(__file__).resolve().parent
8: TESTS = ROOT / 'crates/kernel/tests'
11: SPEC = importlib.util.spec_from_file_location('review_cli', TESTS / 'revision_cli.py')
sinks
calls
16: MODULE.main()
```

## crates/kernel/复核/r2-工程证据/verify_artifacts.py

```text
assignments
4: ROOT = pathlib.Path(__file__).resolve().parents[4]
5: OUT = pathlib.Path(__file__).resolve().parent
19: source = ROOT / f'数据/样例/{name}-{suffix}.json'
28: path = OUT / f'{name}-{suffix}-{case}.json'
32: evidence = ROOT / 'crates/kernel/evidence/revision-r1'
sinks
28: path.write_text(json.dumps(bad, ensure_ascii=False, indent=2) + '\n')
51: (OUT / 'artifact-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
17: verifier.run(data)
53: main()
```

## crates/kernel/复核/r2-测试与证据/audit.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: ROOT = HERE.parents[4]
13: SOLVER = ROOT / '求解器'
14: KERNEL = SOLVER / 'crates/kernel'
15: BIN = HERE / 'target/debug/kernel'
16: CONFIG = SOLVER / '规格/内核配置-v1.json'
26: path = HERE / name
43: output = HERE / (name + '-record.json')
74: path = SOLVER / f'数据/样例/{name}-{suffix}.json'
133: source = SOLVER / '数据/样例/混做粉碎机两下游.json'
sinks
27: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
45: subprocess.run(command, text=True, capture_output=True, timeout=45)
46: write(name + '-process.json', {'command': command, 'exit_code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
72: verifier.run(data)
96: write(name + '-' + suffix + '-' + kind + '.json', record)
111: write(name + '-control-input.json', data)
112: invoke(path, name + '-control', ticks)
113: invoke(path, name + '-repeat', ticks)
124: write(f'{name}-shuffle-{seed}-input.json', shuffled)
125: invoke(moved, f'{name}-shuffle-{seed}', ticks)
136: write('手推-关闭粉碎机-input.json', data)
150: write('手推-关闭粉碎机-expected.json', expected)
151: invoke(path, '手推-关闭粉碎机', 4)
169: write('手推-关闭粉碎机-actual-projection.json', projections)
176: write('audit-results.json', results)
181: main()
```

## crates/kernel/复核/r2-测试与证据/check_stops_and_invariants.py

```text
assignments
34: source = __import__('pathlib').Path(old['input'])
37: output = HERE / ('replay-' + source.stem + '.json')
51: record = load(SOLVER / f'数据/样例/{name}-运行记录-kernel.json')
sinks
calls
27: subprocess.run(command, capture_output=True, text=True, timeout=15)
39: subprocess.run(command, capture_output=True, text=True, timeout=30)
75: write('stops-and-invariants.json', {'request_stops': stops, 'old_probes': replay, 'independent_inventory': invariant})
80: main()
```

## crates/kernel/复核/r3-工程证据/benchmark_replay.py

```text
assignments
4: R = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: O = R / 'crates/kernel/复核/r3-工程证据'
4: B = R / 'target/release/kernel'
4: C = R / '规格/内核配置-v1.json'
sinks
17: (O / '性能复现.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
11: subprocess.run(cmd, capture_output=True, text=True)
```

## crates/kernel/复核/r3-工程证据/cli_probes.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
8: OUT = ROOT / 'crates/kernel/复核/r3-工程证据'
9: BIN = ROOT / 'target/release/kernel'
10: CONFIG = ROOT / '规格/内核配置-v1.json'
21: path = OUT / (name + '.json')
51: source = ROOT / '数据/样例/混做粉碎机两下游.json'
sinks
14: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
28: result_path.unlink(missing_ok=True)
calls
22: write(path, data)
32: subprocess.run(cmd, capture_output=True, text=True)
64: invoke(name, 'seed' if kind == 'seed' else 'run', path, [] if kind == 'seed' else ['--ticks', '1'])
74: invoke(mode + '-load-age-overflow', mode, path, ['--ticks', '2'])
76: invoke(mode + '-one-sweep', mode, ring, ['--ticks', '2', '--max-sweeps', '1'] + (['--no-output'] if mode == 'run' else []))
79: invoke(mode + '-adequate-sweeps', mode, ring, ['--ticks', '2', '--max-sweeps', '1000'] + (['--no-output'] if mode == 'run' else []))
82: invoke('relocated-input', 'seed', source)
84: invoke('relocated-run', 'run', OUT / 'relocated-input-result.json', ['--ticks', '4', '--no-output'])
86: write(OUT / 'CLI探针汇总.json', reports)
92: main()
```

## crates/kernel/复核/r3-工程证据/read_audit.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh')
5: OUT = ROOT / '求解器/crates/kernel/复核/r3-工程证据'
sinks
39: (OUT / '全量读取与指纹.json').write_text(json.dumps({'files': rows, 'kernel_manifest_entries': len(km['files']), 'manifest_mismatches': bad}, ensure_ascii=False, indent=2) + '\n')
49: (OUT / '证据目录扫描.json').write_text(json.dumps(scan, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/r3-工程证据/read_records.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
8: OUT = ROOT / 'crates/kernel/复核/r3-工程证据'
18: path = ROOT / '数据/样例' / (name + '-' + suffix + '.json')
22: source = json.loads((ROOT / 'crates/kernel/evidence/round5/audit-results.json').read_text())
26: path = Path(entry['path'])
44: path = Path(entry['path'])
sinks
20: (OUT / '双参考完整验收.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
39: (OUT / '全部记录台账重核.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
68: (OUT / '全部周期结果重核.json').write_text(json.dumps(cycles, ensure_ascii=False, indent=2) + '\n')
calls
16: verify.run(data)
```

## crates/kernel/复核/r3-工程证据/read_references.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh')
8: OUT = ROOT / '求解器/crates/kernel/复核/r3-工程证据'
9: TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
10: MEETING = Path('/home/zhuran24/文档/会议2全套/会议目录')
sinks
47: (OUT / '引用文件读取清点.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/r3-测试与证据/core_ledger_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: BIN = ROOT / 'target/release/kernel'
4: CFG = ROOT / '规格/内核配置-v1.json'
9: dest = OUT / 'core-ledger-record.json'
sinks
9: src.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
16: (OUT / 'core-ledger-results.json').write_text(json.dumps({'status': 'pass', 'commands': commands, 'ticks': 4, 'core_inbound': core, 'wireless_inbound': [], 'per_species_conservation': True}, ensure_ascii=False, indent=2) + '\n')
calls
12: subprocess.run(cmd, text=True, capture_output=True)
```

## crates/kernel/复核/r3-测试与证据/coverage_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: BASE = ROOT / '数据/样例'
10: record = read(BASE / (name + '-运行记录-v3-kernel.json'))
sinks
53: (OUT / 'coverage-raw-samples.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/r3-测试与证据/generator_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
sinks
7: b.b.OUT.mkdir(exist_ok=True)
15: (OUT / 'generator-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
calls
10: b.generate(name, m, l, c)
12: subprocess.run(cmd, capture_output=True, text=True)
```

## crates/kernel/复核/r3-测试与证据/manual_cycle.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
5: path = ROOT / '数据/样例/生产循环环带-周期证书-kernel.json'
sinks
57: (OUT / 'manual-cycle-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/r3-测试与证据/phase_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: CFG = ROOT / '规格/内核配置-v1.json'
4: BIN = ROOT / 'target/release/kernel'
11: dest = OUT / f'phase-{name}-record.json'
17: source = ROOT / '数据/样例/生产循环环带.json'
22: dest = OUT / 'phase-malformed-cycle-result.json'
sinks
11: src.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
15: (OUT / 'phase-probe-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
22: src.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
25: (OUT / 'phase-malformed-cycle-check.json').write_text(json.dumps({'command': command, 'exit_code': p.returncode, 'status': result['status'], 'period': result['cycle']['period'] if result['cycle'] else None, 'input_axis': result['parameter_point']['input_axes']['transfer.phase'] if result['parameter_point'] else None, 'verify_exit_code': verification.returncode, 'verify_stdout': verification.stdout, 'verify_stderr': verification.stderr}, ensure_ascii=False, indent=2) + '\n')
calls
12: subprocess.run(command, text=True, capture_output=True)
23: subprocess.run(command, text=True, capture_output=True)
24: subprocess.run([str(BIN), 'verify-cycle', str(dest), '--config', str(CFG)], text=True, capture_output=True)
```

## crates/kernel/复核/r3-测试与证据/recheck.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
5: OUT = Path(__file__).resolve().parent
31: source = ROOT / f'crates/kernel/tests/fixtures/{name}.json'
43: path = OUT / f'{name}-重跑周期.json'
sinks
9: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
11: subprocess.run([str(c) for c in command], capture_output=True, text=True)
18: v.run(data)
23: save('verify-outputs.json', {'status': 'pass', 'records': reports, 'protected_files': len(baseline)})
26: save('invalid-cycle-result.json', json.loads((OUT / 'cli-r5/invalid-cycle-result.json').read_text()))
27: a.main()
33: run([binary, 'run', source, '--config', ROOT / '规格/内核配置-v1.json', '--ticks', '12', '--no-output'])
39: save('benchmark-recheck.json', {'platform': platform.platform(), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'reports': reports, 'scope': '沿用原12刻、无输出推进口径，5次独立进程；wall_ns另列，不含于ms/tick。'})
44: run([ROOT / 'target/release/kernel', 'cycle', ROOT / f'数据/样例/{name}.json', '--config', ROOT / '规格/内核配置-v1.json', '--max-ticks', budget, '--out', path])
46: run([ROOT / 'target/release/kernel', 'verify-cycle', path, '--config', ROOT / '规格/内核配置-v1.json'])
48: save('cycle-recheck.json', results)
```

## crates/kernel/复核/r3-测试与证据/reproduce_cargo.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
sinks
6: (OUT / name).mkdir(exist_ok=True)
13: (OUT / (mode + '-command.json')).write_text(json.dumps({'command': command, 'exit_code': p.returncode, 'redirected_outputs_only': True}, ensure_ascii=False, indent=2) + '\n')
calls
12: subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
```

## crates/kernel/复核/r3-测试与证据/seed_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: BIN = ROOT / 'target/release/kernel'
4: CFG = ROOT / '规格/内核配置-v1.json'
6: source = ROOT / '数据/样例/桥接器双通路.json'
6: record = json.loads((ROOT / '数据/样例/桥接器双通路-运行记录-v3-kernel.json').read_text())
15: path = OUT / f'seed-{case}-input.json'
18: dest = OUT / f'seed-{case}-{op}.json'
sinks
5: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
15: save(path, d)
19: subprocess.run(command, capture_output=True, text=True)
26: save(OUT / 'seed-probe-results.json', reports)
```

## crates/kernel/复核/r3-测试与证据/supply_differential.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: BIN = ROOT / 'target/release/kernel'
4: CFG = ROOT / '规格/内核配置-v1.json'
23: source = ROOT / f'数据/样例/{sample}.json'
31: path = OUT / f'diff-{sample}-{mode}.json'
31: dest = OUT / f'diff-{sample}-{mode}-record.json'
sinks
5: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
31: save(path, d)
33: subprocess.run(cmd, text=True, capture_output=True)
34: subprocess.run(cmd, text=True, capture_output=True)
50: save(OUT / 'supply-differential-results.json', reports)
```

## crates/kernel/复核/r3-测试与证据/write_report.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
4: REPORT = OUT.parent / '复核-r3-测试与证据.md'
sinks
18: (OUT / 'findings.json').write_text(json.dumps(findings, ensure_ascii=False, indent=2) + '\n')
172: REPORT.write_text(text)
calls
```

## crates/kernel/复核/r3-规格保真-证据/audit_artifacts.py

```text
assignments
10: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
11: OUT = Path(__file__).resolve().parent
20: SCHEMA = json.loads((ROOT / '规格/内核输出.schema.json').read_text())
32: path = Path(row['path'])
sinks
118: (OUT / '既有产物字段与台账复核.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
122: main()
```

## crates/kernel/复核/r3-规格保真-证据/positive_checks.py

```text
assignments
17: record = call('positive-' + name, 'run', ROOT / '数据/样例' / (name + '.json'), '--ticks', ticks)
26: path = ROOT / 'crates/kernel/tests/fixtures/core_inbound.json'
sinks
calls
17: call('positive-' + name, 'run', ROOT / '数据/样例' / (name + '.json'), '--ticks', ticks)
19: call('positive-verify-' + name, 'verify-record', OUT / ('positive-' + name + '.json'))
21: call('positive-ring-cycle', 'cycle', ROOT / '数据/样例/生产循环环带.json', '--max-ticks', 50)
23: call('positive-ring-verification', 'verify-cycle', OUT / 'positive-ring-cycle.json')
34: save(f'ore-return-{quantity}-input', data)
35: call(f'ore-return-{quantity}-seed', 'seed', initial)
38: call(f'ore-return-{quantity}-cycle', 'cycle', canonical, '--max-ticks', 2)
40: call(f'ore-return-{quantity}-concrete', 'run', canonical, '--ticks', 2)
44: call('zero-ore-runtime-rejection', 'run', OUT / 'zero-ore-sufficient-seed.json', '--ticks', 1)
46: save('positive-check-results', {'status': '通过', 'cases': RESULTS})
50: main()
```

## crates/kernel/复核/r3-规格保真-证据/probe.py

```text
assignments
9: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
10: OUT = Path(__file__).resolve().parent
11: BIN = ROOT / 'target/debug/kernel'
12: CFG = ROOT / '规格/内核配置-v1.json'
19: path = OUT / (name + '.json')
24: path = ROOT / '数据/样例' / (name + '.json')
34: output = OUT / (name + '.json')
sinks
20: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
41: (OUT / (name + '.log')).write_text(json.dumps(RESULTS[-1], ensure_ascii=False, indent=2) + '\n')
calls
36: subprocess.run(cmd, capture_output=True, text=True, timeout=90)
47: save('crusher-input', raw)
48: call('crusher-control', 'run', base, '--ticks', 4)
51: save('checkpoint-control-input', raw)
52: call('checkpoint-control-seed', 'seed', checkpoint)
55: call('checkpoint-control-run', 'run', checkpoint, '--ticks', 2)
59: save('检查点续跑逐字段对照', matches)
62: save('checkpoint-parameter-drift-input', drift)
63: call('checkpoint-parameter-drift-run', 'run', drift_path, '--ticks', 1)
64: call('checkpoint-parameter-drift-seed', 'seed', drift_path)
66: call('checkpoint-parameter-drift-after-seed-run', 'run', OUT / 'checkpoint-parameter-drift-seed.json', '--ticks', 2)
69: call('checkpoint-parameter-missing-seed', 'seed', save('checkpoint-parameter-missing-input', missing))
69: save('checkpoint-parameter-missing-input', missing)
73: call('splitter-control', 'run', save('splitter-input', split), '--ticks', 7)
73: save('splitter-input', split)
77: call('gate-checkpoint-control-seed', 'seed', save('gate-checkpoint-control-input', split))
77: save('gate-checkpoint-control-input', split)
84: save('gate-expired-after-closure-input', split)
85: call('gate-expired-after-closure-seed', 'seed', expired)
86: call('gate-expired-after-closure-no-output', 'run', expired, '--ticks', 1, '--no-output')
87: call('gate-expired-after-closure-record', 'run', expired, '--ticks', 1)
88: call('gate-expired-record-verification', 'verify-record', OUT / 'gate-expired-after-closure-record.json')
96: call('zero-ore-sufficient-seed', 'seed', save('zero-ore-sufficient-input', zero))
96: save('zero-ore-sufficient-input', zero)
103: fixtures.generate('tiny-gate-generated', [unit('gate', '物品准入口', 10, 10)])
106: call('tiny-control', 'run', save('tiny-control-input', tiny), '--ticks', 6)
106: save('tiny-control-input', tiny)
116: save('tiny-expired-after-closure-input', tiny)
117: call('tiny-expired-cycle', 'cycle', tiny_path, '--max-ticks', 3)
118: call('tiny-expired-cycle-verification', 'verify-cycle', OUT / 'tiny-expired-cycle.json')
120: save('tiny-expired-embedded-record', certificate['run_record'])
121: call('tiny-expired-embedded-record-verification', 'verify-record', embedded)
122: save('probe-results', dict(binary=str(BIN), binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), cases=RESULTS))
126: main()
```

## crates/kernel/复核/r4-工程-证据/cache_cli.py

```text
assignments
9: OUT = Path(__file__).resolve().parent / 'cache-cli'
10: ROOT = OUT.parents[4]
11: BIN = ROOT / 'target/release/kernel'
12: CFG = ROOT / '规格/内核配置-v1.json'
32: source = ROOT / '数据/样例' / (name + '.json')
44: path = OUT / f'case-{index}-{variant}-input.json'
sinks
16: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
26: OUT.mkdir(exist_ok=True)
calls
20: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True, timeout=120)
45: save(path, data)
46: invoke(['seed', path, '--out', path])
54: invoke(['run', path, '--ticks', 8, '--out', first])
55: invoke(['run', path, '--ticks', 8, '--no-cache', '--out', second])
62: save(OUT / 'results.json', {'status': 'pass', 'random_seed': 20260920, 'cases': reports})
67: main()
```

## crates/kernel/复核/r4-工程-证据/cli_edges.py

```text
assignments
7: OUT = Path(__file__).resolve().parent / 'cli-edges'
8: ROOT = OUT.parents[4]
9: BIN = ROOT / 'target/release/kernel'
10: CFG = ROOT / '规格/内核配置-v1.json'
22: source = ROOT / '数据/样例/生产循环环带.json'
35: source = ROOT / '数据/样例/混做粉碎机两下游.json'
59: path = OUT / f'structure-{i}.json'
sinks
21: OUT.mkdir(exist_ok=True)
60: path.write_text(json.dumps(data, ensure_ascii=False) + '\n')
68: (OUT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
14: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True, timeout=30)
23: call(['run', source, '--ticks', 2, '--max-sweeps', 1, '--no-output'])
29: call(['run', source, '--ticks', 2, '--max-sweeps', budget, '--no-output'])
32: call(['run', source, '--ticks', 2, '--max-sweeps', 100000, '--no-output'])
61: call(['seed', path])
73: main()
```

## crates/kernel/复核/r4-工程-证据/final_check.py

```text
assignments
7: OUT = Path(__file__).resolve().parent
8: ROOT = OUT.parents[3]
20: path = Path(name) if name.startswith('/') else ROOT / name
27: path = Path(base) / name
34: path = Path(row['path'])
sinks
67: (OUT / '最终范围审计.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
72: main()
```

## crates/kernel/复核/r4-工程-证据/recheck.py

```text
assignments
11: OUT = Path(__file__).resolve().parent
12: ROOT = OUT.parents[3]
13: TESTS = ROOT / 'crates/kernel/tests'
15: BIN = ROOT / 'target/release/kernel'
16: CFG = ROOT / '规格/内核配置-v1.json'
20: path = OUT / name
62: source = Path(row['command'][2])
sinks
21: path.parent.mkdir(parents=True, exist_ok=True)
22: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
54: dense.E.mkdir(exist_ok=True)
83: fixtures.mkdir(exist_ok=True)
calls
29: module.main()
32: schema.main()
40: module.run(data)
43: save('reference-results.json', {'status': 'pass', 'records': reports})
51: save('audit/' + path.name, data)
55: module.main()
66: subprocess.run(row['command'], capture_output=True, text=True, timeout=120)
76: save('benchmark-replay.json', dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), old_binary_sha256=old['binary_sha256'], reports=reports))
87: module.generate(name, machines, logical, columns)
88: subprocess.run([str(BIN), 'seed', str(path), '--config', str(CFG), '--out', str(path)], capture_output=True, text=True)
93: save('benchmark-generator.json', {'reports': reports})
```

## crates/kernel/复核/r4-测试与证据/bin/python.py

```text
assignments
9: path = Path(script).resolve()
11: out = Path(__file__).resolve().parents[1]
13: dest = out / name
19: source = source.replace(old, 'Path(' + new + ')')
sinks
14: dest.mkdir(parents=True, exist_ok=True)
19: source.replace(old, 'Path(' + new + ')')
calls
```

## crates/kernel/复核/r4-测试与证据/final_check.py

```text
assignments
9: OUT = Path(__file__).resolve().parent
10: ROOT = OUT.parents[3]
11: REPORT = OUT.parent / '复核-r4-测试与证据.md'
sinks
66: (OUT / '交付自审.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/r4-测试与证据/manual_period.py

```text
assignments
7: OUT = Path(__file__).resolve().parent
8: ROOT = OUT.parents[3]
sinks
14: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
85: save('manual-expected.json', expected)
98: save('manual-period-check.json', dict(status='pass' if not differences else 'fail', period=20, compared_fields=list(expected[0]), ticks=20, events=200, table=table, differences=differences))
103: main()
```

## crates/kernel/复核/r4-测试与证据/probes.py

```text
assignments
10: OUT = Path(__file__).resolve().parent
11: ROOT = OUT.parents[3]
12: BASE = ROOT / '数据/样例'
13: BIN = ROOT / 'target/release/kernel'
14: CFG = ROOT / '规格/内核配置-v1.json'
15: REPORT = json.loads((OUT / 'probe-commands.json').read_text()) if (OUT / 'probe-commands.json').exists() else []
20: out = OUT / (name + '.json')
93: path = BASE / (name + '-运行记录-v3-kernel.json')
sinks
18: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
calls
22: subprocess.run(args, capture_output=True, text=True, timeout=90)
24: save('probe-commands.json', REPORT)
50: save(name + '-input.json', data)
64: save('d2-capacity-before-stop.json', dict(status='pass', cases=results))
75: save('dormant-axis-evidence.json', dict(record_status=r['status'], axis=row, first_event=e, parameters=values, verify_result=v, spec='选择点参数轴.md:40仅geometric_components使用；受限模型声明.md:40明确path_runs不调用该值', code='polling.rs:124-127只在belt&&previous_belt写marker，未求几何邻接；output.rs:273-275据marker报exercised'))
100: save('coverage-event-excerpts.json', selected)
116: subprocess.run(['node', '-e', script, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], input=json.dumps(dict(schema=schema, cases=rows), ensure_ascii=False), capture_output=True, text=True, check=True)
120: save('independent-schema.json', dict(validator='AJV2020 independent implementation', passed=sum((r['status'] == 'pass' for r in rows)), failed=sum((r['status'] == 'fail' for r in rows)), cases=rows))
131: save('supply-' + mode + '-input.json', data)
157: save('supply-differential.json', dict(status='pass', ticks=30, state_fields=fields, events_equal=True, actual_inbound_and_outbound_equal=True, independent_conservation=True, counts=counts, scope='未耗尽、无回矿候选、显式历史为空但覆盖40刻；不是耗尽或回矿情形等价证明。'))
164: main()
```

## crates/kernel/复核/r4-测试与证据/recheck.py

```text
assignments
13: OUT = Path(__file__).resolve().parent
14: ROOT = OUT.parents[3]
15: BASE = ROOT / '数据/样例'
16: BIN = ROOT / 'target/release/kernel'
17: CFG = ROOT / '规格/内核配置-v1.json'
20: COMMANDS = json.loads((OUT / 'commands.json').read_text()) if (OUT / 'commands.json').exists() else []
26: path = Path(path)
51: path = save(OUT / 'invalid-cycle-input.json', {'schema': 'kernel-input-v3'})
62: path = ROOT / 'crates/kernel/tests/fixtures' / (name + '.json')
79: path = ROOT / 'crates/kernel/tests/verify_outputs.py'
83: source = source.replace(old, '(Path(' + repr(str(OUT / 'record-validation.json')) + ')).write_text')
96: path = OUT / (name + '-fresh-cycle.json')
sinks
28: path.parent.mkdir(parents=True, exist_ok=True)
29: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
83: source.replace(old, '(Path(' + repr(str(OUT / 'record-validation.json')) + ')).write_text')
calls
35: subprocess.run(command, capture_output=True, text=True, timeout=240)
38: save(OUT / 'commands.json', COMMANDS)
45: invoke(['seed', BASE / '混做粉碎机两下游.json', '--out', seed])
46: invoke(['run', seed, '--ticks', '4', '--no-output'])
48: invoke(['run', BASE / '生产循环环带.json', '--ticks', '2', '--max-sweeps', '1', '--no-output'], 2)
50: save(OUT / 'resource-statistics.json', r)
51: save(OUT / 'invalid-cycle-input.json', {'schema': 'kernel-input-v3'})
53: invoke(['cycle', path, '--max-ticks', '2', '--out', result], 2)
56: save(OUT / 'redirected-rust-cli.json', dict(status='pass', original='crates/kernel/tests/round5_cli.rs', note='原测试全部4次CLI调用和全部断言；仅输出位置改为本目录。'))
66: invoke(['run', path, '--ticks', '12', '--no-output'])
73: save(OUT / 'benchmark.json', dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), cases=cases, scope='相同已锁定合成输入，release，3次各12 tick；引擎推进时间，不含装载和序列化。'))
91: audit.main()
97: invoke(['cycle', BASE / (name + '.json'), '--max-ticks', budget, '--out', path])
98: invoke(['verify-cycle', path])
102: save(OUT / 'fresh-cycles.json', results)
109: main()
```

## crates/kernel/复核/r4-测试与证据/run_cargo.py

```text
assignments
7: out = Path(__file__).resolve().parent
8: root = out.parents[3]
sinks
10: wrapper.write_bytes((out / 'bin/python.py').read_bytes())
12: (out / 'tmp').mkdir(exist_ok=True)
21: wrapper.unlink()
calls
18: subprocess.run(['cargo', 'test', '--locked', '--offline', '--', '--skip', 'round5_cli_resource_statistics_and_cycle_load_stop'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
```

## crates/kernel/复核/r4-测试与证据/write_report.py

```text
assignments
6: OUT = Path(__file__).resolve().parent
7: ROOT = OUT.parents[3]
8: K = ROOT / 'crates/kernel'
sinks
20: (OUT / '结果.json').write_text(json.dumps(dict(findings=findings, notes=notes), ensure_ascii=False, indent=2) + '\n')
61: Path(row['record']).name.replace('-运行记录-v3-kernel.json', '')
65: source.replace('|', '\\|')
66: reasons[axis].replace('|', '\\|')
190: (K / '复核/复核-r4-测试与证据.md').write_text(report)
calls
```

## crates/kernel/复核/r4-规格保真-证据/age_cohorts.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
11: dest = OUT / (name + '-result.json')
sinks
11: p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
16: (OUT / 'age-cohort-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
calls
13: subprocess.run(cmd, capture_output=True, text=True)
```

## crates/kernel/复核/r4-规格保真-证据/audit_current.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
sinks
39: (OUT / 'current-audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
22: subprocess.run(cmd, capture_output=True, text=True, timeout=180)
```

## crates/kernel/复核/r4-规格保真-证据/confirm_findings.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
26: target = OUT / 'closed-first-sweep-stop-result.json'
sinks
36: (OUT / 'confirmed-findings.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
28: subprocess.run(cmd, capture_output=True, text=True)
```

## crates/kernel/复核/r4-规格保真-证据/key_probe.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: OUT = Path(__file__).resolve().parent
5: source = '\nuse kernel::{Input,Engine,Config,Result,value::read_json};\nuse serde_json::{Value,json};\nuse std::path::Path;\nfn examine(path: &Path, config_path: &Path) -> Result<Value> {\n let config=Config::parse(read_json(config_path)?)?;\n let input=Input::load(path,&config,false)?;\n let engine=Engine::new(input)?;\n Ok(json!({"status":"accepted","key":engine.cycle_key()?}))\n}\nfn main() {\n let args:Vec<String>=std::env::args().collect();\n let result=match examine(Path::new(&args[1]),Path::new(&args[2])) {\n  Ok(v)=>v,Err(e)=>json!({"status":"rejected","error":e.to_string()})\n };\n println!("{}",result);\n}\n'
35: path = OUT / (name + '-input.json')
sinks
26: (OUT / 'key-probe-build.log').write_text(p.stdout + p.stderr)
35: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
37: (OUT / (name + '-result.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
38: (OUT / 'key-probe-summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run(cmd, input=source, text=True, capture_output=True)
36: subprocess.run([str(binary), str(path), str(ROOT / '规格/内核配置-v1.json')], capture_output=True, text=True)
```

## crates/kernel/复核/r4-规格保真-证据/probes.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
5: OUT = Path(__file__).resolve().parent
6: BIN = ROOT / 'target/release/kernel'
6: CFG = ROOT / '规格/内核配置-v1.json'
9: SCHEMA = json.loads((ROOT / '规格/内核输出.schema.json').read_text())
25: dest = OUT / (name + '-result.json')
sinks
12: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
calls
24: write(name + '-input', d)
29: subprocess.run(cmd, capture_output=True, text=True, timeout=90)
37: invoke('branch-control', 'run', d, ticks=12)
39: invoke('unqueried-branch', 'run', d, ticks=12)
41: invoke('first-sweep-stop', 'run', d, extra=['--max-sweeps', '1'])
41: invoke('first-sweep-cycle-stop', 'cycle', d, extra=['--max-sweeps', '1'])
43: invoke('crusher-control', 'run', d, ticks=3)
45: invoke('checkpoint-control', 'seed', closed)
51: invoke(name, 'seed', trial)
54: invoke('pending-rational', 'seed', trial)
55: write('probe-results', RESULTS)
```

## crates/kernel/复核/r5-测试与证据/k6_ledger.py

```text
assignments
7: source = BASE / '双成品满仓起动试作.json'
24: path = OUT / 'K6-temporary-record.json'
sinks
74: path.unlink()
calls
25: call(f'K6-segment-{segment:02d}-run', ['run', source, '--ticks', 32, '--format', 'checkpoint_delta', '--checkpoint-interval', 16, '--out', path])
72: call(f'K6-segment-{segment:02d}-checkpoint', ['checkpoint', path, '--out', next_source])
83: save('K6-finite-ledger.json', dict(scope='finite_concrete有限前缀，非周期账', rows=all_rows))
84: save('K6-ledger-audit.json', dict(status='pass', segments=segments, completed_ticks=len(all_rows), completed_batches=completion_count, totals={k: str(v) for k, v in sorted(totals.items())}, product_transactions={item: [dict(time=r['time'], route=route, entry=e) for r in all_rows for route in ('core_inbound', 'wireless_inbound') for e in r['warehouse_ledger'][route] if e['item'] == item] for item in PRODUCTS}, final_state=last_state, scope='每笔入库对应成功事件；独立求和并核512刻全物种仓库守恒，续跑首刻无重复；没有周期，不能据此计算周期率。'))
```

## crates/kernel/复核/r5-测试与证据/review_probe.py

```text
assignments
12: OUT = Path(__file__).resolve().parent
13: ROOT = OUT.parents[3]
14: BIN = ROOT / 'target/release/kernel'
15: CFG = ROOT / '规格/内核配置-v1.json'
16: BASE = ROOT / '数据/样例'
93: dest = OUT / (path.stem + '-benchmark-cycle.json')
115: dest = OUT / (name + '-cycle.json')
127: source = OUT / 'reference-input.json'
156: path = Path(cert['run_record_ref']['path'])
sinks
21: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
128: source.write_bytes((BASE / '桥接器双通路.json').read_bytes())
140: path.write_bytes(changed)
153: path.write_bytes(original)
165: path.write_bytes(original)
calls
30: subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
31: save(name + '.json', dict(command=cmd, cwd=str(cwd), returncode=p.returncode, stdout=p.stdout, stderr=p.stderr))
96: subprocess.run([sys.executable, '-B', str(ROOT / 'crates/kernel/tests/measure_command.py'), *cmd], capture_output=True, text=True, check=True)
98: save(path.stem + '-' + mode + '-measurement.json', dict(command=cmd, **measured))
109: save('benchmark-review.json', dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), reports=reports))
116: call(name + '-search', ['cycle', BASE / (name + '.json'), '--max-ticks', ticks, '--no-record', '--out', dest])
117: call(name + '-verify', ['verify-cycle', dest])
120: call('K6-domain', ['check', BASE / '双成品满仓起动试作.json', '--cycle-domain'])
121: call('K6-finite-run', ['run', BASE / '双成品满仓起动试作.json', '--ticks', 512, '--no-output'])
123: save('cycle-manual-audit.json', audits)
130: call('reference-generate', ['cycle', source, '--max-ticks', 120, '--out', cert_path])
132: call('reference-control', ['verify-cycle', cert_path])
141: call('tamper-' + label + '-one-byte', ['verify-cycle', cert_path], expected=2)
149: save('input-reference-isolated.json', isolated)
150: call('tamper-input-reference-isolated', ['verify-cycle', OUT / 'input-reference-isolated.json'], expected=2)
154: call('tamper-' + label + '-restored', ['verify-cycle', cert_path])
160: save(path.name, record)
163: save('reference-resealed.json', changed)
164: call('tamper-record-resealed', ['verify-cycle', OUT / 'reference-resealed.json'], expected=2)
171: save('reference-' + label + '.json', bad)
172: call('tamper-' + label, ['verify-cycle', OUT / ('reference-' + label + '.json')], expected=2)
181: save('relative-cycle.json', relative)
182: call('relative-different-cwd', ['verify-cycle', OUT / 'relative-cycle.json'], cwd=ROOT / 'target')
183: save('reference-tamper-results.json', cases)
```

## crates/kernel/复核/r5-测试与证据/storage_audit.py

```text
assignments
7: evidence = ROOT / 'crates/kernel/evidence/round6'
sinks
calls
57: save('storage-audit.json', dict(status='pass', samples_files=len(files), before_bytes=old_size, after_bytes=size, reduction_percent=100 * (old_size - size) / old_size, oversize_files=oversize, replacement_results=replacement_results, deleted=missing, listing_paths=len(listing['files']), evidence_extensions=dict(extensions), evidence_bytes=sum((p.stat().st_size for p in evidence.rglob('*') if p.is_file())), protected_files=len(protected), protection_scope_counts={k: len(scope[k]) for k in ('retained_from_old', 'added', 'no_longer_byte_protected')}, largest_samples=sorted([dict(path=str(p), bytes=p.stat().st_size) for p in files], key=lambda r: r['bytes'], reverse=True)[:5], limitation='旧大文件已替换，本席不能独立读取已删除旧字节；旧体量由开工清单求和并与迁移清单交叉核，当前体量/字节/文件存在性为现场复算。'))
```

## crates/kernel/复核/r5-规格保真与工程-证据/audit.py

```text
assignments
8: HERE = Path(__file__).resolve().parent
9: ROOT = HERE.parents[3]
10: EVIDENCE = ROOT / 'crates/kernel/evidence/round6'
42: target = ROOT / '规格/复核/约减/等价类计数.json'
sinks
22: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
39: save('artifact-inventory.json', {'path_count': len(rows), 'missing': [r['path'] for r in rows if not r['exists']], 'files': rows})
62: save('reduction-independent.json', {'status': 'pass', 'before_hash_reconstructed': old_sha, 'after_hash': sha(target), 'changed_files': changed, 'unchanged_count': len(unchanged), 'changed_sha256_entries': len(lock['changed_fingerprints']), 'non_source_content_equal': {k: v for k, v in reconstructed.items() if k != 'sources'} == {k: v for k, v in current.items() if k != 'sources'}, 'classes': lock['classes']})
71: save('field-sets.json', {'top_level_fields': sorted(certificate), 'count': len(certificate), 'required_equal': True, 'cycle_fields': sorted(certificate['cycle']), 'input_reference_fields': sorted(certificate['replay_input_ref']), 'domain_fields': sorted(certificate['domain_report'][0])})
85: save('write-boundary.json', {'baseline_files': len(baseline), 'changed': changes, 'evidence_extensions': sorted({p.suffix for p in HERE.rglob('*') if p.is_file()}), 'evidence_bytes': sum((p.stat().st_size for p in HERE.rglob('*') if p.is_file()))})
93: main()
```

## crates/kernel/复核/r5-规格保真与工程-证据/extra_probe.py

```text
assignments
29: output = HERE / 'checkpoint-delta-record.json'
30: base = ROOT / '数据/样例/生产循环环带.json'
sinks
16: package.mkdir(exist_ok=True)
calls
13: call('absolute-record-verify', 'verify-record', absolute)
14: call('absolute-record-checkpoint', 'checkpoint', absolute, '--out', HERE / 'absolute-record-checkpoint.json')
21: save('relative-package/record.json', record)
26: save('relative-package/certificate.json', cert)
27: call('relative-package-cycle-verify', 'verify-cycle', cert_path)
28: call('relative-package-batch', 'verify-batch', package)
31: call('delta-run', 'run', base, '--ticks', 4, '--format', 'checkpoint_delta', '--checkpoint-interval', 3, '--out', output)
33: call('delta-checkpoint', 'checkpoint', output, '--out', checkpoint)
35: call('delta-resumed', 'run', checkpoint, '--ticks', 2, '--out', resumed)
40: save('delta-resume-comparison.json', {'previous_end': end, 'resumed_first': first, 'first_is_t_plus_one': True})
41: save('extra-schema-results.json', schema([record_path, cert_path, output, resumed]))
42: save('extra-results.json', CASES)
47: main()
```

## crates/kernel/复核/r5-规格保真与工程-证据/probe.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: ROOT = HERE.parents[3]
13: BIN = ROOT / 'target/release/kernel'
14: CFG = ROOT / '规格/内核配置-v1.json'
23: path = HERE / name
65: base = ROOT / '数据/样例/生产循环环带.json'
70: path = HERE / (name + '.json')
95: record = read(Path(ref['run_record_ref']['path']))
sinks
24: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
31: (HERE / (name + '.log')).write_text(json.dumps({'command': command, 'cwd': str(cwd), 'exit': result.returncode}, ensure_ascii=False) + '\nSTDOUT\n' + result.stdout + '\nSTDERR\n' + result.stderr)
calls
30: subprocess.run(command, cwd=cwd, capture_output=True, text=True)
58: subprocess.run(['node', '-e', source, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], input=json.dumps({'schema': str(ROOT / '规格/内核输出.schema.json'), 'paths': list(map(str, paths))}), capture_output=True, text=True, check=True)
72: call(name, 'cycle', base, '--max-ticks', 50, '--search-checkpoint-interval', interval, '--out', path, *flags)
73: call(name + '-verify', 'verify-cycle', path, cwd=ROOT.parent)
77: save('interval-comparison.json', {'intervals': [1, 7], 'identical_result': True})
79: call('checkpoint-valid', 'checkpoint', HERE / 'none-7.json', '--out', cp)
81: call('continued', 'cycle', cp, '--max-ticks', 25, '--no-record', '--out', continued)
82: call('continued-verify', 'verify-cycle', continued)
90: call('load-shell-verify', 'verify-cycle', shell)
91: call('load-shell-checkpoint', 'checkpoint', shell, '--out', HERE / 'invalid-checkpoint.json')
99: save('relative.record.json', record)
103: save('relative-cycle.json', ref)
104: call('relative-cycle-verify', 'verify-cycle', relative_cert)
105: call('relative-record-verify-root', 'verify-record', relative_record)
106: call('relative-record-verify-local', 'verify-record', relative_record, cwd=HERE)
107: call('relative-record-checkpoint', 'checkpoint', relative_record, '--out', HERE / 'relative-checkpoint.json')
121: save(f'ore-{quantity}-raw.json', current)
123: call(f'ore-{quantity}-seed', 'seed', source, '--out', seeded)
124: call(f'ore-{quantity}-finite-check', 'check', seeded)
125: call(f'ore-{quantity}-domain', 'check', seeded, '--cycle-domain')
128: save('ore-dependent-memory.json', {'memory_equal': a == b, 'at_79999': a, 'at_80000': b})
131: save('ore-capacity-changed-only.json', crossed)
132: call('ore-capacity-changed-domain', 'check', source, '--cycle-domain')
134: save('schema-results.json', schema(documents))
135: save('results.json', CASES)
140: main()
```

## crates/kernel/复核/否证-r3-1-证据/reproduce.py

```text
assignments
10: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
11: OUT = Path(__file__).resolve().parent
12: BIN = ROOT / 'target/release/kernel'
13: CFG = ROOT / '规格/内核配置-v1.json'
14: SAMPLES = ROOT / '数据/样例'
25: path = Path(path)
31: path = OUT / (name + '.json')
37: path = Path(path)
240: target = snapshot / '求解器/target'
sinks
32: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
49: result_path.unlink(missing_ok=True)
60: (OUT / (name + '.log')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
calls
52: subprocess.run(cmd, capture_output=True, text=True, timeout=120)
61: save('calls', CALLS)
84: call('crusher-control', 'run', save('crusher-input', crusher), '--ticks', 4)
84: save('crusher-input', crusher)
88: call('crusher-checkpoint-seed', 'seed', save('crusher-checkpoint', checkpoint))
88: save('crusher-checkpoint', checkpoint)
96: save('crusher-' + name + '-input', altered)
97: call('crusher-' + name + '-direct', 'run', path, '--ticks', 1)
98: call('crusher-' + name + '-seed', 'seed', path)
100: call('crusher-' + name + '-resumed', 'run', OUT / ('crusher-' + name + '-seed.json'), '--ticks', 1)
103: call('bridge-control', 'run', save('bridge-input', bridge), '--ticks', 30)
103: save('bridge-input', bridge)
104: call('bridge-record-verification', 'verify-record', OUT / 'bridge-control.json')
115: save('bridge-' + name + '-checkpoint', altered)
116: call('bridge-' + name + '-direct', 'run', path, '--ticks', 2)
117: call('bridge-' + name + '-seed', 'seed', path)
123: call('phase-' + name, 'run', save('phase-' + name + '-input', altered), '--ticks', 2)
123: save('phase-' + name + '-input', altered)
130: call('splitter-control', 'run', save('splitter-input', splitter), '--ticks', 7)
130: save('splitter-input', splitter)
132: call('gate-valid-seed', 'seed', save('gate-valid-input', splitter))
132: save('gate-valid-input', splitter)
139: save('gate-expired-input', splitter)
140: call('gate-expired-seed', 'seed', path)
141: call('gate-expired-run', 'run', path, '--ticks', 1)
144: call('gate-expired-verification', 'verify-record', OUT / 'gate-expired-run.json')
148: call('tiny-control', 'run', save('tiny-control-input', tiny), '--ticks', 6)
148: save('tiny-control-input', tiny)
156: call('tiny-expired-cycle', 'cycle', save('tiny-expired-input', tiny), '--max-ticks', 3)
156: save('tiny-expired-input', tiny)
157: call('tiny-expired-cycle-verification', 'verify-cycle', OUT / 'tiny-expired-cycle.json')
158: call('tiny-embedded-verification', 'verify-record', save('tiny-embedded-record', result['run_record']))
158: save('tiny-embedded-record', result['run_record'])
164: call('ring-control-cycle', 'cycle', save('ring-input', ring), '--max-ticks', 25)
164: save('ring-input', ring)
165: call('ring-control-verification', 'verify-cycle', OUT / 'ring-control-cycle.json')
169: call('phase-string-cycle', 'cycle', save('phase-string-cycle-input', altered), '--max-ticks', 25)
169: save('phase-string-cycle-input', altered)
170: call('phase-string-cycle-verification', 'verify-cycle', OUT / 'phase-string-cycle.json')
178: call('zero-ore-seed', 'seed', save('zero-ore-input', zero))
178: save('zero-ore-input', zero)
179: call('zero-ore-run', 'run', OUT / 'zero-ore-seed.json', '--ticks', 1)
183: save('overflow-input', overflow)
185: call('overflow-' + mode, mode, path, '--ticks', 2)
192: call(name, 'run', save(name + '-input', altered), '--ticks', 1)
192: save(name + '-input', altered)
195: call('boolean-seed', 'seed', save('boolean-seed-input', altered))
195: save('boolean-seed-input', altered)
213: save('bridge-coverage', dict(axis=axis, selected_events=selected, bridge_axes=bridges, connection_events=raw['timeline']['connection_events'], history=raw['timeline']['events'], first_time=record['trace']['ticks'][0]['time'], last_time=record['trace']['ticks'][-1]['time'], successful_bridge_moves=bridge_moves, wireless_inbound=wireless, audit_bridge_cases=audit['coverage'].get('connection.bridge_first_contact'), audit_missing=audit['required_unexercised']))
241: save('directory-scan', dict(binaries=binaries, count=len(binaries), bytes=sum((r['bytes'] for r in binaries)), special_dirs=special_dirs, snapshot=dict(path=str(snapshot), count=len(files), bytes=sum((p.stat().st_size for p in files)), files=[str(p.relative_to(snapshot)) for p in files], target_exists=target.is_dir(), target_symlink=target.is_symlink(), target_children=[p.name for p in target.iterdir()] if target.is_dir() else [])))
254: save('source-hashes-before', SOURCES)
261: save('source-hashes-final', dict(files=SOURCES, changed=changes, binary=dict(path=str(BIN), sha256=digest(BIN))))
262: save('checks', CHECKS)
268: main()
```

## crates/kernel/复核/否证-r3-1-证据/supplement.py

```text
assignments
7: HERE = Path(__file__).resolve().parent
21: record = probe.read(probe.SAMPLES / (name + '-运行记录-v3-kernel.json'))
sinks
calls
15: probe.call('tiny-before-boundary', 'run', probe.save('tiny-before-boundary-input', tiny), '--ticks', 1)
15: probe.save('tiny-before-boundary-input', tiny)
16: probe.call('tiny-before-boundary-verification', 'verify-record', HERE / 'tiny-before-boundary.json')
34: probe.save('supplement-results', dict(before_boundary_status=result['status'], before_boundary_time=result['trace']['ticks'][0]['time'], before_boundary_events=result['trace']['ticks'][0]['events'], before_boundary_verified=verification['status'], phase_comparison=phase_comparison, aggregate_bridge_cases=coverage, source_hashes=probe.SOURCES))
```

## crates/kernel/复核/否证-r3-1-证据/verify_deliverable.py

```text
assignments
7: OUT = Path(__file__).resolve().parent
8: REPORT = OUT.parent / '否证-r3-1.md'
78: path = Path(target) if target.startswith('/') else REPORT.parent / target
sinks
33: (OUT / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + '\n')
98: (OUT / '交付核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
103: main()
```

## crates/kernel/复核/否证-r3-2-证据/finalize_check.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
8: OUT = Path(__file__).resolve().parent
9: REPORT = OUT.parent / '否证-r3-2.md'
sinks
10: (OUT / '交付核验.json').write_text('{"status":"checking"}\n')
26: (OUT / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + '\n')
76: (OUT / '交付核验.json').write_text(json.dumps(check, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/否证-r3-2-证据/independent_probes.py

```text
assignments
9: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
10: OUT = Path(__file__).resolve().parent
11: BIN = ROOT / 'target/release/kernel'
12: CFG = ROOT / '规格/内核配置-v1.json'
18: path = Path(path)
25: path = OUT / (name + '.json')
31: path = ROOT / '数据/样例' / (name + '.json')
43: dest = OUT / (name + '-result.json')
sinks
26: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
44: dest.unlink(missing_ok=True)
57: (OUT / (name + '.log')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
calls
42: save(name + '-input', data)
48: subprocess.run(args, text=True, capture_output=True, timeout=90)
58: save('cli-results', RESULTS)
81: invoke('bridge-fresh', 'run', bridge, 30)
95: invoke('checkpoint-' + name + '-direct', 'run', raw, 2)
96: invoke('checkpoint-' + name + '-seed', 'seed', raw)
97: invoke('checkpoint-' + name + '-resumed', 'run', OUT / ('checkpoint-' + name + '-seed-result.json'), 2)
100: save('checkpoint-summary', summaries)
102: invoke('crusher-control', 'run', crusher, 4)
106: invoke('supply-conflict-direct', 'run', drift, 1)
107: invoke('supply-conflict-seed', 'seed', drift)
108: invoke('supply-conflict-resumed', 'run', OUT / 'supply-conflict-seed-result.json', 2)
115: invoke('phase-' + name, 'run', raw, 2)
117: invoke('ring-control', 'cycle', ring, 25)
118: invoke('ring-control-verify', 'verify-cycle', OUT / 'ring-control-result.json')
122: invoke('phase-cycle', 'cycle', bad_phase, 25)
123: invoke('phase-cycle-verify', 'verify-cycle', OUT / 'phase-cycle-result.json')
127: invoke('splitter-control', 'run', splitter, 7)
138: invoke('window-' + name + '-seed', 'seed', raw)
139: invoke('window-' + name, 'run', raw, 1)
141: invoke('window-' + name + '-verify', 'verify-record', OUT / ('window-' + name + '-result.json'))
145: invoke('tiny-control', 'run', tiny, 6)
152: invoke('expired-cycle', 'cycle', tiny, 3)
153: invoke('expired-cycle-verify', 'verify-cycle', OUT / 'expired-cycle-result.json')
154: invoke('expired-embedded-verify', 'verify-record', save('expired-embedded-record', tiny_cycle['run_record']))
154: save('expired-embedded-record', tiny_cycle['run_record'])
162: invoke('zero-' + ore + '-seed', 'seed', zero)
163: invoke('zero-' + ore + '-run', 'run', OUT / ('zero-' + ore + '-seed-result.json'), 1)
169: invoke('slot-' + ('short' if label == 'bad' else 'unknown'), 'run', raw, 1)
172: invoke('seed-bool', 'seed', raw)
176: invoke('overflow-run', 'run', overflow, 2)
177: invoke('overflow-cycle', 'cycle', overflow, 2)
199: save('bridge-coverage', dict(axis=axis, cited_events=cited, bridge_units=[u for u in bridge['layout']['units'] if u['kind'] == '桥接器'], history=history, incoming=dict(incoming), outgoing=dict(outgoing), wireless=dict(wireless), first_time=bridge_run['trace']['ticks'][0]['time'], last_time=bridge_run['trace']['ticks'][-1]['time'], aggregate_axis=audit['coverage'].get('connection.bridge_first_contact'), required_unexercised=audit['required_unexercised']))
203: invoke('bridge-fresh-verify', 'verify-record', OUT / 'bridge-fresh-result.json')
204: save('source-fingerprints', dict(sources=SOURCES, binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest()))
208: main()
```

## crates/kernel/复核/否证-r3-2-证据/scan_evidence.py

```text
assignments
6: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
7: OUT = Path(__file__).resolve().parent
25: target = snapshot / '求解器/target'
sinks
32: (OUT / 'evidence-scan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## crates/kernel/复核/否证-r4-1-证据/recheck.py

```text
assignments
8: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
9: OUT = Path(__file__).resolve().parent
10: BIN = ROOT / 'target/release/kernel'
11: CFG = ROOT / '规格/内核配置-v1.json'
20: path = OUT / (name + '.json')
37: target = OUT / (name + '-result.json')
43: path = ROOT / '数据/样例' / (name + '.json')
sinks
21: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
172: (OUT / 'key-build.log').write_text(build.stdout + build.stderr)
calls
26: subprocess.run([str(x) for x in command], input=stdin, capture_output=True, text=True, timeout=60)
31: write('commands', COMMANDS)
36: write(name + '-input', source)
38: call([BIN, mode, path, '--config', CFG, '--out', target, *extra])
78: invoke('splitter-seed', 'seed', sample('分流器三路轮询'))
86: invoke(name, 'seed', raw)
91: write('age-results', ages)
103: invoke('branch-full', 'run', splitter, '--ticks', '12')
109: invoke('branch-empty', 'run', empty, '--ticks', '12')
111: write('branch-results', dict(maximum_geometric_output_levels={k: sorted(v) for k, v in levels.items()}, original_choices=original_count, full_status=full['status'], completed_ticks=len(full['trace']['ticks']), empty_status=empty_result['status'], empty_exit_code=empty_code, open_items=empty_result['open_items'], control_coverage=axis_coverage(full, 'damping.branch')))
119: invoke('crusher', 'run', crusher, '--ticks', '3')
123: invoke('checkpoint', 'seed', closed)
125: invoke('checkpoint-resumed', 'run', checkpoint, '--ticks', '1')
129: invoke('checkpoint-stop-' + name, 'run', checkpoint, '--ticks', '1', '--max-sweeps', '1', '--format', format_name)
136: write('checkpoint-results', dict(seed_identical=True, seed_time=state(checkpoint)['environment']['time'], seed_phase=state(checkpoint)['semantic_context']['judgment_context']['value']['phase'], full_budget_next_time=resumed['trace']['ticks'][0]['time'], full_budget_next_state_matches=True, limited=prefix_results))
145: invoke('trigger-extra', 'seed', unknown)
168: call(['rustc', '--edition=2021', '--crate-name', 'refutation_r4_seat1_key', '-', '--extern', 'kernel=' + str(ROOT / 'target/release/libkernel.rlib'), '--extern', 'serde_json=' + str(serde), '-L', 'dependency=' + str(ROOT / 'target/release/deps'), '-o', probe], key_source)
178: write('key-' + name + '-input', raw)
179: call([probe, path, CFG])
181: write('key-' + name + '-result', key)
187: write('trigger-results', dict(seed_accepted=True, public_key_accepted=[True, True], only_difference='/state/semantic_context/pending_events/value/0/trigger/extra', extra=extra))
191: invoke('belts', 'run', sample('阻尼连续带核验'), '--ticks', '3')
193: invoke('belts-verify', 'verify-record', OUT / 'belts-result.json')
202: write('coverage-results', dict(new_axis=coverage, first_event=first, verify_result=verified, old_axis_status=old_axis['coverage_status'], old_evidence_count=len(old_axis['evidence']), aggregate_missing=audit['required_unexercised'], aggregate_claim=audit['coverage'].get('damping.belt_adjacency')))
210: invoke('cycle-control', 'cycle', ring, '--max-ticks', '30')
215: invoke('cycle-overflow', 'cycle', overflow, '--max-ticks', '30')
228: call(['node', '-e', schema_script], json.dumps(dict(schema=read(ROOT / '规格/内核输出.schema.json'), cases=[dict(name='cycle-control', data=normal), dict(name='cycle-overflow', data=failed), dict(name='valid-continuation', data=resumed)]), ensure_ascii=False))
235: write('schema-results', dict(validator='AJV2020', cases=schema_results, resource_result=dict(status=failed['status'], stop=failed['stop'], budget=failed['budget'], null_context=[k for k in ['seed', 'parameter_point', 'replay_input', 'run_record'] if failed[k] is None])))
238: write('summary', dict(status='completed', independent_cli_and_probe_calls=len(COMMANDS), binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), findings_reproduced=['KR-r4-L1-01', 'KR-r4-L1-02', 'KR-r4-L1-03', 'KR-r4-L1-04', 'KR-r4-L1-05', 'KR-r4-L2-1', 'KR-r4-L2-2']))
246: main()
```

## crates/kernel/复核/否证-r4-2-证据/final_check.py

```text
assignments
8: ROOT = Path('/home/zhuran24/zmd-research-fresh')
9: WORK = ROOT / '求解器'
10: OUT = Path(__file__).resolve().parent
11: REPORT = OUT.parent / '否证-r4-2.md'
43: path = ROOT / relative
sinks
17: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
49: write('source-excerpts.json', excerpts)
62: write('verdicts.json', verdicts)
94: write('delivery-check.json', payload)
```

## crates/kernel/复核/否证-r4-2-证据/run_checks.py

```text
assignments
9: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
10: OUT = Path(__file__).resolve().parent
11: BASE = ROOT / '数据/样例'
12: CFG = ROOT / '规格/内核配置-v1.json'
13: BIN = ROOT / 'target/debug/kernel'
20: path = OUT / (name + '.json')
25: path = BASE / (name + '.json')
53: target = OUT / (name + '-result.json')
208: path = OUT / (name + '-seed-input.json')
sinks
21: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
56: (OUT / (name + '.log')).write_text(proc.stdout + proc.stderr)
111: (OUT / 'probe-build.log').write_text(proc.stdout + proc.stderr)
133: (OUT / 'schema-validation.log').write_text(proc.stderr)
calls
52: save(name + '-input', data)
55: subprocess.run(command, text=True, capture_output=True, timeout=60)
61: save('commands', COMMANDS)
110: subprocess.run(command, input=code, text=True, capture_output=True, cwd=ROOT / 'target')
113: save('probe-build', dict(command=command, exit_code=proc.returncode, kernel_rlib_sha256=hashlib.sha256(lib.read_bytes()).hexdigest()))
131: subprocess.run(['node', '-e', script, module], text=True, capture_output=True, input=json.dumps(dict(schema=read(ROOT / '规格/内核输出.schema.json'), cases=cases)))
136: save('schema-results', dict(validator='AJV 2020', module=module, cases=rows))
142: invoke('branch-control', 'run', splitter, '--ticks', '12')
159: invoke('branch-empty', 'run', empty, '--ticks', '12')
173: invoke(name, 'seed', trial)
180: invoke('crusher-control', 'run', crusher, '--ticks', '3')
184: invoke('checkpoint-seed', 'seed', checkpoint)
186: invoke('checkpoint-resume-control', 'run', checkpoint, '--ticks', '1')
188: invoke('checkpoint-budget', 'run', checkpoint, '--ticks', '1', '--max-sweeps', '1')
190: invoke('checkpoint-budget-delta', 'run', checkpoint, '--ticks', '1', '--max-sweeps', '1', '--format', 'checkpoint_delta')
206: invoke(name + '-seed', 'seed', trial)
210: subprocess.run(command, text=True, capture_output=True)
212: save(name, key)
221: invoke('key-kind-negative-control', 'seed', invalid_trigger)
225: invoke('adjacency-three-ticks', 'run', source('阻尼连续带核验'), '--ticks', '3')
227: invoke('adjacency-verify', 'verify-record', OUT / 'adjacency-three-ticks-result.json')
242: invoke('cycle-control', 'cycle', ring, '--max-ticks', '2')
247: invoke('cycle-overflow', 'cycle', overflow, '--max-ticks', '2')
249: invoke('run-overflow', 'run', overflow, '--ticks', '2')
259: save('results', summary)
260: save('commands', COMMANDS)
264: main()
```

## crates/kernel/复核/否证-r5-1-证据/audit.py

```text
assignments
7: HERE = Path(__file__).resolve().parent
8: ROOT = HERE.parents[3]
38: path = Path(name)
sinks
65: (HERE / 'verification-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
calls
70: main()
```

## crates/kernel/复核/否证-r5-1-证据/reproduce.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: ROOT = HERE.parents[3]
13: BIN = ROOT / 'target/release/kernel'
14: CFG = ROOT / '规格/内核配置-v1.json'
128: record = read(HERE / f'ore-{amount}-finite-record.json')
sinks
23: path.parent.mkdir(parents=True, exist_ok=True)
24: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
43: (HERE / f'{name}.log').write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\nSTDOUT\n' + proc.stdout + '\nSTDERR\n' + proc.stderr)
141: absolute_dir.mkdir(exist_ok=True)
142: relative_dir.mkdir(exist_ok=True)
calls
34: subprocess.run(list(map(str, command)), cwd=cwd, input=stdin, capture_output=True, text=True, env=env, timeout=120)
45: save(HERE / 'commands.json', CALLS)
50: call(name, [BIN, *args, '--config', CFG], cwd)
78: call(f'constructor-build-{index}', ['rustc', '--edition=2021', '--crate-name', 'r5_seat1_constructor_probe', '-', '-L', f'dependency={deps}', '--extern', f'kernel={ROOT}/target/release/libkernel.rlib', '--extern', f'serde_json={library}', '-o', binary], stdin=source)
109: save(HERE / f'ore-{amount}-raw.json', variant)
111: kernel(f'ore-{amount}-seed', 'seed', input_path, '--out', seed_path)
114: kernel(f'ore-{amount}-cycle', 'cycle', seed_path, '--max-ticks', 1, '--no-record', '--out', HERE / f'ore-{amount}-cycle.json')
116: kernel(f'ore-{amount}-finite-run', 'run', seed_path, '--ticks', 1, '--out', HERE / f'ore-{amount}-finite-record.json')
119: call('constructor-observation', [binary, CFG, *seeds])
135: save(HERE / 'ore-results.json', summary)
144: kernel('cycle-generate', 'cycle', ROOT / '数据/样例/生产循环环带.json', '--max-ticks', 50, '--search-checkpoint-interval', 7, '--out', certificate_path)
154: save(relative_dir / 'record.json', relative)
159: save(relative_dir / 'certificate.json', relative_certificate)
166: save(HERE / 'relative-equality.json', dict(canonical_records_equal=True, unchanged_trace=relative['trace'] == original['trace'], source_fingerprints_unchanged=[r['sha256'] for r in relative['fingerprints']] == [r['sha256'] for r in original['fingerprints']], raw_record_sha256_before=sha(record_path), raw_record_sha256_after=sha(relative_path)))
177: kernel(f'{label}-checkpoint', 'checkpoint', rec, '--out', HERE / f'{label}-checkpoint.json')
188: kernel('load-shell-checkpoint', 'checkpoint', shell_path, '--out', destination)
189: save(HERE / 'load-shell-state.json', dict(source=str(shell_path), sha256=sha(shell_path), status=shell['status'], stop=shell['stop'], replay_input_ref=shell['replay_input_ref'], last_state=shell['last_state'], cycle=shell['cycle'], checkpoint_created=destination.exists()))
201: call('schema-validation', ['node', '-e', script, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], stdin=json.dumps(dict(schema=str(ROOT / '规格/内核输出.schema.json'), paths=list(map(str, paths)))))
205: save(HERE / 'schema-results.json', result['result'])
214: save(HERE / 'results.json', summary)
219: main()
```

## crates/kernel/复核/否证-r5-2-证据/audit_delivery.py

```text
assignments
7: HERE = Path(__file__).resolve().parent
8: REPORT = HERE.parent / '否证-r5-2.md'
18: path = Path(name)
sinks
12: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
26: write('write-boundary.json', {'checked_files': len(baseline), 'changed_files': changed, 'unchanged': not changed, 'comparison': 'sha256/size/mtime_ns'})
43: write('reader-review.json', {'status': 'pass', 'report': str(REPORT), 'finding_ids': expected, 'links_checked': len(links), 'manual_review': ['每条结论自包含且有独立试验、契约和实现依据', '普通有限合法性与生产域准入区分，交叉坏记忆不作合法输入证据', '路径归一化相等与原始字节摘要分别核验', '诊断复现与状态恢复、周期重跑分别判定', '未声称全量回归或一般规则证明，状态与当前实测一致'], 'evidence_extensions': sorted({path.suffix for path in files}), 'evidence_bytes_before_audit_result': sum((path.stat().st_size for path in files)), 'files_over_20MiB': large})
```

## crates/kernel/复核/否证-r5-2-证据/reproduce.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: ROOT = HERE.parents[3]
13: BIN = ROOT / 'target/release/kernel'
14: CFG = ROOT / '规格/内核配置-v1.json'
27: path = HERE / name
158: path = (folder / row['path']).resolve()
178: output = HERE / 'load-shell-checkpoint-output.json'
sinks
28: path.parent.mkdir(parents=True, exist_ok=True)
29: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
37: (HERE / (name + '.log')).write_text(json.dumps(metadata, ensure_ascii=False) + '\nSTDOUT\n' + result.stdout + '\nSTDERR\n' + result.stderr)
138: folder.mkdir(exist_ok=True)
calls
35: subprocess.run(command, cwd=cwd, text=True, capture_output=True)
45: save('commands.json', CASES)
58: subprocess.run(['node', '-e', source, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], input=json.dumps({'schema': str(ROOT / '规格/内核输出.schema.json'), 'paths': list(map(str, paths))}), capture_output=True, text=True, check=True)
63: save('schema-results.json', rows)
98: save(f'ore-{quantity}-raw.json', case)
100: kernel(f'ore-{quantity}-seed', 'seed', source, '--out', seed)
109: kernel(f'ore-{quantity}-cycle', 'cycle', seed, '--max-ticks', 2, '--no-record', '--out', certificate)
116: save('ore-crossed-invalid-memory.json', crossed)
119: save('domain-observations.json', {'legal_seed_observations': observations, 'legal_seed_differences': path_differences(*seeds), 'crossed_is_not_a_legal_seed': True, 'crossed_result': crossed_report})
127: kernel('fresh-cycle', 'cycle', ROOT / '数据/样例/生产循环环带.json', '--max-ticks', 50, '--search-checkpoint-interval', 7, '--out', certificate)
130: kernel('fresh-cycle-checkpoint', 'checkpoint', certificate, '--out', HERE / 'fresh-cycle-checkpoint.json')
144: save(f'{mode}-package/record.json', delivered)
147: save(f'{mode}-package/certificate.json', cert)
152: kernel(mode + '-record-checkpoint', 'checkpoint', record_path, '--out', HERE / (mode + '-record-checkpoint.json'))
168: save('path-observations.json', summary)
179: kernel('load-shell-checkpoint', 'checkpoint', shell, '--out', output)
180: save('load-shell-observations.json', {'source': str(shell), 'source_sha256': digest(shell), 'schema': data['schema'], 'replay_input_ref': data['replay_input_ref'], 'last_state': data['last_state'], 'verification': verified, 'checkpoint_exit': code, 'checkpoint_stdout_json': result, 'checkpoint_file_exists': output.exists()})
193: save('run-summary.json', {'status': 'reproduced', 'commands': len(CASES), 'schema_documents': len(documents), 'finding_ids': ['KR-r5-L2-01', 'KR-r5-L2-02', 'KR-r5-L2-03'], 'build_output': str(ROOT / 'target'), 'binary_sha256': digest(BIN)})
200: main()
```

## crates/kernel/复核/复核-r2-规格保真-证据/check_artifacts.py

```text
assignments
8: OUT = Path(__file__).resolve().parent
9: ROOT = OUT.parents[3]
22: evidence = ROOT / 'crates/kernel/evidence/revision-r1'
sinks
45: (OUT / '既有产物核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
19: verifier.run(data)
38: module.main()
50: main()
```

## crates/kernel/复核/复核-r2-规格保真-证据/probes.py

```text
assignments
9: OUT = Path(__file__).resolve().parent
10: ROOT = OUT.parents[3]
11: CONFIG = ROOT / '规格/内核配置-v1.json'
12: BIN = OUT / 'target/debug/kernel'
13: PROBE = OUT / 'target/debug/spec_review_probe'
27: source = ROOT / ('数据/样例/' + name + '.json')
47: record = OUT / (name + '-record.json')
sinks
21: p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
46: write(name + '-input', data)
49: subprocess.run(command, capture_output=True, text=True)
55: subprocess.run([str(PROBE), str(source), str(CONFIG), 'verify', str(record)], capture_output=True, text=True)
58: subprocess.run([str(PROBE), str(source), str(CONFIG), str(ticks), query], capture_output=True, text=True)
60: write(name + '-library', probe)
85: invoke(name, variant)
90: invoke('unowned-' + kind, data)
100: builder.generate('branch-base', [unit('source', '协议储存箱', 10, 7), unit('merge_a', '汇流器', 10, 10), unit('fork', '分流器', 10, 11), unit('gate', '物品准入口', 10, 12), unit('sink_a', '协议储存箱', 10, 13), unit('sink_b', '协议储存箱', 7, 9, 'r90'), unit('merge_b', '汇流器', 12, 10, 'r270'), unit('sink_c', '协议储存箱', 13, 8, 'r270')], [{'channel': origin, 'fork_unit': 'fork', 'outgoing_channel': chosen}])
119: invoke('branch-cut', data, 1, origin)
122: invoke('branch-retained', control, 1, origin)
123: write('探针结果', results)
128: main()
```

## crates/kernel/复核/完整性批评-2-证据/axis_coverage_union.py

```text
assignments
10: BASE = Path('/home/zhuran24/zmd-research-fresh/求解器/数据/样例')
sinks
calls
35: main()
```

## crates/kernel/复核/完整性批评-2-证据/independent_cycle_key.py

```text
assignments
sinks
calls
169: main(Path(sys.argv[1]))
```

## crates/kernel/复核/完整性批评-2-证据/measure_cycle_cost.py

```text
assignments
11: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
12: BIN = str(ROOT / 'target/release/kernel')
13: CFG = str(ROOT / '规格/内核配置-v1.json')
14: FIX = ROOT / 'crates/kernel/tests/fixtures'
27: out = Path(outdir)
41: dest = out / f'{name}-cycle-{n}.json'
sinks
28: out.mkdir(parents=True, exist_ok=True)
44: dest.unlink(missing_ok=True)
53: (out / '循环代价实测.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
20: subprocess.run(cmd, capture_output=True, text=True)
42: timed([BIN, 'cycle', src, '--config', CFG, '--max-ticks', str(n), '--out', str(dest)])
58: main(sys.argv[1])
```

## crates/kernel/复核/完整性批评-2-证据/tamper_cycle.py

```text
assignments
10: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
11: BIN = str(ROOT / 'target/release/kernel')
12: CFG = str(ROOT / '规格/内核配置-v1.json')
sinks
50: p.write_text(json.dumps(x, ensure_ascii=False))
calls
39: subprocess.run([BIN, 'verify-cycle', str(cert), '--config', CFG], capture_output=True, text=True)
51: subprocess.run([BIN, 'verify-cycle', str(p), '--config', CFG], capture_output=True, text=True)
60: main(Path(sys.argv[1]))
```

## crates/topology/tests/validation.rs

```text
assignments
sinks
748:     let mut child = std::process::Command::new("python")
832:     let result = std::process::Command::new("python")
calls
```

## 会议成果/任务书7执行/证据/仓库/check_warehouse.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
15: ROOT = BASE.parents[4]
sinks
177: (BASE / '核对结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
176: run()
```

## 会议成果/任务书7执行/证据/内核/audit_inputs.py

```text
assignments
sinks
8: (E / n).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
calls
16: write('formal-source-audit.json', {'formal': formal, 'catalog_sha256': digest(ROOT / '数据/正式静态目录.json'), 'conflict_resolution': '31ced2a24fef为09-21中间版本；本轮重读实际第36行并核完整SHA-256，采用d150b86b398f；登记已同步，未修改数据目录。'})
48: write('spec-merge-audit.json', {'files': merged, 'axis_count': len(axes), 'dispositions': counts, 'axis_locations': {k: {f: r[k]['line'] for f, r in tables.items()} for k in axes}, 'not_merged': [], 'partially_merged': [], 'additional_task8_proposals': '规格修改稿-任务8.md'})
63: write('input-reading-audit.json', {'inputs': inputs, 'plant_candidates': rows, 'semantic_scope': '正文按机制及支持域核读；重复轴行和完整JSON由程序逐项对照。源读取和结构核对不宣称游戏步进或独立席复核。'})
```

## 会议成果/任务书7执行/证据/内核/finalize_artifacts.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
4: D = ROOT / '会议成果/任务书7执行'
4: E = D / '证据/内核'
4: S = ROOT / '数据/样例/任务7内核'
165: dest = p.parent / target.split('#')[0]
sinks
6: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
147: (D / '内核验收.md').write_text(report)
159: (E / '文件清单.md').write_text('# 任务8完整文件清单\n\n日期：2026-09-21。仅列本席交付及修改的文件；完整SHA-256见同目录交付清单.json。指定target的二进制仅在build-binding.json登记，没有复制到证据目录。\n\n' + '\n'.join(('- `' + str(p) + '`' for p in files)) + '\n')
168: (E / 'final-check.log').write_text(log)
calls
16: write(E / 'protected-files.json', protected)
32: write(E / 'code-changes.json', change_rows)
36: write(E / 'cycle-results.json', cycle_rows)
38: write(E / 'build-binding.json', {'binary_path': str(binary), 'sha256': h(binary), 'build_command': ['cargo', 'build', '--release', '-p', 'kernel', '--target-dir', str(ROOT / 'target')], 'cwd': str(ROOT), 'builds': [{'id': r['evidence_id'], 'exit_code': r['exit_code'], 'output': r['stderr']} for r in commands if r['name'].startswith('build-')], 'source_sha256': {str(p): h(p) for p in sorted((ROOT / 'crates/kernel/src').glob('*.rs'))}, 'artifact_copied': False})
158: write(E / '结构化结果.json', result)
166: write(E / 'reader-review.json', {'status': 'passed', 'manual_review': ['当前结论与修订史分区；最终检查80+2、19记录/6结果口径统一', '所有证明先列前件；工程诊断与真实反例、全称证明分开', '跨规格七条逐项给原位置、现行文字、建议和理由；已核物理行号', '正式指纹以当前字节为准；owner无待补事实，配额报错未触发', '完整路径、构建版本、引用链接与文件清单核对'], 'links_checked': len(links), 'protected_files_checked': len(protected), 'quota_error': False})
172: write(E / '交付清单.json', {'status': 'sealed', 'manifest_self_hash_omitted': True, 'files': [{'path': str(p), 'sha256': h(p), 'bytes': p.stat().st_size} if p != E / '交付清单.json' else {'path': str(p), 'sha256': None, 'reason': 'manifest self hash omitted'} for p in files]})
```

## 会议成果/任务书7执行/证据/内核/generate_cases.py

```text
assignments
11: OUT = ROOT / '数据/样例/任务7内核'
12: CFG = ROOT / '规格/内核配置-v1.json'
12: BIN = ROOT / 'target/release/kernel'
41: path = OUT / (name + '.json')
sinks
11: OUT.mkdir(exist_ok=True)
15: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
43: seed.unlink()
100: (OUT / (n + '.json')).unlink()
calls
41: write(path, d)
42: run('seed-' + name, [BIN, 'seed', path, '--config', CFG, '--out', seed])
43: write(path, read(seed))
50: b.generate('无线模板', [unit('box', '协议储存箱', 10, 10), unit('power', '供电桩', 14, 10)])
65: b.generate('恢复模板', [unit('source', '协议储存箱', 10, 10), unit('gate', '物品准入口', 10, 13), unit('belt', '传送带', 10, 14), unit('sink', '协议储存箱', 10, 15)])
75: b.generate('链模板', [unit('a', '传送带', 10, 10), unit('b', '传送带', 10, 11), unit('c', '传送带', 10, 12)])
79: b.generate('身份切换模板', [unit('source', '协议储存箱', 10, 10), unit('gate', '物品准入口', 10, 13), unit('bypass', '传送带', 12, 13), unit('sink', '协议储存箱', 10, 14)])
84: b.generate('门环模板', [unit('a', '传送带', 10, 10, 'r90', 1), unit('gate', '物品准入口', 10, 11), unit('b', '传送带', 10, 12, 'r0', 1), unit('c', '传送带', 11, 12, 'r270', 1), unit('down', '传送带', 11, 11, 'r180'), unit('d', '传送带', 11, 10, 'r180', 1)])
89: b.generate('双箱模板', [unit('first', '协议储存箱', 10, 10), unit('second', '协议储存箱', 20, 10), unit('power1', '供电桩', 14, 10), unit('power2', '供电桩', 24, 10)])
95: b.generate('静止模板', [unit('belt', '传送带', 10, 10), unit('box', '协议储存箱', 15, 10), unit('machine', '粉碎机', 25, 10)])
101: write(E / 'sample-manifest.json', changes)
103: main()
```

## 会议成果/任务书7执行/证据/内核/run_command.py

```text
assignments
4: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
5: E = Path(__file__).resolve().parent
sinks
12: log.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\n')
13: index.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n')
calls
9: subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True, timeout=timeout)
18: run(sys.argv[1], sys.argv[2:], expected=None)
18: sys.stdout.write(r.stdout)
18: sys.stderr.write(r.stderr)
```

## 会议成果/任务书7执行/证据/内核/supplemental_checks.py

```text
assignments
5: CFG = ROOT / '规格/内核配置-v1.json'
5: BIN = ROOT / 'target/release/kernel'
6: source = ROOT / '数据/样例/任务7内核/静止成熟与暂停键.json'
9: path = E / 'negative/植物出库域-input.json'
sinks
9: path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
14: (E / 'supplemental-checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
calls
10: run('D3-finite-load', [BIN, 'check', path, '--config', CFG])
11: run('D3-production-domain', [BIN, 'check', path, '--config', CFG, '--cycle-domain'], expected=2)
```

## 会议成果/任务书7执行/证据/内核/validate_cases.py

```text
assignments
9: BIN = ROOT / 'target/release/kernel'
9: CFG = ROOT / '规格/内核配置-v1.json'
9: S = ROOT / '数据/样例/任务7内核'
9: O = E / 'runs'
9: N = E / 'negative'
17: dest = (O if code == 0 else N) / ((tag or name) + '.json')
64: dest = O / (name + '-cycle.json')
76: dest = O / 'budget-cycle.json'
77: dest = N / 'load-stop-cycle.json'
86: dest = O / '同种年龄分组-cycle.json'
101: dest = E / 'relative/cycle.json'
sinks
9: O.mkdir(exist_ok=True)
9: N.mkdir(exist_ok=True)
12: p.parent.mkdir(exist_ok=True, parents=True)
12: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
calls
14: write(E / 'checks.json', checks)
19: run('run-' + (tag or name), [BIN, 'run', S / (name + '.json'), '--config', CFG, '--ticks', str(ticks), '--out', dest, *extra], expected=code)
22: run('verify-record-' + (tag or name), [BIN, 'verify-record', dest, '--config', CFG])
36: run('check-' + name, [BIN, 'check', S / (name + '.json'), '--config', CFG])
37: run('old-input-rejected', [BIN, 'check', ROOT / '数据/样例/混做粉碎机两下游.json', '--config', CFG], expected=2)
62: run('checkpoint', [BIN, 'checkpoint', p, '--config', CFG, '--out', cp])
62: run('checkpoint-run', [BIN, 'run', cp, '--config', CFG, '--ticks', '1', '--out', O / 'checkpoint-record.json'])
66: run('cycle-' + name, args)
67: run('verify-cycle-' + name, [BIN, 'verify-cycle', dest, '--config', CFG])
76: run('cycle-budget', [BIN, 'cycle', S / '生产环带.json', '--config', CFG, '--max-ticks', '1', '--no-record', '--out', dest])
76: run('verify-budget', [BIN, 'verify-cycle', dest, '--config', CFG])
77: run('cycle-load-stop', [BIN, 'cycle', ROOT / '数据/样例/生产循环环带.json', '--config', CFG, '--max-ticks', '1', '--no-record', '--out', dest], expected=2)
77: run('verify-load-stop', [BIN, 'verify-cycle', dest, '--config', CFG])
82: write(p, v)
83: run('negative-' + label, [BIN, 'cycle', p, '--config', CFG, '--max-ticks', '1', '--no-record', '--out', N / (label + '-result.json')], expected=2)
86: write(p, v)
86: run('cycle-同种年龄分组', [BIN, 'cycle', p, '--config', CFG, '--max-ticks', '3', '--no-record', '--out', dest])
86: run('verify-同种年龄分组', [BIN, 'verify-cycle', dest, '--config', CFG])
92: write(p, v)
92: run('negative-' + label, [BIN, 'verify-record', p, '--config', CFG], expected=2)
99: write(p, v)
99: run('negative-' + label, [BIN, 'verify-cycle', p, '--config', CFG], expected=2)
113: write(dest, v)
113: run('verify-relative-cycle', [BIN, 'verify-cycle', dest, '--config', CFG])
114: run('batch-current', [BIN, 'verify-batch', O, '--config', CFG])
115: write(E / 'checks.json', checks)
118: main()
```

## 会议成果/任务书7执行/证据/否证/任务2/check_audit.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[5]
14: BASE = ROOT / '求解器/会议成果/任务书7执行'
28: source = BASE / relative
128: path = ROOT / row['path']
sinks
20: (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
71: (HERE / output).write_text(content)
calls
149: dump('重跑日志.json', runs)
155: dump('核对结果.json', result)
162: main()
```

## 会议成果/任务书7执行/证据/否证/任务2/validate_delivery.py

```text
assignments
8: HERE = Path(__file__).resolve().parent
9: ROOT = HERE.parents[5]
10: BASE = ROOT / '求解器/会议成果/任务书7执行'
11: DOC = BASE / '复核/否证-任务2.md'
59: target = (p.parent / dest.split('#')[0]).resolve()
sinks
17: (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
54: save('结构化结果.json', result)
71: save('交付校验.json', check)
76: main()
```

## 会议成果/任务书7执行/证据/否证/任务4/交付核对.py

```text
assignments
6: E = Path(__file__).resolve().parent
7: O = E.parents[2]
sinks
11: (E / '独立核查.log').write_text('command: ' + ' '.join(cmd) + '\nexit_status: ' + str(r.returncode) + '\nstdout:\n' + r.stdout + '\nstderr:\n' + r.stderr + '\nexplanation: 独立数据、几何、时间表算术及容量反例检查；游戏运行结论由复核正文手推。\n')
40: (E / '读者自审.md').write_text(audit)
48: (E / '交付核对结果.json').write_text(json.dumps(check, ensure_ascii=False, indent=2) + '\n')
53: (E / '交付清单.json').write_text(json.dumps(dict(status='done', files=manifest, self_hash='omitted to avoid self reference'), ensure_ascii=False, indent=2) + '\n')
calls
10: subprocess.run(cmd, capture_output=True, text=True)
```

## 会议成果/任务书7执行/证据/否证/任务4/独立核查.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: O = E.parents[2]
10: ROOT = O.parents[2]
11: A = O / '证据/植物运行'
179: H = max(0, (t - (h0 + 4)) // 2 + 1)
179: G = max(0, (t - (g0 + 4)) // 2 + 1)
sinks
13: (E / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
50: s[35].replace('，即使那个物品格中没有物品也一样', '')
54: s[66].replace('规则 `d150b86b398f`（09-21 上午恢复第 36 行后的现行值；任务 1 首次重锁时是 31ced2a24fef，主会话已同步）', '规则 `31ced2a24fef`')
130: (E / '候选A独立重放.log').write_text(cap.getvalue())
calls
27: save(start.name, current)
210: save('普通种子容量反例.json', witness)
228: save('容量反例合法摆放.json', dict(scope='66台植物机器及核心的容量见证；全关机无运输单位，R16不形成机器直连；非目标达标布局', units=units, seed_totals={'荞花种子': 1150, '砂叶种子': 2150}, normal_caches_empty=True, occupied_cells=len(occupied)))
230: save('独立核查结果.json', result)
```

## 会议成果/任务书7执行/证据/否证/任务4/生成交付.py

```text
assignments
5: E = Path(__file__).resolve().parent
6: O = E.parents[2]
7: REPORT = O / '复核/否证-任务4.md'
sinks
226: (E / '结构化结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
227: (E / '发现记录.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
243: REPORT.write_text('\n'.join(lines))
calls
```

## 会议成果/任务书7执行/证据/否证/任务5/交付核对.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: O = E.parents[2]
sinks
14: (E / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
42: dump('交付核对结果.json', {'status': 'PASS', 'exit_status': 0, 'findings': 24, 'verdicts': {'否证成立': 0, '否证不成立': 20, '无法判定': 4}, 'report_and_structured_records_identical': True, 'links_checked': len(links), 'input_fingerprints_unchanged': len(unchanged), 'source_scripts_executed': False, 'quota_error_observed': False, 'structured_output_tool_available': False})
```

## 会议成果/任务书7执行/证据/否证/任务5/独立核查.py

```text
assignments
11: E = Path(__file__).resolve().parent
12: O = E.parents[2]
13: ROOT = O.parents[2]
14: A = O / '证据/调试释放'
sinks
20: p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
42: write('版本逐项核对.json', versions)
204: write('逐格局部见证.json', {'scope': '一个固定合法次序的局部见证；三个开启间隔；不是全参数执行器', 'paths': {'PH': 3, 'HP': 17, 'PG': 3}, 'traces': local})
263: write('独立核查结果.json', result)
```

## 会议成果/任务书7执行/证据/否证/任务5/生成报告.py

```text
assignments
7: E = Path(__file__).resolve().parent
8: O = E.parents[2]
9: REPORT = O / '复核/否证-任务5.md'
sinks
265: REPORT.parent.mkdir(parents=True, exist_ok=True)
266: REPORT.write_text(''.join(parts))
267: (E / '发现记录.json').write_text(json.dumps(findings, ensure_ascii=False, indent=2) + '\n')
271: (E / '结构化结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/否证/任务6/交付自核.py

```text
assignments
4: E = Path(__file__).resolve().parent
5: B = E.parents[2]
sinks
35: (E / '工具可用性.json').write_text(json.dumps(tool, ensure_ascii=False, indent=2) + '\n')
38: (E / '结构化结果.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
47: (E / '交付清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/否证/任务6/独立核验.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: B = E.parents[2]
10: ROOT = B.parents[2]
11: A = B / '证据/相位认证'
sinks
19: p.parent.mkdir(parents=True, exist_ok=True)
20: p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
83: (E / '作者重放.log').write_text(log.getvalue())
85: (E / '作者重放.log').write_text(log.getvalue())
calls
46: write('审查输入指纹.json', {'schema': 'task6-independent-review-inputs-v1', 'files': rows})
200: write('独立核验结果.json', result)
```

## 会议成果/任务书7执行/证据/否证/任务6/生成报告.py

```text
assignments
5: E = Path(__file__).resolve().parent
6: B = E.parents[2]
sinks
315: report.write_text(''.join(parts))
320: (E / '结构化结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
321: (E / '逐项论证.json').write_text(json.dumps(details, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/否证/任务7/写报告.py

```text
assignments
7: E = Path(__file__).resolve().parent
8: B = E.parents[2]
9: REPORT = B / '复核/否证-任务7.md'
sinks
253: (E / '结构化结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
254: (E / '逐条发现详情.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n')
306: REPORT.write_text('\n'.join(text))
calls
```

## 会议成果/任务书7执行/证据/否证/任务7/最终核查.py

```text
assignments
9: E = Path(__file__).resolve().parent
10: B = E.parents[2]
sinks
50: (E / '最终核查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/否证/任务7/独立核验.py

```text
assignments
14: HERE = Path(__file__).resolve().parent
15: BASE = HERE.parents[2]
16: AUTHOR = BASE / '证据/密排'
17: J = json.loads((BASE / '密排布局.json').read_text())
212: path = AUTHOR / name
sinks
35: (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
239: write('逐格独立核验.json', dict(status='pass', scope='independent static geometry, arithmetic, read-only author reproduction', metrics=stats, checks=checks, channels=channels, routes=routes, bridges=bridges, power=power, planned_capacity=plans, product_segments=product, manifests=manifests))
242: write('作者脚本只读复算.json', replays)
```

## 会议成果/任务书7执行/证据/复核接口/bridge_delay_witness.py

```text
assignments
12: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
12: E = Path(__file__).resolve().parent
sinks
65: (E / 'bridge-delay-witness.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核接口/check_certificates.py

```text
assignments
7: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
7: E = Path(__file__).resolve().parent
90: source = read((p.parent / r['replay_input_ref']['path']).resolve())
sinks
112: (E / 'certificate-independent.json').write_text(json.dumps({'checks': checks, 'references': references}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核接口/check_contracts.py

```text
assignments
5: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
5: E = Path(__file__).resolve().parent
sinks
39: (E / 'contracts-independent.json').write_text(json.dumps({'checks': checks, 'formal_sources': formal, 'catalog_sha256': hashlib.sha256((B / '数据/正式静态目录.json').read_bytes()).hexdigest(), 'binary_sha256': binding['sha256'], 'dispositions': dict(Counter((v['disposition'] for v in axes.values()))), 'scope': 'current published contracts and current binary/source; historical references classified in report'}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核接口/check_geometry.py

```text
assignments
8: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
8: E = Path(__file__).resolve().parent
9: P = B / '会议成果/任务书7执行/密排布局.json'
sinks
15: (E / name).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
calls
101: write('geometry-independent.json', {'input_sha256': hashlib.sha256(P.read_bytes()).hexdigest(), 'checks': checks, 'summary': summary, 'routes': routestats, 'power': power, 'bridges': bridges, 'channels': edges})
```

## 会议成果/任务书7执行/证据/复核接口/check_runs.py

```text
assignments
6: E = Path(__file__).resolve().parent
sinks
65: (E / 'runs-independent.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核接口/probe_bridge.py

```text
assignments
11: BIN = ROOT / 'target/release/kernel'
11: CFG = ROOT / '规格/内核配置-v1.json'
30: record = E / (name + '-record.json')
sinks
28: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
34: (E / 'bridge-probe-results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
calls
23: b.generate('bridge-template', units)
29: run(name + '-seed', [BIN, 'seed', p, '--config', CFG, '--out', seed])
29: run(name + '-check', [BIN, 'check', seed, '--config', CFG])
30: run(name + '-run', [BIN, 'run', seed, '--config', CFG, '--ticks', '2', '--format', 'full_state_each_instant', '--out', record])
30: run(name + '-verify', [BIN, 'verify-record', record, '--config', CFG])
```

## 会议成果/任务书7执行/证据/复核接口/run_review.py

```text
assignments
6: ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
7: E = Path(__file__).resolve().parent
13: dest = E / 'commands.json'
sinks
13: dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
14: (E / (label + '.log')).write_text(p.stdout + p.stderr)
23: (E / 'build-binding.json').write_text(json.dumps({'binary': str(b), 'sha256': hashlib.sha256(b.read_bytes()).hexdigest()}, indent=2) + '\n')
calls
11: subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
22: run('build', ['cargo', 'build', '--release', '-p', 'kernel', '--target-dir', ROOT / 'target'])
29: run('original-batch', [ROOT / 'target/release/kernel', 'verify-batch', ROOT / '会议成果/任务书7执行/证据/内核/runs', '--config', ROOT / '规格/内核配置-v1.json'])
```

## 会议成果/任务书7执行/证据/复核接口/write_report.py

```text
assignments
5: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
5: E = Path(__file__).resolve().parent
6: P = B / '会议成果/任务书7执行/复核/接口与证据.md'
sinks
22: (E / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
30: P.write_text('\n'.join(lines) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核推导/check_derivation.py

```text
assignments
7: HERE = Path(__file__).resolve().parent
sinks
103: (HERE / '核算结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/复核推导/validate_deliverables.py

```text
assignments
8: HERE = Path(__file__).resolve().parent
9: ROOT = HERE.parents[4]
47: report_path = HERE / '交付校验.json'
55: target = (Path(path).parent / dest.split('#')[0]).resolve()
sinks
48: report_path.write_text('{}\n')
77: report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/密排/核验.py

```text
assignments
7: BASE = Path(__file__).resolve().parents[2]
7: EV = Path(__file__).resolve().parent
8: J = json.loads((BASE / '密排布局.json').read_text())
sinks
10: (EV / name).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
calls
64: save('自动通道.json', channels)
95: save('桥与供电.json', dict(bridges=bridge, power=power))
129: save('核验结果.json', dict(status='pass', scope='geometry, source binding, arithmetic; direct arguments in markdown', checks=checks, metrics=metrics))
```

## 会议成果/任务书7执行/证据/密排/生成.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh')
8: OUT = ROOT / '求解器/会议成果/任务书7执行'
9: EV = OUT / '证据/密排'
sinks
11: p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
216: (EV / '逐单位与路径.md').write_text('\n'.join(lines) + '\n')
calls
24: write(EV / '输入指纹.json', sources)
194: write(OUT / '密排布局.json', layout)
217: write(EV / '工具与输入核查.json', dict(structured_output_tool_available=False, return_format='final JSON + evidence JSON', full_read_sources=len(sources), candidate_summary=[dict(id=c['id'], machines=len(c['machines']), feeds=len(c['feeds']), all_actual_rates_null=all((x['proven_actual_rate_per_tick'] is None for x in c['feeds']))) for c in feed['candidates']], no_kernel_build=True, no_kernel_execution=True))
```

## 会议成果/任务书7执行/证据/推导修订/核验.py

```text
assignments
9: BASE = Path('/home/zhuran24/zmd-research-fresh')
10: EVIDENCE = Path(__file__).resolve().parent
11: REPORT = BASE / '求解器/会议成果/任务书7执行/推导复核范围.md'
55: path = Path(item['path'])
65: path = Path(item['path'])
sinks
49: (EVIDENCE / '核验结果.json').write_text('{"status":"running"}\n')
184: (EVIDENCE / '核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
198: (EVIDENCE / '核验结果.json').write_text(json.dumps({'status': 'failed', 'error': repr(error)}, ensure_ascii=False, indent=2) + '\n')
calls
196: main()
```

## 会议成果/任务书7执行/证据/植物运行/修订核验.py

```text
assignments
9: E = Path(__file__).resolve().parent
10: O = E.parent.parent
11: ROOT = O.parents[2]
sinks
169: (E / '修订核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/植物运行/提取与算术.py

```text
assignments
8: HERE = Path(__file__).resolve().parent
9: OUT = HERE.parent.parent
10: ROOT = OUT.parents[2]
11: OLD = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
19: B = json.loads((ROOT / '求解器/数据/候选B/contract.json').read_text())
38: A = runpy.run_path(str(OLD / 'portmatch.py'))
sinks
16: p.write_text(value)
calls
230: write(OUT / '送料与接口.json', interface)
231: write(HERE / '算术与图核验.json', checks)
```

## 会议成果/任务书7执行/证据/植物运行/来源增量核查.py

```text
assignments
5: E = Path(__file__).resolve().parent
sinks
19: b.replace('，即使那个物品格中没有物品也一样，能送多少送多少'.encode(), '，能送多少送多少'.encode())
22: ls[66].replace('规则 `d150b86b398f`（09-21 上午恢复第 36 行后的现行值；任务 1 首次重锁时是 31ced2a24fef，主会话已同步）', '规则 `31ced2a24fef`')
34: (E / name).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/植物运行/核验.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: O = E.parent.parent
sinks
12: p.write_text(s)
calls
22: subprocess.run([sys.executable, '-B', str(E / '提取与算术.py')], capture_output=True, text=True)
113: dump(E / '局部结构.json', geometries)
170: dump(E / '局部时间表核对.json', traces)
206: dump(E / '核验结果.json', results)
```

## 会议成果/任务书7执行/证据/汇总/核验.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: E = HERE.parent.parent
13: ROOT = E.parents[2]
14: REPORT = HERE / '输入与核验.json'
sinks
88: REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
71: subprocess.run(argv, cwd=ROOT / '求解器', capture_output=True, text=True)
```

## 会议成果/任务书7执行/证据/相位认证/核验.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: B = E.parent.parent
10: ROOT = B.parent.parent.parent
sinks
20: (E / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
47: write('读取核查.json', {'files': read_audit, 'scope': '全部列入输入逐字节读取；JSON遍历、Python静态解析；正文引用另作语义核查'})
117: write('设计律核查.json', {'local_instances': geometry_results, 'full_AB_realization': '未提供实际几何，保持待核', 'direction': '局部结构定理前件检查'})
230: write('窗口与算术.json', {'recipes': recipes, 'reverse_balance': {'b': str(b), 'g': str(g), 'c': str(c), 'refining_formula': '30*b+60*c+r', 'plant_formula': '25*b/3+20*c'}, 'gate_samples': sample_rows, 'sample_scope': '单门合法旧窗口、单一持续备货、恰1tick排空；只查界的算术', 'k5_global_graph_elimination_proved': False})
289: write('核验结果.json', result)
```

## 会议成果/任务书7执行/证据/终修/修订.py

```text
assignments
8: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
9: E = B / '会议成果/任务书7执行/证据/终修'
10: D = B / '会议成果/任务书7执行'
11: R = sha256((B.parent / '《明日方舟：终末地》游戏规则.txt').read_bytes()).hexdigest()
sinks
21: path.write_text(after)
28: s.replace(a, b)
31: s.replace(OLD, R)
34: s.replace('主会话三审第11—31、49—53行', '主会话三审第11—31、49—54行')
52: s.replace(OLD, R)
56: s.replace('本表是修改请求，不是已完成的实现。', '本表保留首次提交的修改请求位置；当前已汇入结果见规格回填的汇入记录与本次终修汇总。')
57: s.replace('空箱冷却及扣格后效以有据机制或覆盖报告处理', '所有尝试后冷却已定；歧义部分扣格后效以有据机制或覆盖报告处理')
58: s.replace('空箱冷却具体未决保留', '空箱及零发送冷却采用已定every_attempt')
63: s.replace(OLD, R)
66: s.replace('本次修订文字待独立复核。账面为', '本次任务7终修已核R36及来源影响，其余历史增量的复核范围见末尾记录。账面为')
67: s.replace('正常制造门控使一台机器至多留一批', '同种物品在一座桥上同时至多占一轴（R13），两轴同种服务另核；正常制造门控使一台机器至多留一批')
68: s.replace('日期：2026-09-21。修订输入为 397 行', '历史执行记录，截止2026-09-21任务3首次修订；其中来源及空箱登记由文末终修记录更正。修订输入为 397 行')
74: s.replace('SHA-256 前 12 位与任务给定值一致。', 'SHA-256前12位按磁盘现文核定；完整R为`' + R + '`。')
81: s.replace(OLD, R).replace('本次重写文字待独立复核', '重写全文的整体复核范围保持；本次终修已核现行来源及R36对所列收支/产能结论的影响')
81: s.replace(OLD, R)
84: s.replace(OLD, R)
85: s.replace('三份指定独立复核的裁定全部采纳，48个编号逐项处理', '三份指定报告的48个编号按实质证据分层承接；任务7终修另外处理AX/IE发现')
89: s.replace('裁定确认现文正确，保留', '保留所引正面论证及明确前件')
90: s.replace('| L-N01 | 已证窄式／否证不成立 | 保留所引正面论证及明确前件 |', '| L-N01 | 已定事实及范围核对／该攻击未成立 | r2§3.1已核失败前移与调度断点；C82应用承接旧审 |')
91: s.replace('| L-N02 | 已证窄式／否证不成立 | 保留所引正面论证及明确前件 |', '| L-N02 | 条件后果核对／该攻击未成立 | r2§3.2重核停流后果，偏向其余旧数学承接旧审 |')
99: s.replace('相位§1.1、§7：R前12位更新为31ced2a24fef', '相位§1.1、§7：R前12位按终修更新为d150b86b398f')
100: s.replace('| P-N01 | 已证窄式／否证不成立 | 保留所引正面论证及明确前件 |', '| P-N01 | 净需求分数复算／该攻击未成立 | 保留执行复核§3的净需求推导；旧几何和轨迹未重放 |')
101: s.replace('| P-N05 | 已证窄式／否证不成立 | 核实原句正确并保留，另作状态补记 |', '| P-N05 | 历史复核存在及版本核对 | 保留文档事实；不据此新增运行证明 |')
102: s.replace('无编号承接项也已核对：', '无编号旧审承接项（本轮未重核其完整推导与旧算例）：')
103: s.replace('R36环境与空箱断点', 'R36环境与已定空箱冷却')
104: s.replace('现行指纹见第1节。', '任务3首次修订指纹见第1节历史表，当前终修指纹见证据/终修/交付清单.json。')
117: s.replace('[核验脚本](证据/推导修订/核验.py)复核', '首次修订的历史[核验脚本](证据/推导修订/核验.py)曾复核')
126: s.replace('本席新增结论待独立复核。', '已有复核按被审指纹和条目承接；本次终修核AX-04引用及其条件范围。')
138: s.replace('状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。', '状态：任务2、6及任务8 S8-01—04的当前工程契约已汇入；IE-07精确键冲突已终修。当前Rust行为按内核验收/IE-06范围承接，PC-06真实调度对应仍开放。')
151: s.replace('状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。', '状态：任务2、6和任务8 S8-01/04/07输入支持说明已汇入，IE-07关联冲突已终修。实际种子支持与完整起法认证分列。')
161: s.replace('状态：任务书7任务2、6证书契约已汇入，schema升版；Rust生成与语义验收由任务8实现，新增条件证明待独立复核。', '状态：任务2、6证书契约与任务8 S8-05/06工程说明已汇入。IE-07已终修；当前Rust生成及独立重放按任务8/IE-06支持域使用，真实前向对应保持未决。')
162: s.replace('须重算并生成v3', '须重算并生成kernel-output-v4')
163: s.replace('须重新校验来源投影、完整回放并生成v3', '须重新校验来源投影、完整回放并生成kernel-output-v4')
171: s.replace('状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。', '状态：任务2、6规则与任务8工程支持说明已汇入；IE-07关联S8-06已终修。99轴处置保持，已实现机制和未证真实对应分别登记。')
172: s.replace('Rust实现尚待任务8同步部分接收和准入口条件恢复；配置被装载不构成这些行为已实现的证据。', 'Rust已实现部分接收、每次尝试冷却和准入口当前条件恢复，定向运行与独立重放见任务8/IE-06；完整真实调度与全部后态仍按PC-06等义务登记。')
173: s.replace('当前Rust传输函数仍为旧实现，任务8须迁移部分接收、残留格与台账', '当前Rust已实现部分接收及台账；严格部分接收且同种多编号格的扣格歧义提交前停止')
174: s.replace('当前Rust身份锁存实现待任务8替换；恢复后的接通记账、轮询和同刻组织仍待任务6', '当前Rust已按原几何候选恢复三原因；恢复后的接通记账、轮询和同刻组织的一般真实对应仍待任务6')
175: s.replace('部分接收、门条件恢复修改后的完整后继仍缺任务6推导与任务8实现', '部分接收及门条件恢复已有任务8实现和IE-06定向重放，完整真实后继仍缺任务6的PC-06推导')
185: s.replace('状态：内核席提交，尚未写入规格目录。', '状态：S8-01—07已经任务7终修核对并汇入规格正文；原位置行号绑定首次提交版本。')
186: s.replace('交规格席落地', '当前落点见文末终修记录').replace('规格席落地后须重锁受影响输入/证书的依赖并重新验收；本稿没有直接改规格文件。', '当前落地后须按新文字重新生成关联证据，原运行证书按旧指纹封存；本次定向重放见复核/终修记录.md。')
186: s.replace('交规格席落地', '当前落点见文末终修记录')
188: s.replace('独立接口与证据席的复核待交', '独立接口复核IE-06已交，IE-07契约冲突由本次终修处理')
189: s.replace('该稿尚未汇入规格目录；当前schema已接受实际输出。', '该稿S8-01—07现已由终修席汇入；当前schema接受实际输出的范围保持。')
191: s.replace('## 1. 依据与证据层级', '前六节为任务1首次执行史料，截止2026-09-21上午恢复R36前；后续当前口径见“汇入记录”及文末“终修记录”。\n\n## 1. 依据与证据层级')
195: (E / '正文修订差异.md').write_text('# 终修正文差异\n\n执行记录，截止2026-09-21；仅含被修订段落差异，当前正文为规则应用入口。\n\n' + '\n'.join(('## ' + Path(x['path']).name + '\n\n```diff\n' + x['diff'] + '```\n' for x in changes)))
196: (E / '修改清单-第一段.json').write_text(json.dumps([{k: v for k, v in x.items() if k != 'diff'} for x in changes], ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/终修/核验.py

```text
assignments
14: B = Path('/home/zhuran24/zmd-research-fresh/求解器')
15: D = B / '会议成果/任务书7执行'
16: E = Path(__file__).resolve().parent
92: R = (B.parent / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
144: out = E / 'runs' / f'{label}-cycle.json'
sinks
20: (E / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
27: (E / (name + '.log')).write_text(r.stdout + r.stderr)
124: (E / (name + '.log')).write_text(out.getvalue())
139: (E / 'runs').mkdir(exist_ok=True)
calls
25: subprocess.run(args, cwd=B, text=True, capture_output=True)
129: write('跨桥定向查错.json', {'scope': '三组有限精确分数时序，只核局部事件与数值；普遍界由正文引理证明，未扫描全参数', 'cases': probe})
145: command(label + '-cycle', [binary, 'cycle', str(p), '--config', cfg, '--max-ticks', '5', '--no-record', '--out', str(out)])
176: write('commands.json', commands)
177: write('核验结果.json', {'status': 'pass', 'checks': checks, 'check_count': len(checks), 'changed_files': changes, 'unchanged_count': len(original) - len(changes), 'scope': '正文/版本/受保护文件、静态几何、局部精确分数见证及三个当前诊断周期；无全厂认证'})
181: main()
183: write('commands.json', commands)
183: write('核验结果.json', {'status': 'fail', 'error': repr(ex), 'checks': checks})
```

## 会议成果/任务书7执行/证据/规格/audit_backfill.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: W = R / '求解器'
3: S = W / '规格'
3: E = W / '会议成果/任务书7执行/证据/规格'
sinks
5: (E / n).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
calls
73: subprocess.run(cmd, text=True, capture_output=True)
76: save('historical-references.json', refs)
82: save('loader-evidence.json', {'code': load_code, 'interpretation': 'reference()检查文件原始字节sha256；Catalog::load比较serde_json::Value相等，并非原始字节逐字相等；catalog和config编译期include_str使用当前文件。topology也include同一路径，本次按授权只编译kernel。另有样例检查器SOURCE_HASHES已仅同步两项哈希，见secondary-registry.json；候选B来源清单及各baseline属于既有证据指纹，不刷新其通过结果。'})
85: save('self-check.json', report)
```

## 会议成果/任务书7执行/证据/规格/backfill_specs.py

```text
assignments
3: ROOT = Path('/home/zhuran24/zmd-research-fresh')
3: SPEC = ROOT / '求解器/规格'
3: OUT = ROOT / '求解器/会议成果/任务书7执行/证据/规格'
sinks
8: docs[n].replace(a, b)
220: docs[n].replace('级二提升', '正式循环对应证明').replace('级二', '正式循环对应').replace('级一', '生产部分')
220: docs[n].replace('级二提升', '正式循环对应证明').replace('级二', '正式循环对应')
220: docs[n].replace('级二提升', '正式循环对应证明')
244: note.replace('[运行语义§1](运行语义.md)', '本文§1')
257: (SPEC / n).write_text(new)
258: (OUT / '旧条款摘录.md').write_text(historical)
259: (OUT / 'spec-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n')
266: cat.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
267: (OUT / 'catalog-semantic-changes.json').write_text(json.dumps({'path': str(cat), 'diff': list(difflib.unified_diff(cat_before.splitlines(), cat.read_text().splitlines(), lineterm='', n=2))}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/规格/final_text_fixes.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh/求解器')
3: E = R / '会议成果/任务书7执行/证据/规格'
sinks
5: old.replace('旧正式循环对应名目撤下', '旧“级二”名目撤下').replace('生产部分生产部分周期', '生产部分周期')
5: old.replace('旧正式循环对应名目撤下', '旧“级二”名目撤下')
7: new.replace('各处置数量按当前内核配置统计，旧55本版选值、18停止轴、11已定属于2026-09-20史料；', '当前配置共99轴：18项已定、47项本版选值、19项工程停止、15项输入量化；')
8: new.replace('T12；T12；open', 'T12；open')
10: p.write_text(new)
11: (E / 'reader-fixes.json').write_text(json.dumps(edits, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/规格/polish_contracts.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: S = R / '求解器/规格'
3: E = R / '求解器/会议成果/任务书7执行/证据/规格'
sinks
10: new.replace(a, b)
12: p.write_text(new)
51: p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
53: (E / 'polish-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n')
55: p.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/规格/relock_sources.py

```text
assignments
3: ROOT = Path('/home/zhuran24/zmd-research-fresh')
4: OUT = ROOT / '求解器/会议成果/任务书7执行/证据/规格'
sinks
6: (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
35: cat.write_text(json.dumps(new, ensure_ascii=False, indent=2) + '\n')
calls
17: save('before.json', {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': [{'path': str(p), 'sha256': digest(p), 'lines': len(p.read_text().splitlines())} for p in dict.fromkeys(tracked)], 'protected': [str(p) for p in protected]})
19: subprocess.run(cmd, text=True, capture_output=True)
20: save('sha256sum.json', {'command': subprocess.list2cmdline(cmd), 'cwd': str(ROOT), 'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
36: save('source-relock.json', {'checks': checks, 'catalog_before': hashlib.sha256(json.dumps(old, ensure_ascii=False).encode()).hexdigest(), 'catalog_after': digest(cat), 'note': 'catalog_before is parsed-value serialization digest; original byte digest is before.json. task.goal/conditions also refreshed from all current task lines.'})
```

## 会议成果/任务书7执行/证据/规格/sync_secondary_registry.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: E = R / '求解器/会议成果/任务书7执行/证据/规格'
sinks
9: new.replace(sha, actual)
10: p.write_text(new)
11: (E / 'secondary-registry.json').write_text(json.dumps({'path': str(p), 'original_sha256': hashlib.sha256(old.encode()).hexdigest(), 'final_sha256': hashlib.sha256(new.encode()).hexdigest(), 'reason': 'SOURCE_HASHES是仍执行的正式源比对登记（原L58—62，读取在L720、L734—735）；按任务1同步全部现行登记，仅替换规则/任务两个哈希字面量，其余字节及算法保持。原样例、投影和历史结果不重生成。', 'diff': list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm='', n=2))}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/规格/verify_build_load.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: W = R / '求解器'
3: E = W / '会议成果/任务书7执行/证据/规格'
53: out = json.loads((E / 'seed-output.json').read_text())
sinks
5: (E / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
10: (E / (name + '.log')).write_text('$ ' + shlex.join(args) + '\nCWD=' + str(W) + '\nEXIT_CODE=' + str(r.returncode) + '\nSTDOUT:\n' + r.stdout + '\nSTDERR:\n' + r.stderr)
calls
9: subprocess.run(args, cwd=W, text=True, capture_output=True)
11: save('commands.json', commands)
47: save(input_path.name, sample)
48: save('sample-migration.json', {'source': str(p), 'source_sha256': h(p), 'derived': str(input_path), 'changed_json_paths': sorted(changes), 'preserved_geometry': orig['layout'] == sample['layout'], 'preserved_settings': orig['settings'] == sample['settings'], 'preserved_inventory': orig['initial_state']['nonwarehouse']['value']['inventory'] == state['inventory'], 'scope': '仅迁移引用、配置值/生命周期及其种子投影；无箱、无门、无调试动作。合成初态可达性未证。'})
49: run('cargo-build', ['cargo', 'build', '--release', '-p', 'kernel', '--target-dir', str(W / 'target')])
51: run('kernel-seed', [str(bin), 'seed', str(input_path), '--config', str(config_path), '--out', str(E / 'seed-output.json')])
52: run('kernel-check', [str(bin), 'check', str(E / 'seed-output.json'), '--config', str(config_path)])
55: save('load-verification.json', {'status': 'passed', 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'binary': {'path': str(bin), 'sha256': h(bin)}, 'input': {'path': str(input_path), 'sha256': h(input_path)}, 'seed_output': {'path': str(E / 'seed-output.json'), 'sha256': h(E / 'seed-output.json')}, 'catalog_sha256': h(W / '数据/正式静态目录.json'), 'config_sha256': h(config_path), 'axis_sha256': h(W / '规格/选择点参数轴.md'), 'trajectory_executed': False, 'interpretation': 'seed先通过Input::parse_with_base的目录引用、编译期目录与三份正式源检查，再派生初态调度上下文；check复读派生输入。未运行step，不认证新传输、门恢复、完整语义或达标。'})
```

## 会议成果/任务书7执行/证据/规格/write_deliverable.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: W = R / '求解器'
3: D = W / '会议成果/任务书7执行'
3: E = D / '证据/规格'
sinks
5: (E / n).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
12: (E / '执行说明.md').write_text("# 规格回填执行记录\n\n日期：2026-09-21。范围：源指纹、规格/配置/schema回填及一个样例的装载验证。\n\n关键命令、cwd、退出码和完整stdout/stderr见commands.json与三个同名日志；源文件sha256sum原始输出见sha256sum.json。首次构建实际编译kernel，输出为`Compiling kernel v0.1.0`和`Finished release profile [optimized] target(s) in 5.40s`；文字自审修改轴表说明后重跑相同命令，最终日志为增量构建0.01s，退出码均0。最终装载证据以load-verification.json锁定的版本为准。\n\nbackfill_specs.py首次在冗余替换断言处退出1，未写规格；删去重复要求后完成九份规格写入。polish_contracts.py首次因重复标点替换断言退出1，先前两个文件的修正已写入；改为幂等替换后继续完成，最终文件由manifest.json及自核锁定。这两项属于编写脚本的字符串定位错误。\n\naudit_backfill.py最初因`ModuleNotFoundError: No module named 'jsonschema'`退出1。最终用标准库解析schema，并将五处删除的枚举加回，核恢复字节SHA-256等于修改前值，证明schema改动只限五处枚举删除；没有声称运行第三方JSON Schema元模式验证。最终39项自核通过。\n\n没有遇到OpenAI/Codex额度、配额、usage limit或rate limit错误。\n\n未运行git；未改三份正式文件、候选约束、推导正文或Rust源码；模拟器未访问。编译产物只在指定target中；证据目录只保留脚本、日志、JSON和Markdown，target产物仅以路径/哈希登记。\n")
113: (D / '规格回填.md').write_text(report)
calls
10: save('for-owner.json', owner)
116: save('build-products.json', {'scope': 'mtime >= before.json time; generated or refreshed under the required build target. No copies.', 'files': build})
123: save('manifest.json', {'status': 'rule_backfill_completed', 'error': None, 'scope': '任务1规则回填；非完整语义获证', 'files': [{'path': str(p), 'action': 'modified' if p in modified else 'created', 'sha256': h(p), 'before_sha256': base_hash.get(str(p))} for p in files], 'self': str(E / 'manifest.json'), 'self_hash_note': 'manifest does not recursively hash itself', 'build_products': str(E / 'build-products.json'), 'for_owner': owner, 'checks_passed': len(check['checks'])})
```

## 会议成果/任务书7执行/证据/规格/汇入/audit_merge.py

```text
assignments
5: R = Path('/home/zhuran24/zmd-research-fresh')
5: S = R / '求解器/规格'
5: E = Path(__file__).resolve().parent
6: AJV = Path('/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js')
7: SCHEMA = json.loads((S / '内核输出.schema.json').read_text())
sinks
61: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1').replace('cycle-normalization-v1', 'cycle-normalization-v2')
61: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1')
61: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1')
61: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3')
61: x.replace('kernel-output-v3', 'kernel-output-v4')
147: (E / 'audit-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
136: subprocess.run(['node', '-e', node_script, str(AJV)], input=json.dumps({'schema': SCHEMA, 'cases': cases}), text=True, capture_output=True)
```

## 会议成果/任务书7执行/证据/规格/汇入/finish_merge.py

```text
assignments
4: R = Path('/home/zhuran24/zmd-research-fresh')
4: S = R / '求解器/规格'
4: T = R / '求解器/会议成果/任务书7执行'
4: E = Path(__file__).resolve().parent
20: record = T / '规格回填.md'
sinks
41: record.write_text(record.read_text() + ''.join(lines))
45: (E / 'audit.log').write_text(p.stdout + p.stderr)
51: (E / 'commands.json').write_text(json.dumps(cmdrec, ensure_ascii=False, indent=2) + '\n')
56: (E / '执行核查.md').write_text(f"# 规格汇入执行核查\n\n日期：2026-09-21。性质：作者执行记录与证据索引；规格汇入完成，新增条件证明的独立复核及任务8内核运行验收仍待执行。\n\n输入版本见before.json，最终版本见manifest.json。规则第36行现行为d150b86b398f，任务2稿中的旧指纹与零传输未决已按任务6 SP-01及三审§6修订。两稿其余衔接与逐文件处置见../../../../规格回填.md的“汇入记录”（实际相对链接见下文）。\n\n实际运行`{sys.executable} -B {E / 'audit_merge.py'}`，cwd=`{R}`，退出{p.returncode}。输出：\n\n```text\n{p.stdout.strip()}\n```\n\n检查包括99轴三份表与配置的恰集、处置及生命周期；旧口径扫描；保护文件及源稿原字节；链接；AJV 8.20.0 Draft 2020-12元校验与25个正反例。共{report['passed']}项作者检查通过、{report['failed']}项失败。多项属于逐轴核对，数量不表示独立游戏行为样例数。\n\nschema合成材料只存在于自核进程内。旧环带证书作为形状脚手架的来源按audit-results.json锁定，其内容和文件均未修改。合成proof路径和全零摘要只是校验占位，语义验收会要求真实文件与内容；本次未发出生产或完整基地周期证书。真实入库、玩家拿取与数学代表调整分别有字段与守恒义务；形状互相冒充的负例拒收。\n\n读者自审核了：当前事实与史料分区、头部状态、已定和待证范围、22/44/18/15处置计数、正式行号、链接、条件前件、代码实现边界。修订脚本保留在本目录供审阅，按汇入前版本顺序执行；完成后只重跑audit_merge.py。脚本中的早期错误及修复见commands.json的implementation_attempts，最终自核已重跑。\n\n本轮仅写11份顶层规格、规格回填.md末尾和本证据目录；规格
79: p.write_text(p.read_text().replace('见../../../../规格回填.md的“汇入记录”（实际相对链接见下文）', '见下文链接的规格回填.md“汇入记录”'))
79: p.read_text().replace('见../../../../规格回填.md的“汇入记录”（实际相对链接见下文）', '见下文链接的规格回填.md“汇入记录”')
87: (E / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
44: subprocess.run(command, cwd=R, text=True, capture_output=True)
```

## 会议成果/任务书7执行/证据/规格/汇入/merge_bodies.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: S = R / '求解器/规格'
3: T = R / '求解器/会议成果/任务书7执行'
4: RH = hashlib.sha256((R / '《明日方舟：终末地》游戏规则.txt').read_bytes()).hexdigest()
sinks
6: (S / n).write_text(s)
11: s.replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', RH).replace('31ced2a24fef', RH[:12])
11: s.replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', RH)
12: s.replace('状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。', '状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。')
16: s.replace('通用event-order-v2周期槽函数和event-order-v3/order-expr-v1纯函数AST只扩展per_instant的表示，本版运行仍不支持。', '判定规则整场固定（任务L15）；旧per_instant时间函数改变相对序的编码只作史料或扩大探索诊断，当前游戏证书准入拒绝这种改序。')
17: s.replace('单级、存货侧不请求阻尼是本版选值，不证明一般规则豁免。', '对非运输取货侧，零级无出货；仅一个非空级时，规则L30只需判断该级有无可动成员，阻尼和最早接通不参与级间比较，故可短路阻尼。直接对端全为非汇流器是结构充分条件；门断边/恢复及纯重排保持它。逐台记录全部自动通道、实际对端和级分组；全局消去须覆盖每个可能读阻尼的单位。条件证明见任务6 PA-01，独立复核pending。')
18: s.replace('4. 实际送出后箱级冷却为5 tick。空箱或全拒收、a_i全0时的冷却触发未由现行文字唯一给出，报告unresolved(transfer.failure_cooldown)，或对具体接法证明所有此类后效均不影响所证结论。此停止是证据范围，不是一次游戏后继。', '4. 每次有资格尝试后箱级冷却为5 tick，包含空箱、全拒收、部分送出和全部送出。`transfer.failure_cooldown=every_attempt`是规则L36及三审§6已定后效。持续供电且开关不变时，节拍由初始冷却余量和5 tick周期确定。')
19: s.replace('当前Rust仍实现旧整箱接收，以下是任务8须落实的规则要求。', '以下为现行规格要求；Rust与此契约的一致性由任务8验收。')
20: s.replace('整箱多物种必须先过§4.3的竞争检测', '箱内多物种部分接收必须先过§4.3的竞争检测')
21: s.replace('其冷却后效见T6', '该次尝试仍开始5 tick冷却（规则L36）')
25: s.replace('## 4. 库存选择器和其它模板', append + '\n## 4. 库存选择器和其它模板')
44: s.replace('§6.1—6.4是2026-09-19旧工程模型的史料证明（其中任务旧L9=现L10、旧L12=现L13、旧L13=现L14、旧L14=现L15；史料的数值引用保留当时行号），依赖的旧传输、门恢复及支持域须按本次回填重核。状态字段表保留作迁移接口；旧证明的通过范围不随源指纹自动转移。§6.5给现行交接义务。', '本节规定现行生产投影、候选状态键和周期证书的支持条件。任务2给仓库接收响应的对应；任务6给带读取前件的状态删减。条件证明的独立复核和实现字段读取审计继续按PC-09及任务8验收。')
52: s.replace('本版给出**可证的子域**D；一般支持域中直接删字段并不良定义。D的前提必须逐项入证书并由验收器核：', 'D是生产投影的保守准入域；每项按实际使用区间核验。其工程无动作执行器与§6.5允许外部成品拿取的真实对应分别记录：')
53: s.replace('无未来离线、建造、调试、非矿外部事件或逐时刻异序', '抽象执行器本身无未来离线、建造、调试、非矿外部事件或逐时刻异序；外部对应另允许任务L8—9的合法成品拿取，固定判定参数持续保持。抽象执行器')
54: s.replace('抽象执行器，外部补矿', '抽象执行器的外部补矿')
55: s.replace('由B<80000，整个tick内各成品每次完整批入库都有容量。比较两键时成品数量不参与，因此代表可有不同数值，不能以这些代表状态声称级二获证。（据：第五轮任务书§2.1抽象的工程分级；规则L13/L36/L41；T12已排除项；级二义务见§6.5）', '由B<80000，代表化执行在整个tick内的候选与实际成品接收均有容量。D.5是代表编码的工程安全条件；证书的现实环境前提只写“仓库收得下成品”。真实仓库和拿取账分别按§6.5复核。（规则L13、L36、L41；任务L2、L9。）')
56: s.replace('若坚持把G的代表化当具体游戏动作，证明立即卡在任务L12，不能使用这种解释。这里证明的是生产投影的转移与率，完整合法环境提升尚未成立。', '代表化只改变数学表示。真实玩家拿取按任务L8—9、L13及§6.5保存，其数量和相对时点另核；矿石可得性与真实矿库存复原分别证明。')
57: s.replace('时间基点t为该state.environment.time；不饱和年龄，不截断累计计数。', '时间基点t为该state.environment.time。下列变化逐项核未来读取及后继保持；未满足某项前件时保留详细值，并报告相应周期覆盖尚未证明。')
58: s.replace('两个物种的under_capacity抽象接收标记', '两个物种的receivable_at_all_checks接收响应标记')
59: s.replace('级一删除的合法性', '生产投影删除的合法性')
60: s.replace('非null变`age=t-entered_at`（包括非运输格）；null仍null。无年龄饱和', '运输格改`residual=max(0,1−(t−entered_at))`，0表示成熟；仅在全部读取只用成熟阈值时成立。非运输格无未来年龄读取时移入审计，有其它读取则保留相对时标')
61: s.replace('非运输记录虽不读仍保守保留', '其它事件引用先转相对时间，完整原时标保存在StateSeed')
62: s.replace('全部保留，按(item,年龄)规范多重集，同种年龄不同不能合并', '全部保留，按(item,规范剩余滞留)保存多重集；年龄删除须先满足下一行的读取前件')
63: s.replace('全保留；按unit排序，原因作集合；即使没设累计上限也不擅自删total_received', '按unit排序、原因作集合；固定C且未来只读n<C时保留min(n,C)，永久无限且无其它读取时n移审计；窗口计数按idle/active保留')
64: s.replace('精确累计可能导致永不重键，是检测不完备而非无循环', '调试改阈值用完整真实n；k=5删状态仍需图/指针维护无关证明')
65: s.replace('null保留，否则变elapsed=t-start，禁止只取模5', 'idle保留；active保存(j,w)，w=start+5−t>0；到期未维护阶段另存，0与5分别编码')
66: s.replace('G中须为空无动作/不适用，保留此标记；不接受未来玩家事件；级二独立量化F，不把无限玩家历史塞进生产状态', 'G执行器中保留空动作标记；外部对应的真实拿取记录与环境证明按§6.5另存，实际外部时序需未来读取时保留相对期限')
67: s.replace('制造完成另由remaining判，预计deadline仅审计，仍保守保留偏移', '制造完成由remaining判，旧deadline在无未来触发/去重读取时移审计；活动期限保持精确相对值')
96: body.replace('具体条文核查及逐步证明见《仓库接收与循环对应》§2—7，引用时锁定该稿指纹。', '具体条文核查见[仓库接收与循环对应](../会议成果/任务书7执行/仓库接收与循环对应.md)§2—7；源稿指纹及本节汇入处置见[汇入记录](../会议成果/任务书7执行/规格回填.md)。新增条件证明待独立复核。')
97: body.replace('传输相位和空箱冷却后效保留在比较中，本证明对每种实际合法取值分别成立。认证一个布局时，生产证据应覆盖声明的全部取值，或附使其不影响结论的充分证明。规则第36行现文未唯一说明空箱无实际发送的尝试是否启动冷却；需要固定该机制的具体运行在明确前保留相应未决，能够覆盖后果的结构证明继续有效。', '传输相位保留在比较中，生产证据覆盖声明的全部相位，或附使其不影响结论的充分证明。规则第36行及三审§6确定每次尝试均开始5 tick冷却，空箱和全部拒收亦同；持续供电且开关不变时，节拍由初始冷却余量及5 tick周期决定（任务6 SP-01）。')
98: body.replace('现有生产键还保守保留非运输格年龄、部分历史累计和审计期限偏移，物理循环可能因此没有重复工程键。采用该键做全称认证时，任务6须补其循环覆盖证明，或直接覆盖漏检循环。上述投影定理保留此表示前件。', '§6.2新键在未来读取前件成立时删除无作用年龄、累计和审计偏移，保持真实耗时与入库。采用详细保守键或未通过某项删状态前件时，仍须证明所有真实周期均被覆盖，或直接处理漏检循环；连续时间有限表示按PC-07另证。')
131: s.replace('任务5须推导该程序可能留下的库存分布、缓存与进度、开关、指针和时间状态，以及末级放开后的全过程；总数是否够填不再作为待定许可。', '任务5§3.1给条件可达谓词和可靠包络；精确集合未枚举。串行释放保留全部相对进度；关闭时intake接口与末级空缓存后态须按任务6 PC-06联合核，释放安全及恢复覆盖继续证明。')
142: s.replace('零传输触发条件见T6', '每次尝试均起冷却，含零传输，见T6')
144: s.replace('离线改变接通先后是否追溯改变已成方向未写明；不可擅自重定向；方向变化不改写按单位分侧的轮询/分级辖域（T14）', '纯重排保持已建方向；实际拆建另按建造历史核，按单位分侧的轮询/分级辖域仍保留（T14）')
145: s.replace('离线只明确接通先后可能改变，同一时刻内判定次序固定，跨时刻辖域见 T2', '纯重排保持库存、进度、冷却、窗口及整场固定判定规则')
146: s.replace('库存/计数/进度保持或重置均不能仅由沉默裁定；完整后效与时间推进见 T10，清零不是已排除也不是已准许', '正时间演化单列；一般指针接续与精确可达排列族见T10及任务6 PC-04')
147: m[0].replace('空箱/全拒收的零传输冷却触发条件未定', '空箱/全拒收也起5 tick冷却')
148: s.replace('受限转移§6.1—6.4保留为历史模型证明材料，须按本次传输与门恢复修改复核；§6.5列任务2待汇入的替换义务。旧级二名目撤下，装载通过仅证明对应输入通过校验，完整循环、参数/初态全称认证继续由任务2、6承担。', '受限转移§6给现行生产键、后继/耗时保持条件及仓库对应。完整循环另核全部有效状态和外部过程复原；全称覆盖另核全部起点、固定参数与合法接续。新增条件证明待独立复核，任务8验收实现。')
149: s.replace('任务5证明该程序的全部可能后置状态与释放过程。', '任务5§3.1给所列专线条件下的可达谓词和可靠包络，exact_reachable_set_enumerated=false。准备截面无在制；串行释放后保留相对进度。关闭时intake与末级空缓存后态的衔接按任务6 PC-06核定。')
150: s.replace('旧本版扫描与重复归约见[受限转移定义](受限转移定义.md)§5史料；条件恢复及部分传输后的完整推进由任务6复核。', '同刻重试、失败控制环及真实唤醒义务见[受限转移定义](受限转移定义.md)§5。')
151: s.replace('本次条件恢复与部分接收修改尚待任务6/8推导、实现和复核；旧唯一后继证明保留为史料。', '条件恢复与部分接收按当前转移契约验收；一般失败环接续及部分扣格后态继续保留具体义务。')
152: s.replace('条件恢复与部分接收按当前转移契约验收；一般失败环接续及部分扣格后态继续保留具体义务。条件恢复与部分接收按当前转移契约验收；一般失败环接续及部分扣格后态继续保留具体义务。', '条件恢复与部分接收按当前转移契约验收；一般失败环接续及部分扣格后态继续保留具体义务。')
168: s.replace('同一时刻内判定次序固定，跨时刻共用排序或逐时刻排序的两种解释见 T2', '判定比较规则整场固定，重复实例的工程嵌入见T2')
169: s.replace('分叉分支和传输相位固定性没有已写依据', '分叉历史全取值覆盖，箱相位服从每次尝试的5 tick冷却')
170: s.replace('空箱/全拒收零传输的冷却触发单列为缺游戏事实（T6）', '空箱/全拒收也开始5 tick冷却已定（规则L36、T6）')
171: s.replace('原受限转移§5、§6.1—6.4保留作旧工程模型史料，须核变更后才可沿用。', '受限转移§5给工程失败环边界，§6给现行条件投影；新增条件证明待独立复核。')
172: s.replace('尚未给出这个归纳证明，故不得用它推出缓存有界。', '任务5指定程序在专线、单配方等条件下给准备截面的空/单完成批包络；串行释放后保留在制及相对进度，关闭时intake接口仍须联合核（PC-06）。其它起法继续承担可达界证明。')
173: s.replace('都是待证明的抽象，须保留所有转移守卫、轮询后效、周期与交付率。', '按任务6 PA-09各自的未来读取前件成立；字段审计和独立复核仍需完成，精确剩余实数的有限表示另列PC-07。')
174: s.replace('生产部分周期的旧D内字段映射、良定义及率保持见受限转移§6.1—6.4史料；部分接收和条件恢复之后的循环对应须由任务2、6复核。', '生产周期的D域、逐字段读取前件、后继/真实耗时及率保持见受限转移§6.1—6.4；仓库前向投影与反向复原见§6.5。')
175: s.replace('分支可否只选一次、无终点运输回路及准入口临时断链的阻尼', '需要多级比较时的全部分支历史、无终点运输回路及准入口临时断链的阻尼')
176: s.replace('对连续时间/相位给保持事件先后的可靠有限分区', '对连续时间/相位给保持实际耗时和交付的可靠有限表示')
201: s.replace(s.splitlines()[2], '日期：2026-09-21。状态：§1—7为原扫描约减及检查记录的史料，按其来源版本读取；现行使用域见§8。')
calls
100: write('受限转移定义.md', s)
139: write('选择点清单.md', s)
164: write('运行语义.md', s)
198: write('四件前置义务对照.md', s)
213: write('参数扫描约减.md', s)
```

## 会议成果/任务书7执行/证据/规格/汇入/merge_certificate.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: S = R / '求解器/规格'
sinks
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1').replace('cycle-normalization-v1', 'cycle-normalization-v2').replace('observable_base_with_withdrawal', 'concrete_base_with_withdrawal').replace('full_base', 'concrete_full_cycle')
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1').replace('cycle-normalization-v1', 'cycle-normalization-v2').replace('observable_base_with_withdrawal', 'concrete_base_with_withdrawal')
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1').replace('cycle-normalization-v1', 'cycle-normalization-v2')
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1').replace('production_v1', 'phase_production_v1')
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3').replace('production-cycle-key-v1', 'phase-cycle-key-v1')
18: x.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3')
18: x.replace('kernel-output-v3', 'kernel-output-v4')
120: p.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
124: s.replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', rh).replace('31ced2a24fef', rh[:12])
124: s.replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', rh)
125: s.replace('状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。', '状态：任务书7任务2、6证书契约已汇入，schema升版；Rust生成与语义验收由任务8实现，新增条件证明待独立复核。')
130: s.replace('kernel-output-v3', 'kernel-output-v4').replace('kernel-cycle-v2', 'kernel-cycle-v3')
130: s.replace('kernel-output-v3', 'kernel-output-v4')
131: s.replace('| schema、run_id | kernel-output-v4、唯一运行标识。 |', '| schema、run_id | kernel-output-v4、唯一运行标识。 |\n| evidence_scope | §5.1公共证据范围；运行记录kind=diagnostic、direction=diagnostic，有限轨迹按实际范围报告。 |')
132: s.replace('当前普通运行未实现，数组必须[]，不能以此写入抽象代表化。', '普通执行器未实现该动作时返回unsupported；抽象执行无拿取事件时数组为[]。具体完整周期按真实拿取填账，数学代表调整单列。')
133: s.replace('空箱/拒收无入库明细。', '空箱/拒收无入库明细，transfer事件仍记录本次尝试和冷却重起5 tick。')
134: s.replace('史料接口：身份维护事件', '身份维护事件')
205: (S / '内核输出.md').write_text(s)
calls
```

## 会议成果/任务书7执行/证据/规格/汇入/merge_specs.py

```text
assignments
6: ROOT = Path('/home/zhuran24/zmd-research-fresh')
7: SPEC = ROOT / '求解器/规格'
8: TASK = ROOT / '求解器/会议成果/任务书7执行'
9: EVIDENCE = TASK / '证据/规格/汇入'
sinks
23: docs[n].replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', rule_hash).replace('31ced2a24fef', rule_hash[:12])
23: docs[n].replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff', rule_hash)
24: docs[n].replace('状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。', '状态：任务书7任务2、6规格汇入完成。已定规则、带前件的证明接口和工程停止分别登记；新增条件证明待独立复核，Rust实现与运行验收由任务8承接。')
108: model.replace('当前报告生产部分周期及其适用域；生产投影到正式基地循环的对应是独立证明义务，任务2有效替换稿待汇入§6.5。旧级二名目撤下。', '生产周期默认报告实际种子、固定参数、接收域和率。正式完整循环的前向投影与反向复原分别按受限转移§6.5验收，全部可达循环覆盖另附证明。任务6条件证明的独立复核状态为pending。')
109: model.replace('§5保留旧算法的条件证明作史料，当前只核所声明支持域和实际执行范围。', '§5列工程函数与真实唤醒的边界；一般失败环接续仍待证明。')
136: inp.replace('默认程序的后置状态集合及释放过程缺任务5证明', '默认程序后态按任务5§3.1的条件可达谓词及可靠包络输入，精确集合未枚举')
137: inp.replace('状态集合与释放后果缺任务5推导', '状态集合的条件包络见任务5，联合释放后果继续核查')
138: inp.replace('不允许在种子参数中切换新排序', '固定判定规则在种子及后续回放中保持')
152: (SPEC / n).write_text(docs[n])
153: config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
154: (EVIDENCE / 'axis-changes.json').write_text(json.dumps({'changed_axes': changed_axes, 'axis_count': len(axes), 'dispositions': counts, 'implementation_status': 'task8_pending'}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/任务书7执行/证据/规格/汇入/polish_merge.py

```text
assignments
3: R = Path('/home/zhuran24/zmd-research-fresh')
3: S = R / '求解器/规格'
sinks
5: s.replace('余货留箱；有货传输后5 tick冷却 | 空箱及全拒收零传输是否启动冷却缺游戏事实；暂停归属、残留格和同刻事件组织待任务6，代码迁移待任务8。', '余货留箱；空箱、全拒收及有货送出每次尝试均起5 tick冷却 | 停用恢复的具体回放、同种跨格部分扣减及同刻事件组织继续核，代码迁移待任务8。')
6: s.replace('任务5/6的推导', '任务5/6的条件证明与联合推导')
7: p.write_text(s)
9: s.replace('正式循环对应证明未完成。认证时须引用真实提升关系和证明而非任意布尔值。', '缺少反向复原或全称覆盖的具体义务时停止。认证时须引用受限转移§6.5对应关系及逐项证明。')
10: s.replace('`warehouse.periodic_lift`的stop登记正式循环对应尚待证明；生产抽象的旧准入与键见受限转移§6.1—6.4史料，须按现行规则复核后执行，不把有限具体库存段冒称无限循环。', '`warehouse.periodic_lift`保留字段名作证明义务入口；stop只在具体反向复原或全称覆盖缺证时触发。生产抽象准入与新键见受限转移§6.1—6.4，完整周期对应见§6.5，依所用支持条件复核后执行。')
11: p.write_text(s)
12: p.read_text().replace('## T18. 设计律的逐单位证据范围', '## 设计律的逐单位证据范围（T4/T6的条件接口）')
12: p.write_text(s)
17: v['meaning'].replace('；无终点返回unresolved，周期提升为待证义务', '；按该字段具体未完成后效报告工程停止')
19: v['extension_gate'].replace('实现有据后效或提供提升证明', '实现该字段的有据后效并补相应证明')
20: p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n')
25: p.write_text(s)
58: p.write_text(json.dumps(sc, ensure_ascii=False, indent=2) + '\n')
60: s.replace('无未来读取的非运输entered_at设null，完整原值仍留端点。', '无未来读取的非运输entered_at设null；仍有相对时标读取时编码为`{relative_time:{value:"entered_at−t"}}`，完整原值仍留端点。')
61: p.write_text(s)
calls
```

## 会议成果/任务书7执行/证据/调试释放/核验.py

```text
assignments
11: E = Path(__file__).resolve().parent
12: O = E.parent.parent
13: ROOT = O.parents[2]
43: source = read(O / '送料与接口.json')
sinks
19: p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
39: dump('输入读取核查.json', {'files': inventory, 'scope': '全部字节读取、JSON解析、脚本语法读取；无来源脚本执行'})
142: dump('局部静止见证.json', {'initial_N': 273, 'final_N': 275, 'rows': rows, 'geometry_reference': '证据/植物运行/局部结构.json', 'raw_transport_cells': 23, 'fixed_service': 'G关闭，PH/HP满专线成熟后同刻传空位', 'scope': '局部库存和缓存事件；不是完整布局或通用执行器；H提前开、P后开不要求精确间隔'})
211: dump('核验结果.json', result)
```

## 会议成果/任务书7执行/证据/调试释放/生成状态.py

```text
assignments
8: E = Path(__file__).resolve().parent
9: O = E.parent.parent
10: ROOT = O.parents[2]
sinks
14: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
212: write(O / '调试后状态.json', data)
213: write(E / '势函数与条件算术.json', {'recipes': RECIPES, 'weights': WEIGHTS, 'recipe_increases': weights, 'candidates': candidate_results, 'scope': '有限停止势函数与条件数字，不是内核或整厂运行证书'})
219: main()
```

## 会议成果/会议3/seat-codex-1/check_cut_side_round8.py

```text
assignments
44: out = {'scope': 'exact algebra on abstract networks; not a factory/performance test', 'identity': 'need-capacity = d(X)+l(out X)-u(in X) = -d(R)+l(in R)-u(out R)', 'cases': cases}
sinks
45: Path(__file__).with_name('cut-side-round8-result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/会议3/seat-codex-1/check_integer_flow_claims.py

```text
assignments
sinks
62: Path(__file__).with_name('integer-flow-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/会议3/seat-codex-1/check_joint_counter_turn6_peer_copy.py

```text
assignments
sinks
50: Path(__file__).with_name('joint_counter_turn5_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
56: main()
```

## 会议成果/会议3/seat-codex-1/check_lower_bound_cuts.py

```text
assignments
sinks
124: Path(__file__).with_name('lower-bound-cut-check.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/会议3/seat-codex-1/check_subset_product.py

```text
assignments
sinks
58: Path(__file__).with_name('subset-product-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/会议3/seat-codex-1/round5-source-snapshots/coarse70.py

```text
assignments
sinks
562: open(a.out, 'w')
calls
514: ap.add_argument('--out', default='')
562: json.dump(dict(info=info, log=log), open(a.out, 'w'), indent=1)
566: main()
```

## 会议成果/会议3/seat-codex-1/verify_cut_certificate.py

```text
assignments
sinks
117: args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
114: ap.add_argument('--output', type=Path, required=True)
```

## 会议成果/会议3/seat-codex-3/check_joint_counter_turn5.py

```text
assignments
sinks
50: Path(__file__).with_name('joint_counter_turn5_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
56: main()
```

## 会议成果/会议3/seat-codex-3/check_network_turn3.py

```text
assignments
sinks
132: Path(__file__).with_name('network_turn3_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
138: main()
```

## 会议成果/会议3/seat-codex-3/check_rate_grid_turn2.py

```text
assignments
58: output = Path(__file__).with_name('rate_grid_turn2_result.json')
sinks
59: output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
64: main()
```

## 会议成果/会议3/seat-codex-3/check_subset_layers_turn4.py

```text
assignments
sinks
94: Path(__file__).with_name('subset_layers_turn4_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
100: main()
```

## 会议成果/会议3/seat-codex-3/check_vote_v1_turn7.py

```text
assignments
sinks
92: Path(__file__).with_name('vote_v1_turn7_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
98: main()
```

## 会议成果/会议3/seat-codex-4/aggflow-audit-70802f19.py

```text
assignments
30: N = args.N
171: P = args.power
244: OUT = sum((mi[e] for e in outa))
sinks
356: open(args.out, 'w')
calls
27: ap.add_argument('--out', default='')
357: json.dump(res, fh, ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-codex-4/review-turn3-7477ab13-p2p.py

```text
assignments
70: OUTP = {(c, d): [] for c in cells for d in range(4)}
72: OUTL = {(c, d, l): [] for c in cells for d in range(4) for l in range(L)}
sinks
394: open(a.out, 'w')
calls
370: ap.add_argument('--out', default='')
394: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-codex-4/review-turn3-p5-a51cec43-p2p.py

```text
assignments
78: OUTP = {(c, d): [] for c in cells for d in range(4)}
80: OUTL = {(c, d, l): [] for c in cells for d in range(4) for l in range(L)}
sinks
402: open(a.out, 'w')
calls
378: ap.add_argument('--out', default='')
402: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-opus-1/coarse70.py

```text
assignments
sinks
562: open(a.out, 'w')
calls
514: ap.add_argument('--out', default='')
562: json.dump(dict(info=info, log=log), open(a.out, 'w'), indent=1)
566: main()
```

## 会议成果/会议3/seat-opus-1/export_cert.py

```text
assignments
sinks
50: open('cert_D1_iter0.json', 'w')
calls
50: json.dump(cert, open('cert_D1_iter0.json', 'w'), ensure_ascii=False, indent=0)
```

## 会议成果/会议3/seat-opus-1/toy.py

```text
assignments
254: SUBS = {'ore': dict(src_items={'ore'}, cin={'crush': 1, 'grind': 0}, cout={'crush': 0, 'grind': 0}, tot=dict(crush_in=2 * D), sink=0), 'sand': dict(src_items={'sand'}, cin={'crush': 1, 'grind': 0}, cout={'crush': 0, 'grind': 0}, tot=dict(crush_in=D / 3), sink=0), 'opow': dict(src_items=set(), cin={'crush': 0, 'grind': 2}, cout={'crush': 1, 'grind': 0}, tot=dict(crush_out=2 * D, grind_in=2 * D), sink=0), 'spow': dict(src_items=set(), cin={'crush': 0, 'grind': 1}, cout={'crush': 3, 'grind': 0}, tot=dict(crush_out=D, grind_in=D), sink=0), 'dense': dict(src_items=set(), cin={'crush': 0, 'grind': 0}, cout={'crush': 0, 'grind': 1}, tot=dict(grind_out=D), sink=D)}
sinks
847: open(a.out, 'w')
calls
753: ap.add_argument('--out', default='')
848: json.dump(dict(info=info, log=log), fh, indent=1)
852: main()
```

## 会议成果/会议3/seat-opus-2/aggflow.py

```text
assignments
35: N = args.N
183: P = args.power
256: OUT = sum((mi[e] for e in outa))
357: KOUT = {'crush': 1, 'refine': 1, 'parts': 1, 'mold': 1, 'plant': 1, 'seed': 2, 'grind': 1, 'pack': 1, 'fill': 1}
371: H = json.load(open(args.hint))
sinks
447: open(args.out, 'w')
calls
32: ap.add_argument('--out', default='')
448: json.dump(res, fh, ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-opus-2/flowcheck.py

```text
assignments
sinks
142: open(out, 'w')
calls
142: json.dump({'deficit': deficit, 'source_side': [repr(x) for x in S]}, open(out, 'w'))
```

## 会议成果/会议3/seat-opus-3/p2p.py

```text
assignments
84: OUTP = {(c, d): [] for c in cells for d in range(4)}
86: OUTL = {(c, d, l): [] for c in cells for d in range(4) for l in range(L)}
sinks
410: open(a.out, 'w')
calls
384: ap.add_argument('--out', default='')
410: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-opus-3/router.py

```text
assignments
sinks
292: open(a.out, 'w')
calls
284: ap.add_argument('--out', default='')
292: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
```

## 会议成果/会议3/seat-opus-4/assemble.py

```text
assignments
sinks
21: part('seat-opus-1/共识段-分解与割.md', '### 1.2 分解与割（主责 seat-opus-1）\n\n（待交）').replace('### 分解与割', '### 1.2 分解与割', 1)
77: four[hit[0]].replace(CUT_OLD, CUT_NEW)
83: open(out, 'w', encoding='utf-8')
calls
83: open(out, 'w', encoding='utf-8').write(body)
```

## 会议成果/会议3/seat-opus-4/freeze-v4-sources/seat-opus-4_assemble.py

```text
assignments
sinks
21: part('seat-opus-1/共识段-分解与割.md', '### 1.2 分解与割（主责 seat-opus-1）\n\n（待交）').replace('### 分解与割', '### 1.2 分解与割', 1)
77: four[hit[0]].replace(CUT_OLD, CUT_NEW)
83: open(out, 'w', encoding='utf-8')
calls
83: open(out, 'w', encoding='utf-8').write(body)
```

## 会议成果/工作/总结-复核-证据/核验.py

```text
assignments
5: root = Path(__file__).resolve().parent
6: out = root.parent
7: evidence = json.loads((root / '输入与结果.json').read_text())
42: target = Path(raw)
43: target = p.parent / target
sinks
59: (root / '核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
60: (root / '核验.log').write_text(json.dumps(result, ensure_ascii=False) + '\n')
calls
```

## 会议成果/工作/总结-复核-证据/生成终稿.py

```text
assignments
5: BASE = Path('/home/zhuran24/zmd-research-fresh')
6: OUT = BASE / '求解器/会议成果/工作'
7: DIALOG = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md')
8: V45 = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-1/共识草案-v45-5c9e556a.md')
9: REVIEW = BASE / '求解器/规格/推导/复核'
sinks
575: (OUT / '总结-终稿.md').write_text('\n'.join(final))
576: (OUT / '总结-否证.md').write_text('\n'.join(audit))
577: (OUT / '总结-复核-证据/回复.json').write_text(json.dumps(reply, ensure_ascii=False, indent=2) + '\n')
578: (OUT / '总结-复核-证据/输入与结果.json').write_text(json.dumps({'inputs': manifest, 'entries': entries, 'disputes': [{'id': d, 'entries': nums, 'decision': s} for d, nums, s in disputes], 'owner_coverage': [{'line': l, 'time': t, 'subject': s, 'entries': ids} for l, t, s, ids in owner_coverage], 'counts': counts}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/工作/生成-总结-读者-codex.py

```text
assignments
4: OUT = Path('/home/zhuran24/zmd-research-fresh/求解器/会议成果/工作')
sinks
96: (OUT / '总结-读者-codex.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
111: (OUT / '总结-读者-codex.md').write_text(''.join(chunks))
calls
```

## 会议成果/工作/终修核验.py

```text
assignments
8: WORK = Path(__file__).resolve().parent
9: ROOT = WORK.parents[2]
10: BASELINE = json.loads((WORK / '终修输入指纹.json').read_text())['inputs']
11: OUTPUT = WORK / '终修核验.json'
12: EDITED = [ROOT / '求解器/会议成果/会议2成果修订-v46.md', ROOT / '求解器/会议成果/任务书7草案.md', ROOT / '求解器/规格/推导/回路总数决定论-v2.md', ROOT / '求解器/规格/推导/三种相位不改产量-v2.md']
18: RECORD = WORK / '终修记录.md'
sinks
146: OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 会议成果/证据-v46/生成修订与核查.py

```text
assignments
6: ROOT = Path('/home/zhuran24/zmd-research-fresh')
7: OUT = ROOT / '求解器/会议成果'
8: EVIDENCE = OUT / '证据-v46'
9: FINAL = OUT / '会议2成果修订-v46.md'
10: BASE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-1/共识草案-v45-5c9e556a.md')
11: SUMMARY = OUT / '工作/总结-终稿.md'
12: DIALOG = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md')
13: LOOP = ROOT / '求解器/规格/推导/回路总数决定论-v2.md'
14: PHASE = ROOT / '求解器/规格/推导/三种相位不改产量-v2.md'
15: REVIEW = ROOT / '求解器/规格/推导/复核/否证-v2-phase.md'
16: MISSING = ROOT / '求解器/规格/推导/复核/否证-v2-loop.md'
17: OVERVIEW = ROOT / '求解器/规格/推导/总纲-流量存量相位.md'
sinks
124: conclusion.replace('令种植、采种、植物粉碎平均批率', '将两种植物合计，令种植、采种、植物粉碎平均批率')
126: conclusion.replace('N+L+1', 'N+ℓ+1')
128: conclusion.replace('种子全空的回路没有第一批', '没有外部植物补给且种子、植株（含在制物料）全空的回路没有第一批')
410: base_text.replace('**', '')
412: q['quote'].replace('**', '')
424: EVIDENCE.mkdir(parents=True, exist_ok=True)
426: draft.write_text(text)
427: draft.replace(FINAL)
445: (EVIDENCE / '输入与结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 候选约束轮次/第57-59轮/G1-复核58/check_review58.py

```text
assignments
19: ROOT = Path(__file__).resolve().parents[4]
20: ROUND = ROOT / '求解器/候选约束轮次/第57-59轮'
sinks
calls
274: subprocess.run([sys.executable, '-B', str(ROUND / 'G1/check_g1.py')], check=True, text=True, capture_output=True, cwd=ROOT)
308: main()
```

## 候选约束轮次/第57-59轮/G1/check_g1.py

```text
assignments
18: ROOT = Path(__file__).resolve().parents[4]
sinks
calls
193: main()
```

## 候选约束轮次/第57-59轮/G2-复核58/check_review.py

```text
assignments
16: ROOT = Path(__file__).resolve().parents[4]
17: SOURCES = ('《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt', '思路.txt', '求解器/候选约束轮次/第57-59轮/G2-推导.md')
sinks
calls
328: main()
```

## 候选约束轮次/第57-59轮/G2/check_local_mechanisms.py

```text
assignments
166: root = Path(__file__).resolve().parents[4]
sinks
calls
178: main()
```

## 候选约束轮次/第57-59轮/G3-复核58/verify.py

```text
assignments
14: HERE = Path(__file__).resolve().parent
15: ROOT = HERE.parents[3]
16: EXPECTED = {'《明日方舟：终末地》游戏规则.txt': '4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd', '求解任务.txt': '1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac', '求解约束.txt': 'f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6', '候选约束.txt': 'a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9', '思路.txt': '95d2af723613bfd61c325ab2fafd89bcd060f099d2a2172a1d79b206c3995cee', '求解器/候选约束轮次/第57-59轮/G3-推导.md': '10e1a1c1e0e2a56153d590912b622f8169ce79e348dda05337a01b164b167e79'}
371: target = HERE / 'verification.json'
sinks
372: target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
calls
377: main()
```

## 候选约束轮次/第57-59轮/G3/build_delivery.py

```text
assignments
6: HERE = Path(__file__).resolve().parent
7: REPORT = HERE.parent / 'G3-推导.md'
sinks
199: (HERE / 'delivery.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
206: REPORT.write_text(''.join(parts))
calls
211: main()
```

## 候选约束轮次/第57-59轮/G3/verify.py

```text
assignments
7: BASE = Path(__file__).resolve().parents[4]
8: HERE = Path(__file__).resolve().parent
sinks
132: (HERE / 'verification.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
calls
138: main()
```

## 候选约束轮次/第57-59轮/G4-复核58/check_g4_review58.py

```text
assignments
16: HERE = Path(__file__).resolve().parent
17: ROOT = HERE.parents[3]
18: EXPECTED_HASHES = {'《明日方舟：终末地》游戏规则.txt': '4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd', '求解任务.txt': '1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac', '求解约束.txt': 'f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6', '候选约束.txt': 'a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9', '思路.txt': '95d2af723613bfd61c325ab2fafd89bcd060f099d2a2172a1d79b206c3995cee', '求解器/候选约束轮次/第57-59轮/G4-推导.md': '26e5c5d3d7a21752ba47ed06a60212f00ecea9674e2006724861ab26902f9390'}
263: out = HERE / '复算结果.json'
sinks
264: out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
273: main()
```

## 候选约束轮次/第57-59轮/G4/check_g4.py

```text
assignments
11: ROOT = Path(__file__).resolve().parents[4]
103: output = Path(__file__).with_name('复算结果.json')
sinks
104: output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
112: main()
```

## 候选约束轮次/第57-59轮/复核59/check_review59.py

```text
assignments
18: HERE = Path(__file__).resolve().parent
19: ROOT = HERE.parents[3]
35: FILES = {'rules': ROOT / '《明日方舟：终末地》游戏规则.txt', 'task': ROOT / '求解任务.txt', 'constraints': ROOT / '求解约束.txt', 'candidates': ROOT / '候选约束.txt', 'idea': ROOT / '思路.txt'}
125: N = L * k // math.gcd(L, k)
sinks
985: (HERE / 'results.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding='utf-8')
calls
990: main()
```

## 内核维护/2026-09-22/bin/python

```text
assignments
11: base = Path(__file__).resolve().parents[1] / 'cargo-test-evidence' / p.stem
14: out = base / f'attempt-{i}'
sinks
14: out.mkdir(parents=True)
16: text.replace(source, repr(str(out)))
18: text.replace(repr(str(out)), 'Path(' + repr(str(out)) + ')')
calls
```

## 内核维护/2026-09-22/check_bridge_python.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
21: (O / 'python-bridge-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22/check_positive.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
5: source = R / '数据/样例/任务7内核/无线多格全收.json'
sinks
8: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
16: (O / (name + '.log')).write_text(r.stdout + r.stderr)
19: (O / 'stale-catalog.log').write_text(r.stdout + r.stderr)
calls
9: save(p, d)
16: subprocess.run(argv, capture_output=True, text=True)
18: save(p, d)
19: subprocess.run(argv, capture_output=True, text=True)
20: save(O / 'positive-validation.json', {'status': 'pass', 'binary_sha256': hashlib.sha256(bin.read_bytes()).hexdigest(), 'commands': rows})
```

## 内核维护/2026-09-22/final_audit.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
41: (O / 'final-audit.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22/health_inventory.py

```text
assignments
8: R = Path.cwd()
8: O = R / '内核维护/2026-09-22'
sinks
9: (O / name).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
24: save('functions.json', {'method': 'Pygments Rust lexer strips comments/strings preserving newlines; count fn keyword to balanced closing brace inclusive; includes blank/comment lines; excludes archived and legacy crates', 'functions': functions, 'over_80': [r for r in functions if r['lines'] > 80]})
34: save('archive-inventory.json', {'roots': summary, 'duplicates': dups, 'manifest_source': 'before.json; byte hashes only, no copies'})
```

## 内核维护/2026-09-22/migrate_active_inputs.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
6: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
38: p.write_text(s)
42: repr(u['transfer']).replace("{'value': '5', 'category': '条文直引'}", 'quantity(cooldown)')
43: p.write_text(s)
calls
33: save(p, d)
34: save(O / 'input-migration.json', reports)
```

## 内核维护/2026-09-22/recover_load_stop.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
5: dest = R / 'crates/kernel/evidence/round5/invalid-cycle-result.json'
8: base = json.loads((R / p).read_text())
27: base = json.loads((R / p).read_text())
sinks
22: dest.write_bytes(b)
22: q.write_text(json.dumps(a, ensure_ascii=False, indent=2) + '\n')
40: dest.write_bytes(b)
40: q.write_text(json.dumps(a, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22/refresh_reference.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
20: p.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
22: (O / 'reference-refresh.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
calls
10: g.run(data)
```

## 内核维护/2026-09-22/relock.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
10: source = R.parent / row['path']
25: source = (p.parent / ref['path']).resolve()
sinks
7: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
13: c.write_text(s)
calls
11: save(p, d)
27: save(p, d)
28: save(O / 'relock.json', {'sources': hashes, 'catalog_sha256': sha(R / '数据/正式静态目录.json'), 'inputs': rows, 'historical_outputs': 'unchanged; not relabeled as current evidence'})
```

## 内核维护/2026-09-22/restore_test_outputs.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
10: (O / ('early-test-' + name)).write_bytes(current)
37: p.write_bytes(found)
39: (O / 'early-test-output-restoration.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22/revert_bridge.py

```text
assignments
5: ROOT = Path.cwd()
5: OUT = ROOT / '内核维护/2026-09-22'
sinks
10: s.replace(a, b)
11: p.write_text(s)
12: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
22: s.replace('R13仍约束同种物品同时只占一轴', 'R13明确豁免桥接器，两轴可同时装同一种物品，各自至多1件/tick')
23: s.replace('R13的同种单格守卫继续适用，同一种物品同时只占一轴', 'R13明确豁免桥接器，同一种物品可同时占两轴，各自至多1件/tick')
24: s.replace('AX-03补明R13的桥同种跨轴守卫，轴身份与联合占格约束分别保留。', 'AX-03旧桥同种跨轴守卫已于2026-09-22退回；轴身份、容量、滞留和按单位调度分别保留。')
26: p.write_text(s)
calls
17: dump(p, d)
78: dump(p, d)
79: dump(OUT / 'bridge-edit-files.json', edits)
```

## 内核维护/2026-09-22/revert_bridge_docs.py

```text
assignments
5: R = Path.cwd()
5: D = R / '会议成果/任务书7执行'
5: O = R / '内核维护/2026-09-22'
sinks
7: p.write_text('# 六个成品来源到无线入库的容量与等待\n\n日期：2026-09-22。状态：旧桥同种互斥读法已退回；以下为现行R13下的局部条件服务。整厂供料与全部可达循环认证开放。L=0，U=1113。\n\n## 1. 原句、服务对象与接收边界\n\n正式来源为项目根目录的《明日方舟：终末地》游戏规则.txt、求解任务.txt、求解约束.txt；本次完整指纹见[维护记录](../../内核维护/2026-09-22/记录.md)。R13明确列「协议储存箱、缓存格和桥接器除外」。R63给桥两轴各自物品格；两轴可以同时存放同一种物品，各自每tick至多1件。每轴仍核容量、至少1tick滞留、端口额度和按单位轮询；轴间不换货。\n\nR17给取货格上限50，R18要求完成批整批转出后才可新开工，R111/114每台5tick产成品1件。两种成品目标合计23/20：任何所有成品必经的唯一1件/tick格会持续多积3/20件/tick，正常有限库存用尽后会阻止下一批开工。这否定该必经单格方案。C68的K+3B+2C≥6只检查合并数量。\n\n现图三源分别进同一箱的三个口，另一种成品使用另一箱；K=0、B=2、C=0。四桥各有两路同种交叉，库存按轴独立。两箱有电、传输开、无取货外送、只收各自成品，仓库持续收得下成品；这是下文服务的接收边界，不是对任意下游阻塞的无条件保证。\n\n## 2. 逐来源几何与条件等待\n\n[布局](密排布局.json)保留全部坐标及68条路径。下表等待界限六源取货格、成品路径和两箱初空、缓存正常单批的工作域；每源新完成批之间至少5tick。计划平均不是已认证产率。\n\n| 来源/计划平均 | 源端口格N | 箱端口格S | 路径格数 | 桥数/元件数 | 完成后到箱/到仓上界 |\n|---|---|---|---:|---|---|\n| M213 电池1/5 | (7,37) | BOX_B(16,44) | 15 | 1/3 | 16/21 tick |\n| M214 电池1/5 | (18,37) | BOX_B(17,
59: tail.replace('for_owner：空。实际上游供料、预装恢复及完整无箱支路', 'for_owner：空。实际上游供料、超出上述恢复域的状态及完整无箱支路')
72: s.replace(a, b)
73: s.replace('## 终修记录（任务书7终修席，2026-09-21）', '## 历史终修记录（2026-09-21旧规则时点，桥相关结论已被现行正文取代）')
75: p.write_text(s)
100: s.replace('### 2.2 桥接器两轴不能同时装同一种物品：已定，且是新发现的硬事实', '### 2.2 旧桥读法（历史裁定，已作废并于2026-09-22退回）')
100: s.replace('终修按旧读法做的改动（18/23、服务字段 null、规格守卫）待下一轮退回，规格两文件末尾已加作废标记。', '终修按旧读法做的改动（18/23、服务字段 null、规格守卫）已退回；现行正文、目录驱动的内核行为及样例已同步，验证见[维护记录](../内核维护/2026-09-22/记录.md)。')
100: p.write_text(s)
calls
```

## 内核维护/2026-09-22/run_checks.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
22: log_path.rename(O / (name + f'.attempt-{i}.log'))
calls
23: subprocess.run(argv, cwd=R, env=env, stdout=log, stderr=subprocess.STDOUT)
25: f.write(json.dumps(row, ensure_ascii=False) + '\n')
```

## 内核维护/2026-09-22/sync_regressions.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
10: p.write_text(s.replace(a, b))
10: s.replace(a, b)
calls
```

## 内核维护/2026-09-22/write_health_plan.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
116: (R / '内核维护/代码体检方案.md').write_text(text)
calls
```

## 内核维护/2026-09-22/write_report.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22'
sinks
98: (O / '记录.md').write_text(text)
112: (O / 'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22b/check_positive.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22b'
5: source = R / '数据/样例/任务7内核/无线多格全收.json'
sinks
8: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
16: (O / (name + '.log')).write_text(r.stdout + r.stderr)
19: (O / 'stale-catalog.log').write_text(r.stdout + r.stderr)
calls
9: save(p, d)
16: subprocess.run(argv, capture_output=True, text=True)
18: save(p, d)
19: subprocess.run(argv, capture_output=True, text=True)
20: save(O / 'positive-validation.json', {'status': 'pass', 'binary_sha256': hashlib.sha256(bin.read_bytes()).hexdigest(), 'commands': rows})
```

## 内核维护/2026-09-22b/relock.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22b'
10: source = R.parent / row['path']
25: source = (p.parent / ref['path']).resolve()
sinks
7: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
13: c.write_text(s)
calls
11: save(p, d)
27: save(p, d)
28: save(O / 'relock.json', {'sources': hashes, 'catalog_sha256': sha(R / '数据/正式静态目录.json'), 'inputs': rows, 'historical_outputs': 'unchanged; not relabeled as current evidence'})
```

## 内核维护/2026-09-22c/check_positive.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22c'
5: source = R / '数据/样例/任务7内核/无线多格全收.json'
sinks
8: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
16: (O / (name + '.log')).write_text(r.stdout + r.stderr)
19: (O / 'stale-catalog.log').write_text(r.stdout + r.stderr)
calls
9: save(p, d)
16: subprocess.run(argv, capture_output=True, text=True)
18: save(p, d)
19: subprocess.run(argv, capture_output=True, text=True)
20: save(O / 'positive-validation.json', {'status': 'pass', 'binary_sha256': hashlib.sha256(bin.read_bytes()).hexdigest(), 'commands': rows})
```

## 内核维护/2026-09-22c/regen_constraints.py

```text
assignments
5: R = Path.cwd()
sinks
10: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
calls
```

## 内核维护/2026-09-22c/relock.py

```text
assignments
5: R = Path.cwd()
5: O = R / '内核维护/2026-09-22c'
10: source = R.parent / row['path']
25: source = (p.parent / ref['path']).resolve()
sinks
7: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
13: c.write_text(s)
calls
11: save(p, d)
27: save(p, d)
28: save(O / 'relock.json', {'sources': hashes, 'catalog_sha256': sha(R / '数据/正式静态目录.json'), 'inputs': rows, 'historical_outputs': 'unchanged; not relabeled as current evidence'})
```

## 几何/1113放松/audit.py

```text
assignments
9: CACHE_FILE = ROOT / 'audit_models.jsonl'
sinks
139: (ROOT / 'audit_checkpoint.json').write_text(json.dumps(audit, ensure_ascii=False))
145: (ROOT / 'audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
calls
81: f.write(json.dumps(dict(key=key, result=result)) + '\n')
147: main()
```

## 几何/1113放松/boundary_joint.py

```text
assignments
83: path = ROOT / 'results' / f"{position['id']}_boundary.json"
sinks
103: path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
calls
92: log.write(msg + '\n')
105: main()
```

## 几何/1113放松/check_solutions.py

```text
assignments
6: ROOT = Path(__file__).resolve().parent
sinks
87: (ROOT / 'solution_checks.json').write_text(json.dumps(dict(status='PASS', checked=len(results), results=results), ensure_ascii=False, indent=2))
calls
89: main()
```

## 几何/1113放松/filter_positions.py

```text
assignments
6: ROOT = Path(__file__).resolve().parent
184: J = budget // 9
sinks
196: (ROOT / 'positions.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
calls
199: main()
```

## 几何/1113放松/make_report.py

```text
assignments
7: ROOT = Path(__file__).resolve().parent
sinks
37: (ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
46: (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
191: report.replace('`build(position).model` 对应返回值', '`build(position)` 的第一个返回值')
192: (ROOT / '报告.md').write_text(report)
calls
194: main()
```

## 几何/1113放松/solve_relaxation.py

```text
assignments
131: path = ROOT / 'logs' / f'{tag}_{stage}.log'
sinks
152: (ROOT / 'results' / f'{tag}_{stage}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
calls
133: log.write(message + '\n')
169: run(position, args.seconds, args.stage, args.workers, args.probing, args.boundary_cuts)
170: main()
```

## 几何/1113放松/verify_infeasible.py

```text
assignments
8: dest = ROOT / 'models'
9: path = dest / (tag + '.pb')
23: dest = ROOT / 'results' / (tag + '_proofcheck.json')
sinks
8: dest.mkdir(exist_ok=True)
30: dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
calls
14: f.write(msg + '\n')
32: main()
```

## 几何/1113放松/异源核查/mip_check.py

```text
assignments
129: R = tuple(args.rect)
130: out = solve(R, args.forbid_edge0, args.time)
sinks
132: (HERE / 'results' / f'{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
calls
```

## 几何/1113放松/异源核查/scan_all.py

```text
assignments
14: ROOT = HERE.parent
sinks
97: (HERE / 'results' / 'scan_all.json').write_text(json.dumps(dict(summary=summary, rows=rows), ensure_ascii=False, indent=1))
calls
89: run(key, [10, 11, 12], seconds, 4, forbid_edge0=True, minimize=None)
102: main()
```

## 几何/1113放松/异源核查/scan_candidates.py

```text
assignments
sinks
18: (HERE / 'results' / f'scan_{mode}.json').write_text(json.dumps(rows, indent=1))
calls
12: run(R, [10, 11, 12], 300, 6, forbid_edge0=mode == 'edge0', minimize='S', tag=tag)
```

## 几何/1113放松/异源核查/strip_model.py

```text
assignments
20: HERE = Path(__file__).resolve().parent
301: out = run(tuple(args.rect), [int(p) for p in args.P.split(',')], args.seconds, args.workers, args.forbid_edge0, args.minimize, args.tag, args.seed)
sinks
286: (HERE / 'results' / f'{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
calls
301: run(tuple(args.rect), [int(p) for p in args.P.split(',')], args.seconds, args.workers, args.forbid_edge0, args.minimize, args.tag, args.seed)
```

## 几何/1113放松/异源核查/their_boundary_nocut.py

```text
assignments
9: HERE = Path(__file__).resolve().parent
sinks
31: (HERE / 'results' / f'their_boundary_nocut_{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
calls
```

## 数据/修订验证/r4/refresh_checks.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: SAMPLES = ROOT / '数据/样例'
sinks
28: (HERE / name).write_bytes(result.stdout)
43: (HERE / '黄金轨迹.log').write_text(output.getvalue())
59: (HERE / '运行输入回归.log').write_text(output.getvalue() + f"本轮写入已重定向至 {HERE / '运行输入回归结果.json'}；未覆盖原脚本显示的路径。\n")
65: (HERE / '验证依赖指纹.json').write_text(json.dumps({'status': '通过', 'unchanged_during_checks': True, 'fingerprints': after, 'scope': '本次实际读取的生产依赖；不把并行线改动记为本席修改'}, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run([sys.executable, '-B', *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
42: golden.main()
56: runtime.main()
61: command('契约自查.log', [ROOT / '数据/工具/check_revision.py', '--output-dir', HERE])
72: main()
```

## 数据/修订验证/r4/reproduce_catalog_gate.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: REPO = ROOT.parent
39: target = solver / '数据/正式静态目录.json'
sinks
30: (solver / '数据/工具').mkdir(parents=True)
32: shutil.copyfile(REPO / name, repo / name)
34: shutil.copyfile(ROOT / name, solver / name)
35: shutil.copytree(ROOT / 'crates', solver / 'crates')
36: shutil.copytree(ROOT / '数据/候选B', solver / '数据/候选B')
38: shutil.copyfile(ROOT / '数据/工具' / name, solver / '数据/工具' / name)
53: target.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
57: (HERE / f'{name}-cargo-gate.log').write_bytes(compiled.stdout)
72: (HERE / '隔离门禁结果.json').write_text(json.dumps({'status': '通过', 'scope': '独立命令及 cargo 实时回源单项；完整正常目录测试另见候选B/cargo-test.log', 'production_catalog_unchanged': True, 'results': results}, ensure_ascii=False, indent=2) + '\n')
calls
54: subprocess.run(['python', '-B', str(ROOT / '数据/工具/formal_catalog.py'), '--catalog', str(target)], capture_output=True, env=env)
56: subprocess.run(cargo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
79: main()
```

## 数据/复核/r4-L1-字段覆盖证据/audit.py

```text
assignments
14: HERE = Path(__file__).resolve().parent
15: REPO = HERE / 'snapshot'
16: DATA = REPO / '求解器/数据'
17: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
sinks
180: (HERE / '独立核对结果.json').write_text(json.dumps(dict(summary=summary, checks=results), ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/r4-L1-字段覆盖证据/mutation_probe.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: SNAPSHOT = HERE / 'snapshot'
13: TEST_REPO = HERE / 'testrepo'
19: TARGET = TEST_REPO / '求解器/数据/正式静态目录.json'
sinks
15: shutil.copytree(SNAPSHOT, TEST_REPO)
18: shutil.copytree(HERE.parents[2] / '.cargo-home', HERE / 'cargo-home')
57: TARGET.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
61: (HERE / (name + '-cargo-test.log')).write_bytes(result.stdout)
66: TARGET.write_bytes(original)
67: (HERE / '回源变异结果.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
58: subprocess.run(['cargo', 'test', '--offline', '--locked', '--manifest-path', str(TEST_REPO / '求解器/Cargo.toml')], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
```

## 数据/复核/r4-L1-字段覆盖证据/snapshot/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/r4-L1-字段覆盖证据/snapshot/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/r4-L1-字段覆盖证据/testrepo/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/r4-L1-字段覆盖证据/testrepo/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/r4-校验器证据/audit.py

```text
assignments
19: OUT = Path(__file__).resolve().parent
20: ROOT = OUT.parents[3]
21: SOLVER = ROOT / '求解器'
22: DATA = SOLVER / '数据'
23: CATALOG = json.loads((DATA / '正式静态目录.json').read_text())
24: CONTRACT = json.loads((DATA / '候选B/contract.json').read_text())
103: source = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
173: target = repo / name
177: target = solver / rel
sinks
28: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
44: (OUT / (name + '.stdout')).write_bytes(result.stdout)
45: (OUT / (name + '.stderr')).write_bytes(result.stderr)
174: target.parent.mkdir(parents=True, exist_ok=True)
178: target.parent.mkdir(parents=True, exist_ok=True)
calls
43: subprocess.run(args, cwd=cwd, env=env, capture_output=True)
133: save('独立核验.json', metrics)
151: save(name + '.json', c)
164: save('目录变异结果.json', variants)
188: save(name, {'mutation': mutation, 'cargo_test_exit_code': result.returncode, 'cargo_test_summaries': re.findall('^test result:.*$', result.stdout.decode(), re.M), 'cli_exit_code': cli.returncode, 'cli_counts': dict(re.findall('^## (能检且通过|能检且不通过|不能静态检)（(\\d+) 项', cli.stdout.decode(), re.M))})
```

## 数据/复核/r4-校验器证据/check_tools.py

```text
assignments
13: OUT = Path(__file__).resolve().parent
14: ROOT = OUT.parents[3]
15: TOOLS = ROOT / '求解器/数据/工具'
26: target = OUT / '转换复现'
sinks
27: target.mkdir(exist_ok=True)
37: (OUT / '转换复现结果.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/r4-校验器证据/隔离副本/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/r5-字段覆盖/audit_fields.py

```text
assignments
16: OUT = Path(__file__).resolve().parent
17: SOLVER = OUT.parents[2]
18: REPO = SOLVER.parent
19: DATA = SOLVER / '数据'
20: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
sinks
32: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
190: relocated.mkdir(exist_ok=True)
199: (OUT / '转换.log').write_text(log.getvalue())
204: (OUT / '校验报告.md').write_bytes(cli.stdout)
calls
203: subprocess.run([str(binary), str(DATA / '候选B/contract.json')], capture_output=True)
208: save('独立字段核对.json', results)
213: main()
```

## 数据/复核/r5-字段覆盖/check_evidence.py

```text
assignments
12: OUT = Path(__file__).resolve().parent
13: SOLVER = OUT.parents[2]
14: DATA = SOLVER / '数据'
15: SAMPLES = DATA / '样例'
sinks
25: (OUT / name).write_bytes(result.stdout)
33: (OUT / '黄金轨迹.log').write_text(log.getvalue())
46: (OUT / '运行输入回归.log').write_text(log.getvalue() + '本次输出已重定向到复核目录。\n')
53: (OUT / '收尾核对.json').write_text(json.dumps({'status': '通过', 'checks': records, 'protected_count': len(snapshot), 'changed': changed}, ensure_ascii=False, indent=2) + '\n')
calls
24: subprocess.run([sys.executable, '-B', *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
32: golden.main()
43: runtime.main()
58: main()
```

## 数据/复核/r5-字段覆盖/isolated/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
748:     let mut child = std::process::Command::new("python")
832:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/r5-字段覆盖/isolated/求解器/数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
113: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 数据/复核/r5-字段覆盖/isolated/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/r5-字段覆盖/isolated/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 数据/复核/否证-r4-1-证据/isolated/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-1-证据/isolated/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-1-证据/isolated/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-1-证据/reproduce.py

```text
assignments
17: HERE = Path(__file__).resolve().parent
18: REPO = HERE.parents[3]
19: WORK = HERE / 'isolated'
20: SNAPSHOT = HERE / 'snapshot'
21: TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
23: FILES = SOURCES + ['求解器/Cargo.toml', '求解器/Cargo.lock', '求解器/crates/topology/Cargo.toml', '求解器/crates/topology/src/lib.rs', '求解器/crates/topology/src/main.rs', '求解器/crates/topology/tests/validation.rs', '求解器/数据/工具/formal_catalog.py', '求解器/数据/工具/convert_candidate_b.py', '求解器/数据/工具/test_formal_catalog.py', '求解器/数据/正式静态目录.json', '求解器/数据/送料契约.md', '求解器/数据/候选B/contract.json', '求解器/数据/候选B/校验报告.md', '求解器/数据/修订记录.md', '求解器/数据/复核/复核-r4-字段覆盖.md', '求解器/数据/复核/复核-r4-校验器正确性.md']
74: target = SNAPSHOT / name
sinks
47: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
53: (HERE / (name + '.stdout')).write_bytes(result.stdout)
54: (HERE / (name + '.stderr')).write_bytes(result.stderr)
75: target.parent.mkdir(parents=True, exist_ok=True)
76: shutil.copyfile(REPO / name, target)
77: shutil.copytree(SNAPSHOT, WORK)
78: shutil.copytree(REPO / '求解器/数据/复核/r4-校验器证据/cargo-home', HERE / 'cargo-home')
79: (HERE / 'tmp').mkdir()
144: catalog_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
145: shutil.copyfile(catalog_path, HERE / (name + '.catalog.json'))
181: catalog_path.write_bytes(original_bytes)
calls
51: subprocess.run(command, cwd=WORK / '求解器', env=ENV, capture_output=True, check=False)
72: write_json(HERE / '输入指纹.json', protected)
147: run(['python', str(tool_dir / 'formal_catalog.py')], name + '-verify')
155: run(['cargo', 'clean', '-p', 'topology', '--offline', '--locked'], name + '-clean')
157: run(['cargo', 'test', '--offline', '--locked'], name + '-cargo-test')
160: run(['cargo', 'run', '--offline', '--locked', '-p', 'topology', '--', str(WORK / '求解器/数据/候选B/contract.json')], name + '-cli')
169: write_json(HERE / '运行结果.json', results)
179: write_json(HERE / '回源对照.json', {'mutation': differences(catalog, control), 'result': control_result})
183: write_json(HERE / '保护核验.json', {'unchanged': protected == after, 'changes': {p: {'before': protected[p], 'after': after[p]} for p in protected if protected[p] != after[p]}})
185: write_json(HERE / '运行元数据.json', {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(), 'recipe_values_match_formal_source': len(expected), 'command_scope': '原转换器仅执行至第41行断言；cargo测试和CLI完整运行', 'rust_version': subprocess.check_output(['rustc', '--version'], env=ENV).decode().strip(), 'cargo_version': subprocess.check_output(['cargo', '--version'], env=ENV).decode().strip()})
```

## 数据/复核/否证-r4-1-证据/snapshot/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-1-证据/snapshot/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-1-证据/snapshot/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/cases/baseline/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/cases/baseline/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/cases/baseline/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/cases/core_port_category/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/cases/core_port_category/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/cases/core_port_category/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/cases/power_coverage/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/cases/power_coverage/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/cases/power_coverage/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/cases/unused_recipe_duration/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/cases/unused_recipe_duration/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/cases/unused_recipe_duration/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/cases/used_recipe_duration/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/cases/used_recipe_duration/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/cases/used_recipe_duration/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/reproduce.py

```text
assignments
16: HERE = Path(__file__).resolve().parent
17: REPO = HERE.parents[3]
18: SNAPSHOT = HERE / 'snapshot'
20: FILES = FORMAL + ['候选约束.txt', '求解器/Cargo.toml', '求解器/Cargo.lock', '求解器/crates/topology/Cargo.toml', '求解器/crates/topology/src/lib.rs', '求解器/crates/topology/src/main.rs', '求解器/crates/topology/tests/validation.rs', '求解器/数据/工具/formal_catalog.py', '求解器/数据/工具/convert_candidate_b.py', '求解器/数据/工具/test_formal_catalog.py', '求解器/数据/正式静态目录.json', '求解器/数据/送料契约.md', '求解器/数据/修订记录.md', '求解器/数据/规则覆盖表.md', '求解器/数据/候选B/contract.json', '求解器/数据/候选B/校验报告.md', '求解器/数据/复核/复核-r4-字段覆盖.md', '求解器/数据/复核/复核-r4-校验器正确性.md']
sinks
38: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
43: (HERE / (prefix + '.stdout')).write_bytes(result.stdout)
44: (HERE / (prefix + '.stderr')).write_bytes(result.stderr)
67: destination.parent.mkdir(parents=True, exist_ok=True)
71: shutil.copytree(REPO / '求解器/.cargo-home', HERE / 'cargo-home')
137: shutil.copytree(SNAPSHOT, case_root)
138: (case_root / catalog_path).write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
calls
42: subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
64: save('原件开工指纹.json', before)
99: save('原配方独立回源.json', {'recipe_count': len(parsed), 'all_equal': True, 'parsed': parsed})
133: save(case + '-catalog.json', changed)
151: run(['cargo', 'test', '--offline', '--locked'], workspace, env, case + '-cargo-test')
156: run(['cargo', 'run', '--offline', '--locked', '--quiet', '-p', 'topology', '--', str(workspace / '数据/候选B/contract.json')], workspace, env, case + '-cli')
165: save('复跑结果.json', results)
169: save('原件收尾核验.json', {'all_unchanged': before == after, 'before': before, 'after': after})
```

## 数据/复核/否证-r4-2-证据/snapshot/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/否证-r4-2-证据/snapshot/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/否证-r4-2-证据/snapshot/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/否证-r4-2-证据/初次共享构建目录结果-不作为证据/reproduce.py

```text
assignments
16: HERE = Path(__file__).resolve().parent
17: REPO = HERE.parents[3]
18: SNAPSHOT = HERE / 'snapshot'
20: FILES = FORMAL + ['候选约束.txt', '求解器/Cargo.toml', '求解器/Cargo.lock', '求解器/crates/topology/Cargo.toml', '求解器/crates/topology/src/lib.rs', '求解器/crates/topology/src/main.rs', '求解器/crates/topology/tests/validation.rs', '求解器/数据/工具/formal_catalog.py', '求解器/数据/工具/convert_candidate_b.py', '求解器/数据/工具/test_formal_catalog.py', '求解器/数据/正式静态目录.json', '求解器/数据/送料契约.md', '求解器/数据/修订记录.md', '求解器/数据/规则覆盖表.md', '求解器/数据/候选B/contract.json', '求解器/数据/候选B/校验报告.md', '求解器/数据/复核/复核-r4-字段覆盖.md', '求解器/数据/复核/复核-r4-校验器正确性.md']
sinks
38: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
43: (HERE / (prefix + '.stdout')).write_bytes(result.stdout)
44: (HERE / (prefix + '.stderr')).write_bytes(result.stderr)
65: destination.parent.mkdir(parents=True, exist_ok=True)
68: shutil.copytree(REPO / '求解器/.cargo-home', HERE / 'cargo-home')
133: shutil.copytree(SNAPSHOT, case_root)
134: (case_root / catalog_path).write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
calls
42: subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
62: save('原件开工指纹.json', before)
96: save('原配方独立回源.json', {'recipe_count': len(parsed), 'all_equal': True, 'parsed': parsed})
130: save(case + '-catalog.json', changed)
143: run(['cargo', 'test', '--offline', '--locked'], workspace, env, case + '-cargo-test')
147: run(['cargo', 'run', '--offline', '--locked', '--quiet', '-p', 'topology', '--', str(workspace / '数据/候选B/contract.json')], workspace, env, case + '-cli')
155: save('复跑结果.json', results)
159: save('原件收尾核验.json', {'all_unchanged': before == after, 'before': before, 'after': after})
```

## 数据/复核/复核-r5-校验器正确性-证据/review_checks.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: REPO = HERE.parents[3]
14: SNAPSHOT = HERE / '被审快照'
15: SOLVER = SNAPSHOT / '求解器'
16: ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(HERE / 'tmp')}
65: path = HERE / (name + '.json')
92: path = HERE / (name + '.json')
105: path = HERE / (name + '.json')
sinks
24: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
29: (HERE / (name + '.stdout.log')).write_bytes(result.stdout)
30: (HERE / (name + '.stderr.log')).write_bytes(result.stderr)
calls
28: subprocess.run(command, capture_output=True, env=ENV)
47: run('目录回源', [sys.executable, '-B', str(gate)])
66: dump(path, changed)
67: run(name, [sys.executable, '-B', str(gate), '--catalog', str(path)])
93: dump(path, changed)
94: run(name, [str(HERE / 'target/debug/topology'), str(path)])
106: dump(path, changed)
107: run(name, [str(HERE / 'target/debug/topology'), str(path)])
132: dump(HERE / '独立复核结果.json', results)
139: main()
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
748:     let mut child = std::process::Command::new("python")
832:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/数据/修订验证/r4/refresh_checks.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: SAMPLES = ROOT / '数据/样例'
sinks
28: (HERE / name).write_bytes(result.stdout)
43: (HERE / '黄金轨迹.log').write_text(output.getvalue())
59: (HERE / '运行输入回归.log').write_text(output.getvalue() + f"本轮写入已重定向至 {HERE / '运行输入回归结果.json'}；未覆盖原脚本显示的路径。\n")
65: (HERE / '验证依赖指纹.json').write_text(json.dumps({'status': '通过', 'unchanged_during_checks': True, 'fingerprints': after, 'scope': '本次实际读取的生产依赖；不把并行线改动记为本席修改'}, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run([sys.executable, '-B', *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
42: golden.main()
56: runtime.main()
61: command('契约自查.log', [ROOT / '数据/工具/check_revision.py', '--output-dir', HERE])
72: main()
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/数据/修订验证/r4/reproduce_catalog_gate.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: REPO = ROOT.parent
39: target = solver / '数据/正式静态目录.json'
sinks
30: (solver / '数据/工具').mkdir(parents=True)
32: shutil.copyfile(REPO / name, repo / name)
34: shutil.copyfile(ROOT / name, solver / name)
35: shutil.copytree(ROOT / 'crates', solver / 'crates')
36: shutil.copytree(ROOT / '数据/候选B', solver / '数据/候选B')
38: shutil.copyfile(ROOT / '数据/工具' / name, solver / '数据/工具' / name)
53: target.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
57: (HERE / f'{name}-cargo-gate.log').write_bytes(compiled.stdout)
72: (HERE / '隔离门禁结果.json').write_text(json.dumps({'status': '通过', 'scope': '独立命令及 cargo 实时回源单项；完整正常目录测试另见候选B/cargo-test.log', 'production_catalog_unchanged': True, 'results': results}, ensure_ascii=False, indent=2) + '\n')
calls
54: subprocess.run(['python', '-B', str(ROOT / '数据/工具/formal_catalog.py'), '--catalog', str(target)], capture_output=True, env=env)
56: subprocess.run(cargo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
79: main()
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
113: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/复核-r5-校验器正确性-证据/被审快照/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 数据/复核/复算-r3/recompute3.py

```text
assignments
17: ROOT = '/home/zhuran24/zmd-research-fresh'
18: SRC = '/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4'
19: OUT = []
sinks
414: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '复算输出-r3.txt'), 'w', encoding='utf-8')
calls
416: f.write('\n'.join(OUT) + '\n')
```

## 数据/复核/复算-r3/派生投影-r3.py

```text
assignments
15: C = '/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/contract.json'
sinks
54: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '派生投影-r3.txt'), 'w', encoding='utf-8')
calls
54: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '派生投影-r3.txt'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
```

## 数据/复核/复算-r4/build_report.py

```text
assignments
7: OUT = Path(__file__).resolve().parent
8: REPORT = OUT.parent / '复核-r4-数值复算.md'
sinks
184: REPORT.write_text(text)
186: (OUT / 'findings.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/复算-r4/compare.py

```text
assignments
11: OUT = Path(__file__).resolve().parent
12: ROOT = OUT.parents[3]
13: SNAP = OUT / '被审快照/求解器'
14: RAW = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
98: path = ROOT / source['path']
sinks
127: lower_parts[0].replace('存货通道至少', '')
128: lower_parts[1].replace('取货通道至少', '')
247: (OUT / '逐项对比.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
calls
```

## 数据/复核/复算-r4/graph_counts.py

```text
assignments
8: OUT = Path(__file__).resolve().parent
9: RAW = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4/channels.csv')
sinks
52: (OUT / '原始流图计数.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/复算-r4/recompute.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[4]
13: OUT = Path(__file__).resolve().parent
14: RAW = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: RULE = ROOT / '《明日方舟：终末地》游戏规则.txt'
16: TASK = ROOT / '求解任务.txt'
17: LIMIT = ROOT / '求解约束.txt'
sinks
24: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=lambda value: str(value)) + '\n')
calls
49: ast.dump(node)
234: save_json('目标反推.json', dict(targets=targets, recipe_support=list(aliases), rates=solved))
260: save_json('独立输入指纹.json', {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})
261: save_json('正式配方独立解析.json', recipes)
262: save_json('独立复算.json', dict(summary=summary, per_machine=per_machine, recipe_batches=recipe_batches))
273: main()
```

## 数据/复核/复算-r4/被审快照/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/复算-r4/被审快照/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
139: write_json(OUT / 'contract.json', contract)
145: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/复算-r4/隔离重跑/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
747:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/复算-r4/隔离重跑/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
19: text.replace('据：蓝图、离线', '据：蓝图')
19: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
27: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
32: p.write_bytes(original + b'\n')
35: p.write_bytes(original)
calls
50: unittest.main()
```

## 数据/复核/复算-r5/audit_evidence.py

```text
assignments
8: OUT = Path(__file__).resolve().parent
9: SNAP = OUT / '输入快照'
10: DATA = SNAP / '求解器/数据'
11: R4 = DATA / '修订验证/r4'
sinks
90: (OUT / '证据链与只读复验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/复算-r5/compare.py

```text
assignments
11: OUT = Path(__file__).resolve().parent
12: SNAP = OUT / '输入快照'
13: DATA = SNAP / '求解器/数据'
sinks
170: bodies['机型下限'].split('，合计')[0].replace('、', ' ')
216: (OUT / '逐项对比.json').write_text(json.dumps(result, default=lambda x: sorted(x) if isinstance(x, set) else str(x), ensure_ascii=False, indent=2) + '\n')
217: (OUT / '报告条目索引.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/复算-r5/prepare.py

```text
assignments
9: ROOT = Path('/home/zhuran24/zmd-research-fresh')
10: OUT = ROOT / '求解器/数据/复核/复算-r5'
11: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
12: TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
33: target = OUT / '输入快照' / rel
sinks
34: target.parent.mkdir(parents=True, exist_ok=True)
36: target.write_bytes(data)
38: (OUT / '输入指纹.json').write_text(json.dumps({'时间': datetime.now(timezone.utc).isoformat(), '文件': records}, ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/复核/复算-r5/recompute.py

```text
assignments
12: OUT = Path(__file__).resolve().parent
13: SNAP = OUT / '输入快照'
14: RAW = SNAP / '原始候选B'
sinks
33: (OUT / name).write_text(json.dumps(value, default=encode, ensure_ascii=False, indent=2) + '\n')
calls
111: save('正式配方独立解析.json', {'全部配方': recipes, '尺寸与端口': sizes, '别名': aliases})
112: save('目标反推.json', {'目标': targets, '说明': '限定原始候选采用的17条配方；未用的蓝铁粉末精炼回块配方仍列入正式解析，但本候选批次率为0。', '秩': rank, '逐配方批次率': rates})
256: save('原始流图计数.json', {'节点': len(nodes), '合并平行边': sum((len(v) for v in graph.values())), 'SCC数': len(components), '非平凡SCC': sorted((c for c in components if len(c) > 1)), '说明': '聚合全部仓库矿口的原始机器图；只是连通性计数，不缩小活性论证范围。'})
259: save('独立复算.json', {'阶段': '尚未读取被审契约和校验报告', '摘要': summary, '机器': machine_rows, '通道': channel_rows, '多料机': multi_rows, '扇出': fanout_rows, '物料': material_rows, '对照项数': len(checks), '错误': errors})
260: save('独立检查明细.json', checks)
```

## 数据/复核/复算-r5/reproduce.py

```text
assignments
11: OUT = Path(__file__).resolve().parent
12: SNAP = OUT / '输入快照'
13: RUN = OUT / '隔离运行'
14: SOLVER = RUN / '求解器'
sinks
21: (OUT / (label + '.stdout.log')).write_bytes(process.stdout)
22: (OUT / (label + '.stderr.log')).write_bytes(process.stderr)
50: (OUT / ('门禁变异-' + label + '.json')).write_bytes(data)
57: (OUT / '重生成校验报告.md').write_bytes(process.stdout)
68: (OUT / '工具复现结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
20: subprocess.run(args, cwd=RUN, env=env, input=stdin, capture_output=True)
```

## 数据/复核/复算-r5/输入快照/原始候选B/design.py

```text
assignments
sinks
198: open(os.path.join(d, 'channels.csv'), 'w', newline='', encoding='utf-8')
209: open(os.path.join(d, 'machines.csv'), 'w', newline='', encoding='utf-8')
220: open(os.path.join(d, 'fanout.json'), 'w', encoding='utf-8')
calls
221: json.dump(fanout, f, ensure_ascii=False, indent=1)
```

## 数据/复核/复算-r5/输入快照/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
748:     let mut child = std::process::Command::new("python")
832:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/复算-r5/输入快照/求解器/数据/修订验证/r4/refresh_checks.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: SAMPLES = ROOT / '数据/样例'
sinks
28: (HERE / name).write_bytes(result.stdout)
43: (HERE / '黄金轨迹.log').write_text(output.getvalue())
59: (HERE / '运行输入回归.log').write_text(output.getvalue() + f"本轮写入已重定向至 {HERE / '运行输入回归结果.json'}；未覆盖原脚本显示的路径。\n")
65: (HERE / '验证依赖指纹.json').write_text(json.dumps({'status': '通过', 'unchanged_during_checks': True, 'fingerprints': after, 'scope': '本次实际读取的生产依赖；不把并行线改动记为本席修改'}, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run([sys.executable, '-B', *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
42: golden.main()
56: runtime.main()
61: command('契约自查.log', [ROOT / '数据/工具/check_revision.py', '--output-dir', HERE])
72: main()
```

## 数据/复核/复算-r5/输入快照/求解器/数据/修订验证/r4/reproduce_catalog_gate.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: REPO = ROOT.parent
39: target = solver / '数据/正式静态目录.json'
sinks
30: (solver / '数据/工具').mkdir(parents=True)
32: shutil.copyfile(REPO / name, repo / name)
34: shutil.copyfile(ROOT / name, solver / name)
35: shutil.copytree(ROOT / 'crates', solver / 'crates')
36: shutil.copytree(ROOT / '数据/候选B', solver / '数据/候选B')
38: shutil.copyfile(ROOT / '数据/工具' / name, solver / '数据/工具' / name)
53: target.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
57: (HERE / f'{name}-cargo-gate.log').write_bytes(compiled.stdout)
72: (HERE / '隔离门禁结果.json').write_text(json.dumps({'status': '通过', 'scope': '独立命令及 cargo 实时回源单项；完整正常目录测试另见候选B/cargo-test.log', 'production_catalog_unchanged': True, 'results': results}, ensure_ascii=False, indent=2) + '\n')
calls
54: subprocess.run(['python', '-B', str(ROOT / '数据/工具/formal_catalog.py'), '--catalog', str(target)], capture_output=True, env=env)
56: subprocess.run(cargo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
79: main()
```

## 数据/复核/复算-r5/输入快照/求解器/数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
113: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 数据/复核/复算-r5/输入快照/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/复算-r5/输入快照/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 数据/复核/复算-r5/隔离运行/原始候选B/design.py

```text
assignments
sinks
198: open(os.path.join(d, 'channels.csv'), 'w', newline='', encoding='utf-8')
209: open(os.path.join(d, 'machines.csv'), 'w', newline='', encoding='utf-8')
220: open(os.path.join(d, 'fanout.json'), 'w', encoding='utf-8')
calls
221: json.dump(fanout, f, ensure_ascii=False, indent=1)
```

## 数据/复核/复算-r5/隔离运行/求解器/crates/topology/tests/validation.rs

```text
assignments
sinks
748:     let mut child = std::process::Command::new("python")
832:     let result = std::process::Command::new("python")
calls
```

## 数据/复核/复算-r5/隔离运行/求解器/数据/修订验证/r4/refresh_checks.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: SAMPLES = ROOT / '数据/样例'
sinks
28: (HERE / name).write_bytes(result.stdout)
43: (HERE / '黄金轨迹.log').write_text(output.getvalue())
59: (HERE / '运行输入回归.log').write_text(output.getvalue() + f"本轮写入已重定向至 {HERE / '运行输入回归结果.json'}；未覆盖原脚本显示的路径。\n")
65: (HERE / '验证依赖指纹.json').write_text(json.dumps({'status': '通过', 'unchanged_during_checks': True, 'fingerprints': after, 'scope': '本次实际读取的生产依赖；不把并行线改动记为本席修改'}, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run([sys.executable, '-B', *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
42: golden.main()
56: runtime.main()
61: command('契约自查.log', [ROOT / '数据/工具/check_revision.py', '--output-dir', HERE])
72: main()
```

## 数据/复核/复算-r5/隔离运行/求解器/数据/修订验证/r4/reproduce_catalog_gate.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
14: REPO = ROOT.parent
39: target = solver / '数据/正式静态目录.json'
sinks
30: (solver / '数据/工具').mkdir(parents=True)
32: shutil.copyfile(REPO / name, repo / name)
34: shutil.copyfile(ROOT / name, solver / name)
35: shutil.copytree(ROOT / 'crates', solver / 'crates')
36: shutil.copytree(ROOT / '数据/候选B', solver / '数据/候选B')
38: shutil.copyfile(ROOT / '数据/工具' / name, solver / '数据/工具' / name)
53: target.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
57: (HERE / f'{name}-cargo-gate.log').write_bytes(compiled.stdout)
72: (HERE / '隔离门禁结果.json').write_text(json.dumps({'status': '通过', 'scope': '独立命令及 cargo 实时回源单项；完整正常目录测试另见候选B/cargo-test.log', 'production_catalog_unchanged': True, 'results': results}, ensure_ascii=False, indent=2) + '\n')
calls
54: subprocess.run(['python', '-B', str(ROOT / '数据/工具/formal_catalog.py'), '--catalog', str(target)], capture_output=True, env=env)
56: subprocess.run(cargo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
79: main()
```

## 数据/复核/复算-r5/隔离运行/求解器/数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
113: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 数据/复核/复算-r5/隔离运行/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/复核/复算-r5/隔离运行/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
113: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
744: target = args.report.resolve()
sinks
747: target.write_text(output)
calls
753: main()
```

## 数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
293: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
290: run(data)
299: main()
```

## 数据/样例/check_port_meeting.py

```text
assignments
41: base = Path(__file__).resolve().parent
44: target = base.parents[1] / '规格/第四轮前置验证/端口相遇比较.json'
sinks
45: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
50: main()
```

## 数据/样例/check_splitter_trace.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
19: target = BASE / '分流器三路轮询-运行记录.json'
sinks
20: target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
24: (BASE / '分流器三路轮询-运行记录-checkpoint_delta.json').write_text(json.dumps(compact, ensure_ascii=False, indent=2) + '\n')
calls
16: run(data)
30: main()
```

## 数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
79: path = BASE / (name + '.json')
sinks
88: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
122: main()
```

## 数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
241: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
250: projection_path(data).write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 数据/样例/runtime_record.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: SPEC = BASE.parents[1] / '规格'
70: evidence = ['没有成功传输：粉碎机布局无箱；分流器布局箱体传输显式关闭，仅检查模板守卫，不验证冷却/相位后效。']
91: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
226: run(data)
257: run(data, captured)
```

## 数据/样例/test_round4.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: OUT = BASE.parents[1] / '规格/第四轮前置验证'
96: output = checker.load_json(BASE / (name + '-运行记录.json'))
105: path = BASE / (name + '-运行记录-checkpoint_delta.json')
sinks
108: path.write_text(json.dumps(compact, ensure_ascii=False, indent=2) + '\n')
142: (OUT / '回归结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
43: run(split)
44: run(copy.deepcopy(split))
70: run(altered)
80: run(altered)
84: run(altered)
88: run(altered)
147: main()
```

## 数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
147: output = checker.load_json(OUTPUT)
269: target = BASE.parents[1] / '规格/内核输入修订验证-r4/运行回归结果.json'
sinks
232: (BASE.parents[1] / '规格/内核输入修订验证-r4/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
233: (BASE.parents[1] / '规格/内核输入修订验证-r4/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
269: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
143: run(data)
196: run(variant)
218: run(data, checkpoints)
273: main()
```

## 规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
103: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/内核输入修订验证-r2/run_checks.py

```text
assignments
9: out = Path(__file__).resolve().parent
11: root = solver.parent
sinks
14: Path(env['TMPDIR']).mkdir(exist_ok=True)
25: name.replace(' ', '-')
46: (out / '自查结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=errors, check=False)
```

## 规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/内核输入修订验证-r4/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
63: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
67: main()
```

## 规格/内核输入修订验证-r4/finalize_delivery.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: SPEC = BASE.parent
11: SOLVER = SPEC.parent
12: ROOT = SOLVER.parent
13: EXAMPLES = SOLVER / '数据/样例'
50: output = checker.load_json(OUTPUT)
sinks
26: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
124: (BASE / '自查报告.md').write_text(report)
calls
79: write_json(BASE / '交付自审.json', audit)
136: write_json(old_path, old)
153: write_json(manifest_path, manifest)
161: main()
```

## 规格/内核输入修订验证-r4/run_checks.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: ROOT = BASE.parents[2]
12: SOLVER = ROOT / '求解器'
13: EXAMPLES = SOLVER / '数据/样例'
14: SHARED = [SOLVER / '规格' / name for name in ('选择点参数轴.md', '选择点清单.md', '规则覆盖表.md', '运行语义.md', '受限模型声明.md', '受限转移定义.md', '内核配置-v1.json')]
sinks
40: log.write_text(process.stdout + process.stderr)
41: (BASE / '候选B校验报告.md').write_text(process.stdout)
65: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
39: subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
70: main()
```

## 规格/内核输入修订验证-r4/test_revision.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: EXAMPLES = BASE.parents[1] / '数据/样例'
142: output = checker.load_json(OUTPUT)
sinks
50: (BASE / '二的幂次到期排序.json').write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + '\n')
152: (BASE / '修订回归结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
109: run(data)
109: run(renamed)
125: run(bad)
157: main()
```

## 规格/复核/r7-独立选择点-证据/生成对照及交付核验.py

```text
assignments
7: ROOT = Path('/home/zhuran24/zmd-research-fresh')
8: SPEC = ROOT / '求解器/规格'
9: BASE = Path(__file__).resolve().parent
sinks
107: (BASE / '逐项对照.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
122: (BASE / '逐项对照.md').write_text('\n'.join(body) + '\n')
148: (BASE / '交付核验.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
calls
153: main()
```

## 规格/复核/r7-独立选择点-证据/被审快照/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/r7-独立选择点-证据/被审快照/求解器/规格/第6轮修订验证/run_checks.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[2]
11: EXAMPLES = ROOT / '求解器/数据/样例'
38: output = BASE / filenames[name]
sinks
39: output.write_text(result.stdout + (result.stderr if name == 'cargo-test' else ''))
52: (BASE / '检查汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
36: subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')})
57: main()
```

## 规格/复核/r7-独立选择点-证据/被审快照/求解器/规格/第6轮修订验证/核对修订回归.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: SPEC = BASE.parent
sinks
calls
193: run()
```

## 规格/复核/r7-独立选择点-证据/被审快照/求解器/规格/第6轮修订验证/核对样例兼容.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: ROOT = BASE.parents[2]
9: EXAMPLES = ROOT / '求解器/数据/样例'
10: SPEC = BASE.parent
41: output = checker.load_json(EXAMPLES / '混做粉碎机两下游-运行记录.json')
sinks
calls
37: golden_checker.run(data)
62: main()
```

## 规格/复核/r7-覆盖证据/核对覆盖.py

```text
assignments
8: ROOT = Path('/home/zhuran24/zmd-research-fresh')
9: BASE = Path(__file__).resolve().parent
10: SPEC = ROOT / '求解器/规格'
11: TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
sinks
50: (BASE / '逐行入口.json').write_text(json.dumps(source_rows, ensure_ascii=False, indent=2) + '\n')
110: (BASE / '原始欠账与完整性批评.json').write_text(json.dumps({'aFindings': findings, 'critic_missing': state['critic']['missing']}, ensure_ascii=False, indent=2) + '\n')
112: (BASE / name).write_bytes((TASK / name).read_bytes())
148: (BASE / '独立核对结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
153: main()
```

## 规格/复核/r7-覆盖证据/被审快照/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/r7-覆盖证据/被审快照/求解器/规格/第6轮修订验证/run_checks.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[2]
11: EXAMPLES = ROOT / '求解器/数据/样例'
38: output = BASE / filenames[name]
sinks
39: output.write_text(result.stdout + (result.stderr if name == 'cargo-test' else ''))
52: (BASE / '检查汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
36: subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')})
57: main()
```

## 规格/复核/r7-覆盖证据/被审快照/求解器/规格/第6轮修订验证/核对修订回归.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: SPEC = BASE.parent
sinks
calls
193: run()
```

## 规格/复核/r7-覆盖证据/被审快照/求解器/规格/第6轮修订验证/核对样例兼容.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: ROOT = BASE.parents[2]
9: EXAMPLES = ROOT / '求解器/数据/样例'
10: SPEC = BASE.parent
41: output = checker.load_json(EXAMPLES / '混做粉碎机两下游-运行记录.json')
sinks
calls
37: golden_checker.run(data)
62: main()
```

## 规格/复核/r8-一致性证据/independent_checks.py

```text
assignments
12: output_dir = Path(__file__).resolve().parent
14: root = spec_dir.parent.parent
66: source = (root / '求解器/crates/kernel/src/transition.rs').read_text()
77: record = json.loads((root / '求解器/数据/样例/混做粉碎机两下游-运行记录-kernel.json').read_text())
sinks
24: (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
63: save('三轴登记.json', {axis: config['axes'][axis] for axis in ['warehouse.external_supply', 'warehouse.periodic_lift', 'damping.branch']})
71: save('闭包字段.json', components)
123: save('分支表局部核对.json', {'非空子集': subsets, '局部总表数': len(policies), '切换集合': path, '选择': [policy[s] for s in path], '说明': '只核输入§5.3与转移§3.4函数定义相同，不是内核端到端测试'})
135: save('停止条件反例.json', {'scope': '有限具体运行的局部传输守卫，不是级一D域/可达循环证书', 'box_items': {item: 1 for item in new_items}, 'U': new_items, 'E': empty_slots, 'O': empty_slots, 'assigned_slots': assigned_slots, '答复第24行停止': old_stop, '现行转移第90行停止': current_stop, '现行规范落格': plan, '容量检查': '各物种入1件，不超过80000；假定有电开关开冷却0且标签无冲突', 'basis': ['规则L13/L36/L41/L73', '任务书4§3.3', '受限转移定义§4.3']})
150: subprocess.run(['node', '-e', node_script, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'], input=json.dumps(payload), text=True, capture_output=True, check=True)
153: save('字段名反例.json', {'scope': '仅schema结构试样，未声称迁移或轨迹合法', '原字段': validation[0], '改名后': validation[1]})
154: save('独立核对结果.json', {'checks': results, 'check_count': len(results), 'status': 'PASS', 'note': '两条冲突反例已成立；其余通过项只作所列有限一致性证据'})
```

## 规格/复核/r8-一致性证据/replay_checks.py

```text
assignments
9: output_dir = Path(__file__).resolve().parent
13: source = (revision_dir / 'check_round5.py').read_text()
22: source = (revision_dir / 'build_schema.py').read_text()
sinks
19: source.replace(old, new)
28: source.replace(old, new)
32: (output_dir / '重跑摘要.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/r8-可导出性复算.py

```text
assignments
16: root = spec.parent.parent
17: evidence = review / 'r8-可导出性证据'
63: source = spec / '第五轮规格修订/check_round5.py'
sinks
18: evidence.mkdir(exist_ok=True)
35: (evidence / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
60: (evidence / '既有自查复跑.log').write_text(log.getvalue())
78: (evidence / '第五轮自查复跑.log').write_text(log.getvalue())
calls
46: save('读取指纹.json', fingerprints)
125: save('独立条件复算.json', cases)
128: save('复核结果.json', {'status': 'PARTIAL' if check_failures else 'PASS', 'original_script_failures': check_failures, 'existing_check_count_before_stop': len(previous['results']), 'round5_check_count': len(namespace['results']), 'schema_byte_reproduction': True, 'reviewed_files_unchanged': True, 'fingerprinted_files': len(fingerprints), 'compilation': '未编译', 'scope': '机械自查复现与独立局部核算；不等于完整语义认证'})
135: save('历史只读指纹差异.json', [{'path': p, 'expected': sha, 'actual': hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p, sha in original.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != sha])
```

## 规格/复核/r8-独立推演证据/independent_checks.py

```text
assignments
9: here = Path(__file__).resolve().parent
11: root = spec.parent.parent
sinks
142: (here / '独立检查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/r8-独立推演证据/recheck.py

```text
assignments
10: here = Path(__file__).resolve().parent
sinks
40: (here / (filename.stem + '.log')).write_text(output.getvalue())
51: (here / '重跑汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
37: output.write(failure)
```

## 规格/复核/r9-一致性证据/check_consistency.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: SPEC = HERE.parents[1]
13: ROOT = SPEC.parents[1]
14: KERNEL = ROOT / '求解器/crates/kernel/src'
15: AJV = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
229: record = {'schema': 'kernel-output-v3', 'run_id': 'review_fixture', 'execution_mode': 'finite_concrete', 'port_meeting': 'shared_edge_opposite', 'profile_id': 'kernel_profile_v1', 'producer': {'kind': 'manual_expected', 'path': str(HERE / 'check_consistency.py'), 'claim': '仅结构试样'}, 'status': 'invalid_input', 'fingerprints': [], 'parameter_assignment': None, 'input_history': None, 'uncovered_axes': [], 'trace': None, 'validation_scope': None, 'open_items': ['结构试样，无实际运行']}
sinks
28: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
71: dump('状态字段与闭包键.json', {'expected_types': {k: v.split() for k, v in state_fields.items()}, 'actual_types': actual_fields, 'field_count': sum((len(v) for v in actual_fields.values())), 'closure_components': actual_components, 'scope': '类型级字段全集核对；Decision.value的嵌套语法另按正文逐项人工核对'})
152: dump('输出字段清单.json', {name: {'expected': fields.split(), 'schema': objects[name]} for name, fields in contracts.items()})
189: dump('分支局部复算.json', {'subsets': subsets, 'table_count': count, 'sequence': sequence, 'answers': answers, 'scope': '输入§5.3与转移§3.4的表查询条件例；非完整布局或Rust执行证据'})
246: subprocess.run(['node', '-e', js, AJV], input=json.dumps({'schema': schema, 'cases': cases}), capture_output=True, text=True, check=True)
250: dump('schema正负例.json', {'count': len(cases), 'cases': results, 'scope': '局部形状核验，不核数量合法性、跨字段守恒或独立运行'})
270: dump('停止前件独立复算.json', {'expressions': expressions, 'cases': truth_rows})
279: dump('r8来源复核.json', {'manifest': manifest_rows, 'observed_sources': source_rows, 'scope': '历史证据与当前字节核对；并行K线变化不是S线写入'})
285: dump('本席读取指纹.json', {str(p): digest(p) for p in source_paths})
287: dump('一致性自查.json', {'status': 'PASS', 'checks': checks, 'count': len(checks), 'schema_cases': len(cases), 'schema_sha256': digest(schema_path), 'findings': [], 'scope': '一致性复核，未运行K线测试，未认证完整目标'})
```

## 规格/复核/r9-可导出性证据/recheck.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: SPEC = HERE.parent.parent
15: ROOT = SPEC.parent.parent
16: SOURCE = SPEC / '第五轮规格修订-r8/check_round8.py'
17: OUTPUT = HERE / '重跑'
73: path = OUTPUT if target.id == 'HERE' else SPEC
124: path = Path(name)
126: path = SPEC / path
sinks
18: OUTPUT.mkdir(exist_ok=True)
27: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
51: source.replace(old, 'output_schema.write_text')
59: (OUTPUT / log_name).write_text(stdout + stderr)
83: (HERE / '原自查重跑.log').write_text(captured.getvalue())
calls
37: dump(HERE / '复核前指纹.json', before)
56: subprocess.run([sys.executable, '-B', str(SPEC / relative), *args], cwd=SPEC.parent, capture_output=True, text=True)
147: dump(HERE / '复算结果.json', result)
```

## 规格/复核/r9-独立推演-证据/check_independent.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: SPEC = HERE.parent.parent
13: ROOT = SPEC.parent.parent
sinks
25: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
171: dump('独立局部复算.json', {'status': 'PASS', 'checks': checks, 'check_count': len(checks), 'capacity_cases': capacity_cases, 'identity_case': identity_case, 'scope': '字段映射试样及局部规则算术；非合法StateSeed、非Rust测试或完整可达反例'})
201: dump('复核验证结果.json', report)
```

## 规格/复核/内核输入/r3-一致性证据/复算与反例.py

```text
assignments
15: HERE = Path(__file__).resolve().parent
16: ROOT = HERE.parents[4]
17: EXAMPLES = ROOT / '求解器/数据/样例'
18: SPEC = ROOT / '求解器/规格'
276: output = load(reference.OUTPUT)
sinks
35: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
291: (HERE / '原检查入口.log').write_text(log.getvalue())
342: (HERE / '错误运行记录仍通过.log').write_text(log.getvalue())
calls
275: save('独立几何.json', geometry_results)
277: save('被核运行记录.json', output)
279: save('独立轨迹核对.json', replay_result)
288: reference.main()
289: regressions.main()
298: save('原程序重跑.json', {'regenerated': regenerated, 'examples': base_checks, 'negative_tests': negatives, 'representation_tests': representations})
309: reference.run(bad)
311: save('反例-未解判定上下文.json', bad)
316: reference.run(bad)
317: save('反例-空仓库源与错误派生状态.json', bad)
330: save('正确空源派生状态被拒绝.json', correction_result)
335: save('反例-错误运行记录.json', bad_output)
341: regressions.main()
344: save('反例检查结果.json', results)
349: main()
```

## 规格/复核/内核输入/r3-覆盖证据/audit.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[4]
14: EXAMPLES = ROOT / '求解器/数据/样例'
15: VALIDATION = ROOT / '求解器/规格/内核输入修订验证-r3'
sinks
29: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
69: (HERE / '隔离重跑.log').write_text(console.getvalue())
calls
39: dump('复核起点指纹.json', before)
45: golden.run(documents[2])
52: dump('重算完整轨迹.json', actual)
65: generator.main()
66: golden.main()
67: runtime_tests.main()
124: dump('核验结果.json', result)
129: main()
```

## 规格/复核/内核输入/r3-覆盖证据/coverage_probes.py

```text
assignments
9: HERE = Path(__file__).resolve().parent
10: ROOT = HERE.parents[4]
11: EXAMPLES = ROOT / '求解器/数据/样例'
77: source = Path(golden.__file__).resolve()
sinks
115: (HERE / '覆盖反例证据.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
95: golden.run(load(golden.INPUT))
120: main()
```

## 规格/复核/内核输入/r4-覆盖证据/audit.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[4]
13: SPEC = ROOT / '求解器/规格'
14: EXAMPLES = ROOT / '求解器/数据/样例'
15: REVISION = SPEC / '内核输入修订验证-r3'
16: TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
50: target = BASE / '被审快照' / relative
67: target = BASE / '重定向输出' / path.relative_to(ROOT / '求解器')
sinks
30: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
51: target.parent.mkdir(parents=True, exist_ok=True)
52: target.write_bytes(raw)
68: target.parent.mkdir(parents=True, exist_ok=True)
90: (BASE / '隔离复验.log').write_text(output.getvalue())
calls
45: write_json(BASE / '复核起点指纹.json', before)
78: tests.main()
82: golden.run(data)
121: main()
```

## 规格/复核/内核输入/r4-覆盖证据/coverage_probes.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[4]
11: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
19: (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
109: write_json('双空箱几何.json', data)
140: write_json('覆盖反例证据.json', {'scope': '几何和有限函数选点是实测；全时域不可表示由复核报告的代数证明给出。', 'independent_geometry': geometries, 'belt_ordered_pairs': len(belt_pairs), 'witness_structure': structural, 'witness_formula': 'n为正的2的幂时B先A后，其余A先B后；共同到期t=5n。', 'witness_prefix': [{'n': n, 'time': 5 * n, 'order': [t['target'] for t in witness_order(n)]} for n in range(33)], 'finite_table_first_unlisted_time': 325, 'finite_table_diagnostic': exhaustion, 'periodic_probe_examples': periodic_checks})
150: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/r4-覆盖证据/被审快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/内核输入/否证-r3-1-证据/核验.py

```text
assignments
12: BASE = Path(__file__).resolve().parent
13: ROOT = BASE.parents[4]
14: SAMPLES = ROOT / '求解器/数据/样例'
15: TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
sinks
25: (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
38: save('核验前指纹.json', before)
77: save('重新生成的运行记录.json', generated)
85: save(name + '.json', value)
119: trace.run(value)
148: save('输入反例-' + name + '.json', value)
157: save('输入反例-空源错误派生状态.json', empty_source)
170: save('空源修正-' + name + '.json', value)
177: save('只读重建的参数投影.json', fresh_profile)
219: trace.run(data)
222: save('闭包中途物理投影.json', captured)
227: save('核验后指纹.json', after)
228: save('核验结果.json', results)
```

## 规格/复核/内核输入/否证-r3-2-证据/recheck.py

```text
assignments
12: BASE = Path(__file__).resolve().parent
13: ROOT = BASE.parents[4]
14: SAMPLES = ROOT / '求解器/数据/样例'
15: SPEC = ROOT / '求解器/规格'
sinks
29: (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
49: call()
62: reference.run(data)
76: write_json('读取指纹.json', before)
80: reference.run(data)
87: write_json('只读重生运行记录.json', coherent)
114: write_json('输出反例-' + name + '.json', record)
143: write_json('输入反例-' + name + '.json', variant)
153: write_json('输入反例-empty_source.json', empty)
164: write_json('正确状态-empty_source.json', fixed_levels)
165: reference.run(empty)
178: reference.run(data)
182: write_json('闭包中途物理投影.json', middle)
206: write_json('只读重生参数投影.json', current_assignment)
212: write_json('核验结果.json', results)
218: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/recheck.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: ROOT = BASE.parents[4]
12: SAMPLES = ROOT / '求解器/数据/样例'
13: SPEC = ROOT / '求解器/规格'
51: dest = BASE / '读取快照' / path.relative_to(ROOT)
57: output = checker.load_json(trace.OUTPUT)
90: source = Path(row['path'])
91: dest = isolated / source.relative_to(ROOT)
sinks
28: path.parent.mkdir(parents=True, exist_ok=True)
29: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
52: dest.parent.mkdir(parents=True, exist_ok=True)
53: dest.write_bytes(path.read_bytes())
92: dest.parent.mkdir(parents=True, exist_ok=True)
93: dest.write_bytes(source.read_bytes())
116: (BASE / '事件冲突隔离.log').write_text(proc.stdout + proc.stderr)
calls
49: save(BASE / '读取指纹.json', before)
56: trace.run(data)
68: save(BASE / '仓库重名输入.json', mutated)
70: trace.run(mutated)
71: save(BASE / '仓库重名重算.json', wrong_ticks)
95: save(isolated / trace.INPUT.relative_to(ROOT), event_input)
115: subprocess.run([sys.executable, '-B', '-c', child], cwd=isolated, text=True, capture_output=True)
158: save(BASE / '复验结果.json', results)
165: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/事件冲突隔离/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/事件冲突隔离/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/事件冲突隔离/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-1-证据/事件冲突隔离/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/否证-r4-1-证据/事件冲突隔离/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/否证-r4-1-证据/读取快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/independent_probes.py

```text
assignments
11: ROOT = Path('/home/zhuran24/zmd-research-fresh')
12: OUT = Path(__file__).resolve().parent
55: output = checker.load_json(golden.OUTPUT)
92: target = OUT / '被核快照' / path.relative_to(ROOT)
136: target = isolated / path.relative_to(ROOT)
sinks
21: path.parent.mkdir(parents=True, exist_ok=True)
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
93: target.parent.mkdir(parents=True, exist_ok=True)
94: target.write_bytes(path.read_bytes())
137: target.parent.mkdir(parents=True, exist_ok=True)
138: target.write_bytes(path.read_bytes())
145: (OUT / '事件碰撞隔离运行.log').write_text(run.stdout + run.stderr)
calls
54: golden.main()
66: save(root / '隔离验收结果.json', {'validate_record': accepted, 'schema_check': True, 'collisions': collisions, 'dependencies': dependencies, 'output_sha256': digest(golden.OUTPUT)})
90: save(OUT / '起点指纹.json', before)
96: golden.run(data)
107: save(OUT / '仓库标签碰撞输入.json', altered)
111: golden.run(altered)
129: save(OUT / '仓库碰撞完整轨迹.json', ticks)
142: save(isolated / '求解器/数据/样例/混做粉碎机两下游.json', altered)
143: subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--isolated', str(isolated)], cwd=isolated, capture_output=True, text=True)
190: save(OUT / '终点指纹.json', after)
191: save(OUT / '独立核验结果.json', result)
201: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/事件碰撞隔离副本/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/事件碰撞隔离副本/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/事件碰撞隔离副本/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-2-证据/事件碰撞隔离副本/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/否证-r4-2-证据/事件碰撞隔离副本/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/否证-r4-2-证据/被核快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/复核检查.py

```text
assignments
12: BASE = Path(__file__).resolve().parent
13: SNAPSHOT = BASE / '被审快照'
14: EXAMPLES = SNAPSHOT / '求解器/数据/样例'
23: path = BASE / name
128: path = save('反例/' + label + '.json', output)
135: target = BASE / ('日志/' + label + '-回归报告.json')
187: source = (EXAMPLES / assignment['profile_source']['path']).resolve()
sinks
24: path.parent.mkdir(parents=True, exist_ok=True)
25: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
137: target.parent.mkdir(parents=True, exist_ok=True)
148: (BASE / '日志').mkdir(exist_ok=True)
149: (BASE / ('日志/' + label + '.log')).write_text(stdout.getvalue() + json.dumps(result, ensure_ascii=False) + '\n')
calls
128: save('反例/' + label + '.json', output)
143: regression.main()
162: golden.run(data)
169: golden.main()
195: save('复核结果.json', result)
200: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/工具/check_revision.py

```text
assignments
11: root = Path(__file__).resolve().parents[2]
17: output_dir = args.output_dir.resolve()
sinks
19: output_dir.mkdir(parents=True, exist_ok=True)
21: (output_dir / '自查结果.json').write_text(json.dumps({'status': '进行中'}, ensure_ascii=False) + '\n')
105: (output_dir / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
15: parser.add_argument('--output-dir', type=Path, default=data / '修订验证/r4')
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/工具/convert_candidate_b.py

```text
assignments
12: ROOT = Path(__file__).resolve().parents[2]
13: REPO = ROOT.parent
14: SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
15: OUT = ROOT / '数据/候选B'
sinks
22: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
124: write_json(OUT / 'contract.json', contract)
130: write_json(OUT / '来源清单.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/工具/test_formal_catalog.py

```text
assignments
sinks
36: text.replace('据：蓝图、离线', '据：蓝图')
36: text.replace('目标须对其每种取值都达成', '目标只须对一种取值达成')
41: directory.mkdir(exist_ok=True)
45: (repo / source['path']).write_bytes((ROOT.parent / source['path']).read_bytes())
50: p.write_bytes(original + b'\n')
53: p.write_bytes(original)
calls
119: unittest.main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
181: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
169: run(data)
185: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
sinks
137: PROFILE_PATH.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
12: BASE = Path(__file__).resolve().parent
135: output = checker.load_json(OUTPUT)
154: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
154: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
131: run(data)
158: main()
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r2/run_checks.py

```text
assignments
9: out = Path(__file__).resolve().parent
11: root = solver.parent
sinks
14: Path(env['TMPDIR']).mkdir(exist_ok=True)
25: name.replace(' ', '-')
46: (out / '自查结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
26: subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=errors, check=False)
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r3-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
26: log.write_text(p.stdout + p.stderr)
39: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
25: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, text=True, capture_output=True)
43: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/identifier_probes.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: ROOT = BASE.parents[4]
sinks
39: (BASE / '标识符变异汇总.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
26: trace.run(modified)
35: trace.run(modified)
44: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/independent_audit.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[4]
11: SNAP = BASE / '被审快照'
12: EXAMPLES = SNAP / '求解器/数据/样例'
276: path = (EXAMPLES / entry['path']).resolve()
sinks
26: (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
264: write('独立几何.json', shapes)
280: write('逐轴对照.json', axis_result)
291: write('目录配方回源.json', {'recipe_count': 18, 'all_equal': True, 'formal_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SNAP.glob('*.txt')}})
293: write('独立轨迹.json', result)
297: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/reproduce_event_collision.py

```text
assignments
sinks
calls
10: g.main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/rerun_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[4]
13: EXAMPLES = ROOT / '求解器/数据/样例'
14: SPEC = ROOT / '求解器/规格'
26: path = Path(path).resolve()
28: dest = BASE / '原程序输出' / path.relative_to(ROOT / '求解器')
47: output = checker.load_json(golden.OUTPUT)
sinks
29: dest.parent.mkdir(parents=True, exist_ok=True)
calls
65: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/标识冲突隔离副本/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/复核-r4-一致性-证据/被审快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/独立核算.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: ROOT = BASE / '被审快照'
10: SAMPLES = ROOT / '求解器/数据/样例'
sinks
245: (BASE / '独立核算结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
250: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/被审快照/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/check_examples.py

```text
assignments
13: BASE = Path(__file__).resolve().parent
14: ROOT = BASE.parents[2]
19: AXIS_PATH = ROOT / '求解器/规格/选择点参数轴.md'
731: target = args.report.resolve()
sinks
734: target.write_text(output)
calls
740: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/check_golden_trace.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: INPUT = BASE / '混做粉碎机两下游.json'
12: GOLDEN = BASE / '混做粉碎机两下游-黄金轨迹.json'
13: OUTPUT = BASE / '混做粉碎机两下游-运行记录.json'
sinks
200: OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
calls
197: run(data)
206: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/generate_examples.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
77: path = BASE / (name + '.json')
sinks
83: path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
113: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/runtime_example.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
197: source = lambda path: {'path': str(Path('../../规格') / path.name), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
sinks
206: PROFILE_PATH.write_text(json.dumps(profile_projection(data), ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/runtime_record.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parents[1] / '规格'
75: evidence = ['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
sinks
calls
153: run(data)
174: run(data, captured)
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/数据/样例/test_runtime_input.py

```text
assignments
14: BASE = Path(__file__).resolve().parent
137: output = checker.load_json(OUTPUT)
259: target = BASE.parents[1] / '规格/内核输入修订验证-r3/运行回归结果.json'
sinks
222: (BASE.parents[1] / '规格/内核输入修订验证-r3/中途种子.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
223: (BASE.parents[1] / '规格/内核输入修订验证-r3/周期排序.json').write_text(json.dumps(periodic, ensure_ascii=False, indent=2) + '\n')
259: target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
133: run(data)
186: run(variant)
208: run(data, checkpoints)
263: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/规格/check_revision.py

```text
assignments
8: root = spec_dir.parent.parent
26: source = (root / filename).read_text().splitlines()
sinks
98: coverage.replace(feed_row, re.sub('§6', '§4.3', feed_row))
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/规格/内核输入修订验证-r3/build_output_schema.py

```text
assignments
4: out = Path(__file__).resolve().parents[1] / '内核输出.schema.json'
sinks
32: out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/规格/内核输入修订验证-r3/check_current_coverage.py

```text
assignments
6: BASE = Path(__file__).resolve().parent
7: SOLVER = BASE.parents[1]
8: ROOT = SOLVER.parent
17: source = (ROOT / name).read_text().splitlines()
23: source = [(i, line.split('：', 1)[0]) for i, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and (not line.startswith(' ')) and (not line.endswith('：'))]
50: output = (SOLVER / '规格/内核输出.md').read_text()
sinks
59: (BASE / '规则覆盖自查.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
63: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/规格/内核输入修订验证-r3/finalize_delivery.py

```text
assignments
8: BASE = Path(__file__).resolve().parent
9: SPEC = BASE.parent
10: SOLVER = SPEC.parent
11: EXAMPLES = SOLVER / '数据/样例'
26: output = checker.load_json(OUTPUT)
sinks
62: audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
72: manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
calls
76: main()
```

## 规格/复核/内核输入/复核-r4-可导出性-证据/隔离运行/求解器/规格/内核输入修订验证-r3/run_checks.py

```text
assignments
11: BASE = Path(__file__).resolve().parent
12: ROOT = BASE.parents[2]
13: EXAMPLES = ROOT / '求解器/数据/样例'
sinks
31: log.write_text(p.stdout + p.stderr)
32: (BASE / '候选B校验报告.md').write_text(p.stdout)
53: (BASE / '自查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
30: subprocess.run(cmd, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_HOME': str(ROOT / '求解器/.cargo-home'), 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')}, text=True, capture_output=True)
57: main()
```

## 规格/复核/否证-r8-1-证据/independent_checks.py

```text
assignments
14: EVIDENCE = Path(__file__).resolve().parent
15: WORKSPACE = EVIDENCE.parents[2]
16: REPOSITORY = WORKSPACE.parent
17: TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
18: AJV = Path('/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js')
23: path = EVIDENCE / name
sinks
25: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
154: subprocess.run(['node', '-e', code, str(AJV)], input=json.dumps(payload), text=True, capture_output=True, check=True)
157: save('schema-试样.json', {'scope': '仅结构试样，不满足运行记录全部语义验收义务', 'original': record, 'renamed': renamed, 'extra_alias': extra})
159: save('schema-结果.json', {'ajv': str(AJV), 'result': result, 'stderr': completed.stderr})
174: save('读取指纹.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': before})
182: save('原文摘录.json', extracts)
190: save('停止条件-独立事务.json', transaction)
192: save('停止条件-谓词对照.json', matrix)
201: save('读取后核对.json', {'unchanged': unchanged, 'file_count': len(paths), 'files': after})
207: save('复算摘要.json', summary)
212: main()
```

## 规格/复核/否证-r8-2-证据/independent_verify.py

```text
assignments
9: output_dir = Path(__file__).resolve().parent
11: root = spec_dir.parent.parent
70: record = {'schema': 'kernel-output-v3', 'run_id': 'r8-seat2-schema-fixture', 'profile_id': 'kernel_profile_v1', 'execution_mode': 'finite_concrete', 'port_meeting': 'shared_edge_opposite', 'producer': {'kind': 'manual_expected', 'path': str(Path(__file__).resolve()), 'claim': '仅字段形状试样，不是游戏执行记录'}, 'status': 'invalid_input', 'fingerprints': [], 'parameter_assignment': None, 'input_history': None, 'uncovered_axes': [], 'trace': None, 'validation_scope': None, 'open_items': ['手工字段试样：没有装载输入或执行游戏转移']}
sinks
15: (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
53: save('停止条件独立复算.json', {'scope': '普通有限执行的局部仓库事务；不是完整布局、可达性或生产周期D域证书', 'preconditions': ['箱体有电、传输开关开、冷却为0', '每个新物种各1件，分别占箱体一格', '两成品均无现存或历史目标', '空格身份已解null、空格序完整', '规范新标签无冲突', '区间无改指派、拿取或离线，保留历史身份'], 'answer_source': answer, 'transition_source': transfer, 'cases': rows, 'result': 'PASS：复现了未指派空格时两条件不同'})
84: save('字段名最小试样.json', {'original': record, 'renamed': renamed, 'both': both})
102: subprocess.run(['node', '-e', node_source, ajv_path], input=json.dumps(payload), capture_output=True, text=True, check=True)
110: save('字段名独立校验.json', {'scope': '仅验证当前schema的结构；不表示轨迹合法、来源核验或目标认证', 'schema_path': str(schema_path), 'schema_sha256': hashlib.sha256(schema_path.read_bytes()).hexdigest(), 'validator': ajv_path, 'validator_stderr': process.stderr, 'original': results[0], 'renamed': results[1], 'both': results[2], 'result': 'PASS：正确字段通过，改名同时触发缺字段和未知字段，保留两名也失败'})
```

## 规格/复核/完整性批评-3-角接对枚举.py

```text
assignments
9: ROOT = pathlib.Path(__file__).resolve().parents[2]
10: CATALOG = ROOT / '数据' / '正式静态目录.json'
sinks
calls
96: main()
```

## 规格/复核/约减/check_independent_r1.py

```text
assignments
10: HERE = Path(__file__).resolve().parent
11: ROOT = HERE.parents[2]
174: path = HERE / '独立重推-r1-核验结果.json'
sinks
175: path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
108: run(['manufacture', 'transfer'])
108: run(['transfer', 'manufacture'])
181: main()
```

## 规格/复核/约减/check_independent_r2.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: ROOT = HERE.parents[2]
280: path = HERE / '独立重推-r2-核验结果.json'
sinks
281: path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
287: main()
```

## 规格/复核/约减/count_classes.py

```text
assignments
11: ROOT = Path(__file__).resolve().parents[3]
12: HERE = Path(__file__).resolve().parent
382: output = HERE / '等价类计数.json'
sinks
367: name.replace('|', '\\|')
374: (HERE / '事件对清单.md').write_text('\n'.join(lines) + '\n')
388: output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
399: main()
```

## 规格/复核/约减/recheck_r2_coverage.py

```text
assignments
14: HERE = Path(__file__).resolve().parent
sinks
20: (HERE / '复核-r2-覆盖-原脚本check.log').write_text(process.stdout + process.stderr + f'\n退出码：{process.returncode}\n')
84: (HERE / '复核-r2-覆盖-原函数重验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
18: subprocess.run([sys.executable, '-B', str(HERE / 'count_classes.py'), '--check'], capture_output=True, text=True, check=False)
91: main()
```

## 规格/复核/约减/review_r1_coverage.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
sinks
283: (HERE / '复核-r1-覆盖-独立复算.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
calls
292: main()
```

## 规格/复核/约减/review_r2_coverage.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: ROOT = HERE.parents[2]
sinks
356: (HERE / '复核-r2-覆盖-独立复算.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
360: main()
```

## 规格/复核/约减/verify_branch_projection.py

```text
assignments
sinks
118: (HERE / '分支表约减验证.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/复核/约减/verify_reduction.py

```text
assignments
sinks
136: (HERE / '验证结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
95: run(copy.deepcopy(data))
144: main()
```

## 规格/复核/约减/否证-r1-1-证据/check_branch_projection.py

```text
assignments
11: HERE = Path(__file__).resolve().parent
12: SOLVER = HERE.parents[3]
13: REPO = SOLVER.parent
14: REVIEW = HERE.parent
16: TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
sinks
191: (HERE / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
calls
199: main()
```

## 规格/复核/约减/否证-r1-2-证据/check_branch_projection.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: WORK = HERE.parents[3]
15: REPO = WORK.parent
16: SAMPLES = WORK / '数据/样例'
19: CONFIG = WORK / '规格/内核配置-v1.json'
20: BINARY = WORK / 'target/debug/kernel'
141: path = HERE / 'current-input.json'
142: output = HERE / 'current-record.json'
sinks
29: (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
143: save(path.name, data)
146: subprocess.run(command, text=True, capture_output=True, timeout=60, pass_fds=(EXECUTABLE.fileno(),))
159: save(name + '-representative-input.json', data)
160: save(name + '-representative-record.json', record)
207: save('results.json', result)
217: save('results.json', result)
223: main()
```

## 规格/复核/约减/复核-r1-正确性-核验.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: ROOT = HERE.parents[2]
146: output = HERE / '复核-r1-正确性-核验.json'
sinks
147: output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
153: main()
```

## 规格/复核/约减/复核-r2-正确性-核验.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[2]
19: TARGETS = [ROOT / '规格/参数扫描约减.md'] + [HERE / name for name in ('count_classes.py', 'verify_reduction.py', 'verify_branch_projection.py', '等价类计数.json', '事件对清单.md', '验证结果.json', '分支表约减验证.json', '修订记录.md', '修订-r1-自查.log')]
133: path = HERE / '否证-r1-1-证据/check_branch_projection.py'
sinks
120: (template['operation'] + '(' + template['target'] + ')').replace('|', '\\|')
196: (HERE / '复核-r2-正确性-check.log').write_text('命令：' + ' '.join(command) + '\n退出码：' + str(process.returncode) + '\n' + process.stdout + process.stderr)
212: (HERE / '复核-r2-正确性-核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
195: subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
219: main()
```

## 规格/推导/复核/否证-1-证据/检查局部证据.py

```text
assignments
sinks
calls
52: f.write(msg)
```

## 规格/推导/复核/否证-相位-1-证据/check_traces.py

```text
assignments
9: HERE = Path(__file__).resolve().parent
10: ROOT = HERE.parents[4]
sinks
calls
15: json.dump(value, out, ensure_ascii=False, indent=2)
16: out.write('\n')
25: save('inputs.json', {'scope': '局部时序算术复算，不是完整布局、可达性证书或 kernel 核对', 'sources': [{'path': s, 'sha256': hashlib.sha256((ROOT / s).read_bytes()).hexdigest()} for s in source_names], 'continuous_filler': {'duration': 5, 'use_each': 10, 'initial_before_start_each': 12, 'arrivals_odd_each': 3, 'arrivals_even_each': 1, 'last_tick': 10}, 'three_fillers': {'duration': 5, 'use_each': 10, 'initial_after_start_each': [0, 0, 0], 'arrivals_AB_each': 2, 'arrivals_C_odd_each': 2, 'arrivals_C_even_each': 1, 'last_tick': 40}, 'gate_sliding_window': {'limit': 2, 'offered_ticks': [0, 4, 5, 6]}, 'gate_intermittent': {'limit': 2, 'offered_ticks': list(range(0, 21, 5))}, 'two_gates': {'limits': [1, 1], 'window_origins': [0, 0], 'at_tick_0': {'front_belt': 'P1', 'gate_A': 'P0', 'gate_B': 'Q0'}, 'P1_ready_to_leave_front': 1}, 'parts_backlog': {'manufacture_duration': 1, 'output_capacity': 50, 'gate_limit': 1, 'ini
59: save('continuous_filler.json', continuous)
93: save('three_fillers.json', three)
120: save('gate_sliding_window.json', sliding)
123: save('gate_intermittent.json', intermittent)
156: save('serial_gates.json', serial)
185: save('parts_backlog.json', backlog)
201: save('checks.json', checks)
203: log.write(json.dumps(checks, ensure_ascii=False, indent=2) + '\nall assertions passed\n')
```

## 规格/推导/复核/否证-相位-2-证据/逐tick核算.py

```text
assignments
10: HERE = Path(__file__).resolve().parent
11: ROOT = HERE.parents[4]
12: INPUTS = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '求解器/规格/推导/三种相位不改产量.md']
sinks
calls
216: json.dump(result, f, ensure_ascii=False, indent=2)
217: f.write('\n')
219: f.write('局部算术断言全部通过。三灌装机完成4+4+3批；第三台开工前库存不恒定。\n')
220: f.write('滑动5tick窗口有3件通过k=2门；串联示例I1从tick1等到tick10送达。\n')
221: f.write('满速粉碎机接k=1门时tick63首次完成品留在缓存格。\n')
222: f.write(f'饱和双门局部核算{serial_checks}例未发现稳态计数偏离min(k1,k2)/5。\n')
223: f.write('未运行kernel，未证明全厂两种相位的可达循环态产率不同。\n')
228: main()
```

## 规格/推导/证据-v2-loop-否证/check.py

```text
assignments
8: OUT = Path(__file__).resolve().parent
9: ROOT = OUT.parents[3]
10: DER = OUT.parent
35: source = (prior / '检查局部证据.py').read_text().split('msg=')[0]
sinks
16: (OUT / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
23: save('inputs', [dict(path=str(p), sha256=sha256(p.read_bytes()).hexdigest(), lines=len(p.read_text().splitlines())) for p in files])
86: save('fifo-stated-model', {'scope': 'Independent supplied-word model, NOT kernel execution or complete layout', 'blocked': bad, 'released': good, 'full_inputs': full})
107: save('checks', checks)
```

## 规格/推导/证据-v2-loop-否证/final_check.py

```text
assignments
6: OUT = Path(__file__).resolve().parent
7: FILE = OUT.parent / '复核/否证-v2-loop.md'
sinks
43: (OUT / 'review-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
68: (OUT / 'final-check.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
69: (OUT / '读者自审.md').write_text('# 读者视角自审\n\n日期：2026-09-20。状态：通过。\n\n' + '\n'.join(('- ' + s for s in audit['reader_review'])) + '\n\n详细检查结果见 final-check.json；结构化返回值见 review-result.json。\n')
calls
```

## 规格/推导/证据-v2-loop-否证/probe.py

```text
assignments
9: OUT = Path(__file__).resolve().parent
10: ROOT = OUT.parents[3]
11: SOLVER = ROOT / '求解器'
18: BIN = SOLVER / 'target/release/kernel'
19: CFG = SOLVER / '规格/内核配置-v1.json'
23: path = OUT / (name + '.json')
38: dest = OUT / (name + '.json')
sinks
24: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
42: subprocess.run(cmd, capture_output=True, text=True, timeout=55)
46: save('commands', COMMANDS)
50: save(name + '-seed', data)
51: invoke('seed', seed, name + '-canonical')
54: invoke('run', canonical, name + '-run', ticks)
55: invoke('verify-record', record, name + '-verified')
73: save('protected-before', hashes)
75: bf.generate('mixed-layout', [unit('grinder', '研磨机', 10, 10), unit('front', '传送带', 12, 9), unit('middle', '传送带', 12, 8), unit('back', '传送带', 12, 7), unit('power', '供电桩', 17, 11)])
89: run(name, data, 12)
91: bf.generate('gate-layout', [unit('harvest', '采种机', 10, 10), unit('gate', '物品准入口', 12, 15), unit('planter', '种植机', 10, 16), unit('crusher', '粉碎机', 18, 13), unit('power', '供电桩', 16, 17)])
103: run('gate-first-release', gate, 8)
104: save('probe-results', results)
108: save('protected-after-probes', after)
112: main()
```

## 规格/推导/证据-v2-loop/核对-本版.py

```text
assignments
9: OUT = Path(__file__).resolve().parent
10: ROOT = OUT.parents[3]
11: DOC = OUT.parent / '回路总数决定论-v2.md'
16: path = Path(source['path'])
157: path = Path(target)
159: path = DOC.parent / path
sinks
182: (OUT / '核对结果-本版.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
185: (OUT / '核对-本版.log').write_text('PASS: 16 recorded inputs unchanged; review evidence matches; manual trace counts, corrected inventory algebra, first-clearance arithmetic, mineral budget, premise quotes, links and document structure checked.\nSCOPE: no kernel simulation; no complete-layout certificate; no proof of universal startup safety or phase independence.\n')
calls
```

## 规格/推导/证据-v2-phase-否证/check_phase_v2.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[3]
14: SOLVER = ROOT / '求解器'
15: BIN = SOLVER / 'target/release/kernel'
16: CFG = SOLVER / '规格/内核配置-v1.json'
102: path = HERE / (name + '.json')
sinks
19: (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
calls
27: write('input_hashes.json', before)
86: subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
91: builder.generate(name, units)
102: write(path.name, data)
104: call(['seed', path, '--out', canonical])
104: write(name + '-seed.json', seeded)
106: call(['check', canonical])
106: write(name + '-check.json', checked)
108: call(['run', canonical, '--ticks', '81', '--out', HERE / (name + '-trace.json')])
108: write(name + '-run.json', ran)
164: write('probe_results.json', {'recipes': recipe_checks, 'target_mass': 52, 'third_filler': third, 'continuous_filler': continuous, 'recycle_trace': recycle_trace, 'geometry_verified': True, 'gate_k5_opportunity_histories': 1 << 15, 'non_sliding_receipts': non_sliding, 'deadlock': deadlock, 'alive_after_sand': alive_after_sand, 'kernel': kernel, 'kernel_steps_executed': 0 if all((v['status'] == 'seed_failed' for v in kernel.values())) else 'inspect_traces', 'inputs_unchanged': before == after, 'complete_layout_certified': False})
```

## 规格/推导/证据-v2-phase-否证/write_review.py

```text
assignments
5: HERE = Path(__file__).resolve().parent
6: OUT = HERE.parent / '复核/否证-v2-phase.md'
sinks
73: (HERE / 'review_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
121: OUT.write_text(text)
calls
```

## 规格/推导/证据-v2-phase/final_check.py

```text
assignments
7: HERE = Path(__file__).resolve().parent
8: DOC = HERE.parent / '三种相位不改产量-v2.md'
21: path = Path(href)
22: path = path if path.is_absolute() else source.parent / path
sinks
49: (HERE / 'final-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/推导/证据-v2-phase/v2_rewrite_check.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: ROOT = HERE.parents[3]
14: REV = ROOT / '求解器/规格/推导/复核'
15: CHAT = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-主线.md')
sinks
132: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
133: (HERE / 'v2_rewrite_check.log').write_text('PASS: specified source hashes match; all source bytes unchanged.\nPASS: all review JSON loaded; generated tick records compared field by field.\nPASS: 625 bounded serial-gate probes reproduced; not a general phase proof.\nPASS: 18 recipes conserve ore content; 0.6*50+0.55*40=52.\nPASS: k=5 cannot reject an otherwise feasible receipt due to its periodic quota.\nNo kernel build, simulator access, full-layout or reachability certification.\n')
calls
```

## 规格/推导/证据-v2-phase/verify.py

```text
assignments
13: HERE = Path(__file__).resolve().parent
14: ROOT = HERE.parents[3]
15: DER = ROOT / '求解器/规格/推导'
16: DIALOGUE = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-精简.md')
66: dest = HERE / f'replay-{label}'
sinks
30: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
68: dest.mkdir()
72: code.replace('HERE = Path(__file__).resolve().parent', f'HERE = Path({str(dest)!r})')
73: code.replace('ROOT = HERE.parents[4]', f'ROOT = Path({str(ROOT)!r})')
77: (dest / 'execution.log').write_text(capture.getvalue())
134: (HERE / 'verify.log').write_text('PASS: 两席原脚本复算结果逐字节相同；18条配方矿含量守恒；目标恰用52；额外蓝铁块/粉末循环净收支为零；所有输入哈希未变。\n未运行kernel，未认证整厂，未进行第二版独立复核。\n')
calls
53: write_json('sources.json', {'files': before, 'snapshot_copied': False, 'dialogue_initial_full_read': dialogue_record, 'opus_phase_separate_evidence_directory': None})
126: write_json('checks.json', {'replays': replays, 'recipe_conservation_checked': len(recipes), 'max_item_total_ore_weight': 50, 'target_ore_per_tick': '52', 'battery_capsule_per_20_ticks': [12, 11], 'blue_block_powder_extra_cycle_net_balance': cycle_balance, 'input_hashes_unchanged': True, 'kernel_run': False, 'whole_layout_certified': False, 'v2_independent_review_completed': False})
```

## 规格/第6轮修订验证/run_checks.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[2]
11: EXAMPLES = ROOT / '求解器/数据/样例'
38: output = BASE / filenames[name]
sinks
39: output.write_text(result.stdout + (result.stderr if name == 'cargo-test' else ''))
52: (BASE / '检查汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
36: subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_TARGET_DIR': str(ROOT / '求解器/target')})
57: main()
```

## 规格/第6轮修订验证/核对修订回归.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: SPEC = BASE.parent
sinks
calls
196: run()
```

## 规格/第6轮修订验证/核对样例兼容.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: ROOT = BASE.parents[2]
9: EXAMPLES = ROOT / '求解器/数据/样例'
10: SPEC = BASE.parent
41: output = checker.load_json(EXAMPLES / '混做粉碎机两下游-运行记录.json')
sinks
calls
37: golden_checker.run(data)
62: main()
```

## 规格/第7轮修订验证/finalize_delivery.py

```text
assignments
10: BASE = Path(__file__).resolve().parent
11: SPEC = BASE.parent
12: ROOT = SPEC.parents[1]
13: SAMPLES = ROOT / '求解器/数据/样例'
14: OWN_SPEC = ['运行语义.md', '选择点清单.md', '选择点参数轴.md', '受限模型声明.md', '规则覆盖表.md', '四件前置义务对照.md', '修订记录.md', 'check_revision.py', '内核配置-v1.json', '受限转移定义.md', '参数轴-对内核输入请求的答复.md', '内核输入.md', '第三轮任务验证/发现处置.json', '第6轮修订验证/核对修订回归.py']
sinks
28: (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
35: (BASE / output).write_text(result.stdout)
calls
32: subprocess.run([sys.executable, '-B', str(script)], cwd=ROOT, capture_output=True, text=True)
61: save('接口快照.json', {'status': 'PASS', 'axis_count': 99, 'request_sections_read': [1, 2, 3, 4, 5, 6, 7], 'shared_interface': interface, 'sources': before, 'scope': '当前共享实际字节只读重验；其它席修改不据此归成本席成果'})
76: save('全文辖域扫描.json', {'status': 'PASS', 'forbidden_active_assertions': forbidden, 'forbidden_hits': bad, 'reviewed_hits': hits, 'scope': '现行正文及历史索引全辖域定位；不以字符串扫描证明语义穷尽，旧复核/被审快照保留史料原文'})
79: save('交付自审.json', {'status': 'PASS', 'finding_count': 2, 'unhandled_findings': [], 'schema_and_full_record_verified': True, 'shared_sources_stable_during_validation': True, 'protected_files': len(protected), 'protected_unchanged': True, 'simulator_file_set_unchanged': True, 'specification_checks': len(spec_result['checks']), 'local_regression_checks': len(regression['checks']), 'reader_review': ['正文终态与历史分区', '相遇待审和已定类型守卫分开', '当前空格序成功/失败完整后效', '非空/空格身份编码可逆', '99轴及F/O/U一致', '链接与符号落点', '有限实验不升级全称认证'], 'open_items': ['角点相遇等其它谓词的全规则审查', '竞争匿名空格的批量分配', '一般语义相容性、全部初态/离线、有限抽象与完整周期提升'], 'scope': '测试与读者自审已完成；随后由本脚本写清单/指纹并逐项重读，失败则整个封存退出非零'})
94: save(manifest_path.name, {'schema': 'revision-delivery-v1', 'revision': 'round3-r7', 'sealed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': [str(path) for path in ordered], 'fingerprints': str(fingerprints_path), 'fingerprint_exclusions': [str(fingerprints_path)], 'scope': '本席实际修改/新增及本轮快照、日志；源码含必要共享改动，不冒领C线同期其它实现；构建产物不列交付'})
100: save(fingerprints_path.name, hashes)
113: main()
```

## 规格/第7轮修订验证/run_checks.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: ROOT = BASE.parents[2]
11: EXAMPLES = ROOT / '求解器/数据/样例'
39: output = BASE / filenames[name]
sinks
40: output.write_text(result.stdout + (result.stderr if name == 'cargo-test' else ''))
53: (BASE / '检查汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
calls
37: subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'CARGO_TARGET_DIR': str(ROOT / '求解器/target-spec-r7')})
58: main()
```

## 规格/第7轮修订验证/核对修订回归.py

```text
assignments
9: BASE = Path(__file__).resolve().parent
10: SPEC = BASE.parent
11: EXAMPLES = SPEC.parent / '数据/样例'
sinks
calls
260: main()
```

## 规格/第7轮修订验证/核对样例兼容.py

```text
assignments
7: BASE = Path(__file__).resolve().parent
8: ROOT = BASE.parents[2]
9: EXAMPLES = ROOT / '求解器/数据/样例'
10: SPEC = BASE.parent
42: output = checker.load_json(EXAMPLES / '混做粉碎机两下游-运行记录.json')
sinks
calls
38: golden_checker.run(data)
65: main()
```

## 规格/第五轮规格修订-r8/check_round8.py

```text
assignments
12: HERE = Path(__file__).resolve().parent
13: SPEC = HERE.parent
14: WORKSPACE = SPEC.parent
15: AJV = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
120: record = {'schema': 'kernel-output-v3', 'run_id': 'schema_only_round8', 'profile_id': 'kernel_profile_v1', 'producer': {'kind': 'manual_expected', 'path': str(Path(__file__).resolve()), 'claim': '仅字段结构试样，非运行记录'}, 'status': 'invalid_input', 'fingerprints': [], 'parameter_assignment': None, 'input_history': None, 'uncovered_axes': [], 'trace': None, 'validation_scope': None, 'open_items': ['结构试样：无可执行输入'], 'execution_mode': 'finite_concrete', 'port_meeting': 'shared_edge_opposite'}
sinks
20: (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
32: (HERE / log_name).write_text(proc.stdout + proc.stderr)
calls
30: subprocess.run([sys.executable, '-B', str(SPEC / relative), *args], cwd=WORKSPACE, capture_output=True, text=True)
63: run_script('第五轮规格修订/build_schema.py', 'schema生成.log')
65: run_script('check_revision.py', '规格自查.log')
71: run_script('第五轮规格修订/check_round5.py', '第五轮自查.log', '--output-dir', str(HERE))
108: dump('停止条件复算.json', {'scope': '局部守卫及条件落格，非完整可达布局或Rust运行', 'source_expression': source_expression, 'reply_expression': reply_expression, 'truth_table': truth_table, 'counterexample': {'U': products, 'E': empty_slots, 'O': empty_slots, 'assigned_slots': sorted(assigned_slots), 'stop': False, 'allocation': allocation, 'O_after': [], 'quantities_after': {item: 1 for item in products}, 'conditions': ['有电且传输开、冷却0', '身份和O完整', '新标签无冲突', '无改指派/拿取/离线且retain_history']}})
135: subprocess.run(['node', '-e', script, AJV], capture_output=True, text=True, check=True, input=json.dumps({'schema': schema, 'records': [record, renamed]}))
148: dump('字段名复算.json', {'scope': '仅schema结构，非执行认证', 'original': valid, 'renamed': invalid})
160: dump('回矿容量复算.json', {'scope': '核心PC和整箱各回1件矿的局部容量算术；非Rust测试', 'cases': ore_cases})
185: dump('辖域扫描.json', {'files': scan, 'forbidden_current_phrases': forbidden, 'historical_scope': '复核目录与以旧轮次命名的证据保存旧句，不作为现行契约；本轮脚本中的旧句仅为负例', 'questions_read': questions})
193: dump('本轮自查结果.json', {'status': 'PASS', 'checks': checks, 'check_count': len(checks), 'round5_check_count': round5['check_count'], 'axis_count': 99, 'scope': '规格、配置、schema、接口前件和局部容量；不含K线运行回归或全称认证', 'sources': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}})
```

## 规格/第五轮规格修订/build_schema.py

```text
assignments
4: here = Path(__file__).resolve().parent
5: base = json.loads((here / '运行记录v2基线.schema.json').read_text())
sinks
58: (spec / '内核输出.schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
calls
```

## 规格/第五轮规格修订/check_round5.py

```text
assignments
8: AJV_PATH = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
25: here = Path(__file__).resolve().parent
25: root = spec.parent.parent
28: output_dir = args.output_dir.resolve()
sinks
30: output_dir.mkdir(parents=True, exist_ok=True)
35: (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
calls
14: subprocess.run(['node', '-e', script, AJV_PATH], input=json.dumps(payload), text=True, capture_output=True, check=True)
27: parser.add_argument('--output-dir', type=Path, default=here)
92: dump('StateSeed字段清点.json', fields)
101: dump('提升容量卡点.json', case)
123: dump('轮询均分局部推演.json', polling)
158: dump('活动内核来源.json', {'current': shared, 'changed_since_round5_start': [p for p, h in shared.items() if h != fingerprints[p]], 'scope': 'K线活动源码只读观测；不以旧轮次字节限制本轮实现'})
162: dump('自查结果.json', report)
```
