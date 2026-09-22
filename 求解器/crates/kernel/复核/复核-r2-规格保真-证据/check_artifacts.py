"""复核既有产物与测试；仅重定向原CLI测试的写入目录，不改断言。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / 'crates/kernel/tests'))
import verify_outputs as verifier


def main():
    """来源闭合、四记录完整重算及原修订负例保持独立记录。"""
    reports = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = verifier.checker.load_json(ROOT / f'数据/样例/{name}.json')
        expected = verifier.run(data)
        for suffix in ('运行记录-kernel', '运行记录-checkpoint_delta-kernel'):
            reports.append(verifier.verify(ROOT / f'数据/样例/{name}-{suffix}.json', data, expected))
    evidence = ROOT / 'crates/kernel/evidence/revision-r1'
    inspected = {}
    for p in sorted(evidence.glob('*.json')):
        data = json.loads(p.read_text())
        inspected[p.name] = {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'top_level': list(data), 'status': data.get('status')}
        if p.name == 'baseline.json':
            inspected[p.name]['top_level'] = '指纹映射'
            inspected[p.name]['entries'] = len(data)
        if p.name == 'deliverables.json':
            inspected[p.name]['mismatches'] = [r['path'] for r in data['files'] if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() != r['sha256']]
    sys.argv = ['revision_cli.py', str(OUT/'target/debug/kernel')]
    spec = importlib.util.spec_from_file_location('original_cli_test', ROOT/'crates/kernel/tests/revision_cli.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EVIDENCE = OUT
    module.OUT = OUT/'cli-temporary'
    module.main()
    configuration = json.loads((ROOT/'规格/内核配置-v1.json').read_text())
    counts = {}
    for axis, row in configuration['axes'].items():
        counts[row['disposition']] = counts.get(row['disposition'], 0) + 1
    result = {'records': reports, 'implementation_evidence': inspected, 'configuration_counts': counts,
              'stop_axes': {k:v['value'] for k,v in configuration['axes'].items() if v['disposition']=='超出覆盖即停'}}
    (OUT/'既有产物核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'records':len(reports),'counts':counts,'deliverable_mismatches':inspected['deliverables.json']['mismatches']},ensure_ascii=False))


if __name__ == '__main__':
    main()
