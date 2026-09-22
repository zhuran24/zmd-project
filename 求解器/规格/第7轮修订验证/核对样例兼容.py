"""只读重验当前99轴样例、负例和黄金轨迹，不刷新任何来源锁。"""
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EXAMPLES = ROOT / '求解器/数据/样例'
SPEC = BASE.parent
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
import check_golden_trace as golden_checker
import runtime_example as runtime
import runtime_record
from test_runtime_input import validate_schema


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = checker.load_json(SPEC / '内核配置-v1.json')
    assert config['axis_count'] == 99
    assert digest(SPEC/'内核配置-v1.json') == runtime.SUPPORTED_PROFILE_SHA256
    source_paths = [path for path in EXAMPLES.iterdir() if path.is_file()]
    source_paths += [SPEC/name for name in ['选择点参数轴.md', '受限模型声明.md', '内核配置-v1.json', '受限转移定义.md', '运行语义.md', '内核输入.md', '内核输出.md', '内核输出.schema.json']]
    before = {str(path): digest(path) for path in source_paths}
    documents = [checker.load_json(EXAMPLES/name) for name in checker.NAMES]
    for data in documents:
        assert len(runtime.axis_values(data)) == 99
    results = [checker.check(data, EXAMPLES/name) for data, name in zip(documents, checker.NAMES)]
    negatives = checker.negative_tests(documents)
    representations = checker.representation_tests(documents)
    data = next(data for data in documents if data['purpose'] == 'synthetic_execution')
    profile = runtime.validate_profile(data, checker.load_json(runtime.PROFILE_PATH))
    ticks = golden_checker.run(data)
    golden = checker.load_json(EXAMPLES/'混做粉碎机两下游-黄金轨迹.json')
    assert [tick['summary'] for tick in ticks] == golden['ticks']
    # 校验C线持久记录实际内容及其来源，不能只比较摘要。
    output = checker.load_json(EXAMPLES/'混做粉碎机两下游-运行记录.json')
    schema = checker.load_json(SPEC/'内核输出.schema.json')
    validate_schema(output, schema, schema)
    runtime_record.validate_record(output, data, ticks)
    for tick in ticks:
        occupied = set()
        for slot in tick['state']['inventory']:
            unit, role, index = slot['slot'].split(':')
            if role == 'buffer':
                continue
            for row in slot['contents']:
                key = (unit, row['item'])
                assert key not in occupied, ('同单位同种跨格', key)
                occupied.add(key)
    assert before == {str(path): digest(path) for path in source_paths}, '共享文件检查期间变化，须重跑'
    report = {'status': 'PASS', 'scope': '当前C线原产物只读检查，未临时刷新哈希或改赋值；非全称认证',
              'axis_count': 99, 'samples': results, 'negative_tests': negatives, 'representation_tests': representations,
              'golden_match': True, 'schema_matches': True, 'full_record_matches_recomputation': True, 'ticks': len(ticks),
              'completed_batches': ticks[-1]['summary']['completed_batches'], 'sources': before}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
