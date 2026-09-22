# 静态写点与路径表达式台账

源码只读扫描；未执行列出的程序。`sinks` 包括创建目录、覆盖、删除和移动；`calls` 为间接写出链定位，不能仅凭命名认定实际写入。历史快照不是当前测试入口。

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
