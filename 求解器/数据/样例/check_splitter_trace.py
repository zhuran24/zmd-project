#!/usr/bin/env python3
"""仓库供矿的三路轮询有限参考执行与两种输出编码验收。"""
import copy
import json
from pathlib import Path
import check_examples as checker
from check_golden_trace import run
from checkpoint_delta import encode_trace
from runtime_record import build_record, validate_record

BASE = Path(__file__).resolve().parent


def main():
    data = checker.load_json(BASE / '分流器三路轮询.json')
    ticks = run(data)
    record = build_record(data, ticks)
    validate_record(record, data, ticks)
    target = BASE / '分流器三路轮询-运行记录.json'
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    compact = copy.deepcopy(record)
    compact['trace'] = encode_trace(record['trace'], 4)
    validate_record(compact, data, ticks)
    (BASE / '分流器三路轮询-运行记录-checkpoint_delta.json').write_text(json.dumps(compact, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status':'通过', 'ticks':len(ticks), 'last_summary':ticks[-1]['summary'],
                      'events':[len(t['events']) for t in ticks], 'output':str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
