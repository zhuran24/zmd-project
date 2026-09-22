"""相对记录的批量入口、绝对路径对照与检查点压缩格式恢复。"""
import copy
import hashlib
import json
import os
import sys
sys.dont_write_bytecode = True
from probe import HERE, ROOT, CASES, call, read, save, schema


def main():
    absolute = HERE/'referenced-7.record.json'
    assert call('absolute-record-verify', 'verify-record', absolute)[0] == 0
    assert call('absolute-record-checkpoint', 'checkpoint', absolute, '--out', HERE/'absolute-record-checkpoint.json')[0] == 0
    package = HERE/'relative-package'
    package.mkdir(exist_ok=True)
    record = read(absolute)
    for row in record['fingerprints']:
        row['path'] = os.path.relpath(row['path'], package)
    record['producer']['path'] = os.path.relpath(record['producer']['path'], package)
    record_path = save('relative-package/record.json', record)
    cert = read(HERE/'referenced-7.json')
    cert['run_record_ref']['path'] = record_path.name
    cert['run_record_ref']['sha256'] = hashlib.sha256(record_path.read_bytes()).hexdigest()
    cert['run_record_ref']['producer'] = copy.deepcopy(record['producer'])
    cert_path = save('relative-package/certificate.json', cert)
    assert call('relative-package-cycle-verify', 'verify-cycle', cert_path)[0] == 0
    call('relative-package-batch', 'verify-batch', package)
    output = HERE/'checkpoint-delta-record.json'
    base = ROOT/'数据/样例/生产循环环带.json'
    assert call('delta-run', 'run', base, '--ticks', 4, '--format', 'checkpoint_delta', '--checkpoint-interval', 3, '--out', output)[0] == 0
    checkpoint = HERE/'delta-checkpoint.json'
    assert call('delta-checkpoint', 'checkpoint', output, '--out', checkpoint)[0] == 0
    resumed = HERE/'delta-resumed-record.json'
    assert call('delta-resumed', 'run', checkpoint, '--ticks', 2, '--out', resumed)[0] == 0
    a=read(output);b=read(resumed)
    end=int(a['trace']['end_time']['value']['value'])
    first=int(b['trace']['ticks'][0]['time']['value']['value'])
    assert first==end+1
    save('delta-resume-comparison.json', {'previous_end':end,'resumed_first':first,'first_is_t_plus_one':True})
    save('extra-schema-results.json', schema([record_path,cert_path,output,resumed]))
    save('extra-results.json', CASES)
    print(json.dumps({'cases':len(CASES)},ensure_ascii=False))


if __name__=='__main__':
    main()
