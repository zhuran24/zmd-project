"""交付前核查：原件字节、逐条判定、实际探针与证据目录约束。"""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
REPORT = OUT.parent / '否证-r3-1.md'


def read(name):
    return json.loads((OUT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reasons = [
        ('KR-r3-L1-01', '未能否证：输入§6.4要求原样保留检查点参数；独立实测缺失/冲突输入直接run拒收，经seed覆盖后续跑成功。完整论证：/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/复核/否证-r3-1.md §2.1。'),
        ('KR-r3-L1-02', '未能否证：after_closure的t=5仍接受deadline=5，并在t=6执行W|5事件，verify-record拒收；before_boundary同值则在t=5合法执行。见论证文件§2.2。'),
        ('KR-r3-L1-03', '未能否证：新跑P=1结果的verify-cycle返回cycle_replayed=true，原样提取run_record却因前缀窗口时序非法被verify-record拒收；代码未调用全记录独立事件检查。见§2.3。'),
        ('KR-r3-L1-04', '未能否证：sufficient明确要求种子两矿正库存；源矿为空而仅留历史身份时seed仍成功，导出输入推进一刻才invalid_input。见§2.4。'),
        ('KR-r3-L2-01', '未能否证：新生成桥检查点的参数清空、镜像冲突、仅改顶层相位三例均run拒收、seed覆盖成功；合法对照状态完整保留。见§2.5。'),
        ('KR-r3-L2-02', '未能否证：同步参数与镜像后，-1、6、1/2及not-a-Time均被run接受；非法字符串还进入P=20周期并通过verify-cycle，超出Time及整数0…5支持域。见§2.6。'),
        ('KR-r3-L2-03', '未能否证：新跑桥记录把32条成功搬运标作先接覆盖，但方向在输入中已resolved、先接历史早于记录；聚合所列10份证据也全部是move。见§2.7。'),
        ('KR-r3-L3-01', '未能否证：slot=bad及nonwarehouse.value=true分别复现run/seed退出101、stdout为空且无结果文件；正常非法标签对照能返回invalid_input，证实并非约定Stop。见§2.8。'),
        ('KR-r3-L3-02', '未能否证：同源时差溢出输入的run为inconclusive，cycle却为stopped且内层仍是resource；装载外壳丢失顶层资源未决分类。见§2.9。'),
        ('KR-r3-L3-03', '未能否证：独立扫描仍有15个ELF/ar共219896964字节及193文件的仓库式快照，内含独立空target；遗留属性不消除证据类型违纪，不归责本轮新增。见§2.10。'),
    ]
    verdicts = {'verdicts': [dict(id=identifier, refuted=False, reason=reason) for identifier, reason in reasons]}
    (OUT / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + '\n')
    protected = read('source-hashes-final.json')['files']
    protected.update({p: value for p, value in read('supplement-results.json')['source_hashes'].items()
                      if not Path(p).is_relative_to(OUT)})
    changed = [p for p, value in protected.items() if sha(Path(p)) != value]
    assert not changed, changed
    calls = read('calls.json')
    assert len(calls) == 45 and len({r['name'] for r in calls}) == 45
    rows = {r['name']: r for r in calls}
    expected = {
        'crusher-control': (0, 'completed'), 'crusher-checkpoint-seed': (0, None),
        'crusher-missing-direct': (2, 'invalid_input'), 'crusher-missing-seed': (0, None),
        'crusher-missing-resumed': (0, 'completed'), 'crusher-supply-conflict-direct': (2, 'invalid_input'),
        'crusher-supply-conflict-seed': (0, None), 'crusher-supply-conflict-resumed': (0, 'completed'),
        'bridge-record-verification': (0, 'input_checked'), 'bridge-control-direct': (0, 'completed'),
        'bridge-control-seed': (0, None), 'gate-expired-seed': (0, None), 'gate-expired-run': (0, 'completed'),
        'gate-expired-verification': (2, 'invalid_input'), 'tiny-expired-cycle': (0, 'counterexample'),
        'tiny-expired-cycle-verification': (0, 'input_checked'), 'tiny-embedded-verification': (2, 'invalid_input'),
        'phase-string-cycle': (0, 'counterexample'), 'phase-string-cycle-verification': (0, 'input_checked'),
        'zero-ore-seed': (0, None), 'zero-ore-run': (2, 'invalid_input'),
        'overflow-run': (2, 'inconclusive'), 'overflow-cycle': (2, 'stopped'),
        'bad-slot': (101, None), 'bad-unit': (2, 'invalid_input'), 'boolean-seed': (101, None),
        'tiny-before-boundary': (0, 'completed'), 'tiny-before-boundary-verification': (0, 'input_checked'),
    }
    for case in ['missing', 'mirror-conflict', 'top-conflict']:
        expected['bridge-' + case + '-direct'] = (2, 'invalid_input')
        expected['bridge-' + case + '-seed'] = (0, None)
    for case in ['valid-zero', 'negative', 'six', 'fraction', 'string']:
        expected['phase-' + case] = (0, 'completed')
    for name, pair in expected.items():
        assert (rows[name]['exit_code'], rows[name]['status']) == pair, name
    for name in ['bad-slot', 'boolean-seed']:
        assert rows[name]['stdout'] == '' and not rows[name]['output_exists']
    assert read('tiny-expired-cycle.json')['run_record'] == read('tiny-embedded-record.json')
    assert read('tiny-expired-cycle-verification.json')['cycle_replayed'] is True
    assert read('phase-string-cycle-verification.json')['cycle_replayed'] is True
    checks = read('checks.json')
    assert checks['crusher_checkpoint_preserved'] and checks['bridge_control_state_preserved']
    assert checks['tiny_cycle']['period']['value'] == '1' and checks['phase_string_period']['value'] == '20'
    doc = REPORT.read_text()
    for identifier, _ in reasons:
        assert doc.count(identifier) == 1, identifier
    assert doc.count('**判定：未能否证，refuted=false。**') == 10
    missing_links = []
    for target in re.findall(r'\]\(([^)]+)\)', doc):
        path = Path(target) if target.startswith('/') else REPORT.parent / target
        if path == OUT / '交付核验.json':
            continue
        if not path.exists():
            missing_links.append(target)
    assert not missing_links, missing_links
    files = [p for p in OUT.rglob('*') if p.is_file()]
    unexpected = [str(p) for p in files if p.suffix not in ['.py', '.log', '.json', '.md']]
    forbidden = [str(p) for p in OUT.rglob('*') if p.is_dir() and p.name in ['target', '.cargo-home', 'registry', '__pycache__']]
    assert not unexpected and not forbidden
    scan = read('directory-scan.json')
    assert scan['count'] == 15 and scan['bytes'] == 219896964
    assert scan['snapshot']['count'] == 193 and scan['snapshot']['target_children'] == []
    report = dict(status='pass', protected_originals=len(protected), changed_originals=changed,
        cli_calls=len(calls), asserted_cli_outcomes=len(expected), verdict_ids=[r[0] for r in reasons],
        missing_links=missing_links, forbidden_evidence_files=unexpected, forbidden_evidence_dirs=forbidden,
        evidence_files=len(files), evidence_bytes=sum(p.stat().st_size for p in files), report_sha256=sha(REPORT),
        reading_review=['十项均有原文依据、代码与现场证据、可反驳方向及适用边界',
                        '区分历史遗留、当前实现、条件负例与真实任务可达性',
                        '路径与编号齐全；未将完整构建或45次CLI写成完整回归测试'])
    (OUT / '交付核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
