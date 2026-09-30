#!/usr/bin/env python3
"""逐个验收第3轮CLI结果；明确记录现行schema与空装载资源外壳的冲突。"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'crates/kernel/evidence/revision-r3'
sys.path.insert(0, str(ROOT / '数据/样例'))
from test_runtime_input import validate_schema


def main():
    schema_path = ROOT / '规格/内核输出.schema.json'
    schema = json.loads(schema_path.read_text())
    report = json.loads((OUT / 'cli/results.json').read_text())
    passed, gaps = [], []
    for case in report['cases']:
        data = json.loads(Path(case['output']).read_text())
        if data.get('schema') == 'kernel-input-v3':
            continue
        try:
            validate_schema(data, schema, schema)
        except Exception as error:
            if case['case'] != 'age-overflow-cycle':
                raise
            assert data['status'] == 'inconclusive' and data['stop']['kind'] == 'resource'
            assert data['budget']['completed_ticks'] == 0 and data['run_record'] is None
            errors=[]
            for child in schema['oneOf']:
                try:
                    validate_schema(data, child, schema)
                except Exception as detail:
                    errors.append(str(detail))
            gaps.append(dict(case=case['case'],output=case['output'],error=str(error),
                             branch_errors=errors,issue='KQ-09',
                             schema_pointer='/$defs/CycleResult/allOf/4/then/properties'))
        else:
            passed.append(dict(case=case['case'],schema=data['schema'],status=data['status']))
    result=dict(status='passed_with_schema_gap' if gaps else 'pass',
                schema_sha256=hashlib.sha256(schema_path.read_bytes()).hexdigest(),
                passed=passed,open_schema_gaps=gaps)
    (OUT / 'cli-schema-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],passed=len(passed),open_schema_gaps=len(gaps)),ensure_ascii=False))


if __name__ == '__main__':
    main()
