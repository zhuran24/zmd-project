"""Requested catalog verification, semantic discriminator, and finite CLI chain."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
from run_guarded import run, OUT, ROOT, save

def existing_or_run(name, argv):
    result = OUT / (name + '.result.json')
    if result.exists():
        row = json.loads(result.read_text())
        assert row['argv'] == argv and not any(row['history_diff'].values())
        return row['exit_code']
    return run(name, argv)

assert existing_or_run('formal-catalog-verify', ['python3', '-B', '数据/工具/formal_catalog.py']) == 0

old_catalog_bytes = subprocess.check_output(['git', 'show', 'HEAD:求解器/数据/正式静态目录.json'], cwd=ROOT)
old_catalog = json.loads(old_catalog_bytes)
old_lib = subprocess.check_output(['git', 'show', 'HEAD:求解器/crates/topology/src/lib.rs'], cwd=ROOT).decode()
begin = old_lib.index('"矿系不入库/计划"')
end = old_lib.index('let core_in', begin)
(OUT / 'old-core-predicate.rs.txt').write_text(old_lib[begin:end])

contract = json.loads((ROOT / '数据/候选B/contract.json').read_text())
extra = deepcopy(next(m for m in contract['machines'] if m['kind'] == '种植机'))
extra['id'] = 'VERIFY_EXTRA_GROWER'
contract['machines'].append(extra)
core_id = contract['core']['id']
feed = next(e for e in contract['logical_feeds'] if e['target'] == core_id)
old_item = feed['item']
feed['item'] = '荞花'
save('semantics-33-growers-buckflower.json', contract)
growers = sum(m['kind'] == '种植机' for m in contract['machines'])
plants = ['荞花', '砂叶', '荞花种子', '砂叶种子', '荞花粉末', '砂叶粉末', '细磨荞花粉末']
threshold = old_catalog['static_checks']['constants']['plant_trigger']['quantity']['value']
assert threshold == '32' and growers == 33
# Direct transcription of the archived predicate, not a claim to run an old binary.
old_predicate = all(e['item'] in old_catalog['task']['targets'] or (growers != int(threshold) and e['item'] in plants)
                    for e in contract['logical_feeds'] if e['target'] == core_id)
assert old_predicate
code = existing_or_run('semantics-new-topology', [str(ROOT / 'target/release/topology'), str(OUT / 'semantics-33-growers-buckflower.json')])
report = (OUT / 'semantics-new-topology.stdout.log').read_text()
failure_section = next(s for s in report.split('## ') if s.startswith('能检且不通过'))
unknown_section = next(s for s in report.split('## ') if s.startswith('不能静态检'))
row = next(s for s in failure_section.splitlines() if '| 矿系不入库/计划 |' in s)
assert code == 1, row
unknown_rows = [next(s for s in unknown_section.splitlines() if '正式条目/' + name + ' |' in s)
                for name in ['矿系不入库', '非成品零入库', '传输按仓库余量判定']]
save('semantic-discriminator.json', {'growers': growers, 'feed_id': feed['id'], 'original_item': old_item,
     'replacement_item': '荞花', 'feed': feed, 'old_predicate_passes': old_predicate,
     'old_predicate_evidence': 'old-core-predicate.rs.txt; expression evaluated with HEAD catalog',
     'new_binary_exit_code': code, 'new_target_check': row, 'formal_unknown_rows': unknown_rows,
     'scope': 'Checks this named guard only; the modified full contract has other failures.'})

source = ROOT / '数据/样例/任务7内核/无线多格全收.json'
document = json.loads(source.read_text())
for ref in [document['catalog'], document['parameters']['axis_registry']]:
    ref['path'] = str((source.parent / ref['path']).resolve())
save('positive-input.json', document)
binary = str(ROOT / 'target/release/kernel')
config = str(ROOT / '规格/内核配置-v1.json')
rows = []
for name, args, status in [
    ('positive-seed', ['seed', str(OUT / 'positive-input.json'), '--out', str(OUT / 'positive-seed.json')], None),
    ('positive-check', ['check', str(OUT / 'positive-seed.json')], 'input_checked'),
    ('positive-run', ['run', str(OUT / 'positive-seed.json'), '--ticks', '6', '--out', str(OUT / 'positive-record.json')], 'completed'),
    ('positive-verify-record', ['verify-record', str(OUT / 'positive-record.json')], 'input_checked'),
]:
    code = run(name, [binary, *args, '--config', config])
    response = json.loads((OUT / (name + '.stdout.log')).read_text())
    rows.append({'name': name, 'exit_code': code, 'status': response.get('status')})
    assert code == 0 and response.get('status') == status, rows[-1]
assert json.loads((OUT / 'positive-seed.json').read_text())['schema'] == 'kernel-input-v3'
assert json.loads((OUT / 'positive-record.json').read_text())['status'] == 'completed'
stale = deepcopy(document)
old_sha = hashlib.sha256(old_catalog_bytes).hexdigest()
stale['catalog']['sha256'] = old_sha
save('old-sha-input.json', stale)
code = run('old-sha-rejection', [binary, 'seed', str(OUT / 'old-sha-input.json'), '--config', config])
response = json.loads((OUT / 'old-sha-rejection.stdout.log').read_text())
reason = [s for s in response.get('open_items', []) if str(ROOT / '数据/正式静态目录.json') in s and '源文件指纹不符' in s]
assert code == 2 and response.get('status') == 'invalid_input' and reason, (code, response)
rows.append({'name': 'old-sha-rejection', 'exit_code': code, 'status': response['status'], 'reason': reason})
save('positive-chain-summary.json', {'commands': rows, 'old_catalog_sha256': old_sha,
     'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
     'scope': '6 tick finite execution and record verification; no whole-factory or universal cycle certification'})
print(json.dumps(rows, ensure_ascii=False, indent=2))
