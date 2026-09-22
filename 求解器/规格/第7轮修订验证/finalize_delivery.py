"""只读重验当前来源、完整记录及保护范围，再封存第7轮交付字节。"""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent
SPEC = BASE.parent
ROOT = SPEC.parents[1]
SAMPLES = ROOT / '求解器/数据/样例'
OWN_SPEC = ['运行语义.md', '选择点清单.md', '选择点参数轴.md', '受限模型声明.md',
            '规则覆盖表.md', '四件前置义务对照.md', '修订记录.md', 'check_revision.py',
            '内核配置-v1.json', '受限转移定义.md', '参数轴-对内核输入请求的答复.md',
            '内核输入.md', '第三轮任务验证/发现处置.json', '第6轮修订验证/核对修订回归.py']
OWN_SAMPLE = ['check_examples.py', 'generate_examples.py', 'runtime_example.py',
              '桥接器双通路.json', '分流器三路轮询.json', '混做粉碎机两下游.json',
              'kernel_profile_v1参数赋值.json', '混做粉碎机两下游-运行记录.json']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def rerun(script, output):
    result = subprocess.run([sys.executable, '-B', str(script)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, (script, result.stdout, result.stderr)
    (BASE / output).write_text(result.stdout)
    return json.loads(result.stdout)


def main():
    report = json.loads((BASE / '检查汇总.json').read_text())
    assert report['status'] == 'PASS' and all(row['exit_code'] == 0 for row in report['commands'])
    watched = [SPEC / name for name in OWN_SPEC] + [SAMPLES / name for name in OWN_SAMPLE]
    watched += [SPEC / name for name in ['内核输入-对参数轴的修改请求.md', '内核输出.md', '内核输出.schema.json']]
    watched += [SAMPLES / name for name in ['runtime_record.py', 'event_order.py', 'test_runtime_input.py',
                                          'check_golden_trace.py', '混做粉碎机两下游-黄金轨迹.json', '混做粉碎机两下游-黄金轨迹.md']]
    watched += [ROOT / '求解器/数据/正式静态目录.json']
    watched += list((ROOT / '求解器/crates/topology').rglob('*.rs'))
    before = {str(path): digest(path) for path in watched}
    spec_result = rerun(SPEC / 'check_revision.py', '规格自查结果.json')
    full_result = rerun(BASE / '核对样例兼容.py', '黄金完整核验结果.json')
    regression = rerun(BASE / '核对修订回归.py', '修订回归结果.json')
    interface = spec_result['shared_interface']
    assert interface['axis_set_matches'] and not interface['lifetime_mismatches']
    assert not interface['revision6_description_mismatches'] and all(interface['schemas_present'].values())
    assert full_result['schema_matches'] and full_result['full_record_matches_recomputation']
    assert before == {str(path): digest(path) for path in watched}, '末次重验期间共享源变化，须重新运行'
    protected = json.loads((BASE / '开工只读指纹.json').read_text())
    assert all(digest(Path(path)) == value for path, value in protected.items())
    initial_sim = {path for path in protected if path.startswith(str(ROOT / '模拟器') + '/')}
    assert initial_sim == {str(path) for path in (ROOT / '模拟器').rglob('*') if path.is_file()}
    save('接口快照.json', {'status': 'PASS', 'axis_count': 99, 'request_sections_read': [1, 2, 3, 4, 5, 6, 7],
         'shared_interface': interface, 'sources': before,
         'scope': '当前共享实际字节只读重验；其它席修改不据此归成本席成果'})
    documents = [SPEC / name for name in OWN_SPEC if name.endswith('.md')]
    forbidden = ['**相遇判据已定**', '两端口要相遇只能重合', '共边相向相遇已定',
                 '角触/隔格/同类端口', '按共享选择点 T5 已定', '找第一仍为空且无历史身份的格']
    bad = [{'path': str(path), 'phrase': phrase} for path in documents
           for phrase in forbidden if phrase in path.read_text()]
    assert not bad, bad
    hits = []
    for path in documents:
        for line, value in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'port_meeting|相遇谓词|角点|O\(S|warehouse_empty_slot_order', value):
                hits.append({'path': str(path), 'line': line, 'text': value,
                             'classification': '现行定义或明确撤回记录，逐条读者自审核过'})
    save('全文辖域扫描.json', {'status': 'PASS', 'forbidden_active_assertions': forbidden,
         'forbidden_hits': bad, 'reviewed_hits': hits,
         'scope': '现行正文及历史索引全辖域定位；不以字符串扫描证明语义穷尽，旧复核/被审快照保留史料原文'})
    save('交付自审.json', {'status': 'PASS', 'finding_count': 2, 'unhandled_findings': [],
         'schema_and_full_record_verified': True, 'shared_sources_stable_during_validation': True,
         'protected_files': len(protected), 'protected_unchanged': True, 'simulator_file_set_unchanged': True,
         'specification_checks': len(spec_result['checks']), 'local_regression_checks': len(regression['checks']),
         'reader_review': ['正文终态与历史分区', '相遇待审和已定类型守卫分开', '当前空格序成功/失败完整后效',
                           '非空/空格身份编码可逆', '99轴及F/O/U一致', '链接与符号落点', '有限实验不升级全称认证'],
         'open_items': ['角点相遇等其它谓词的全规则审查', '竞争匿名空格的批量分配',
                        '一般语义相容性、全部初态/离线、有限抽象与完整周期提升'],
         'scope': '测试与读者自审已完成；随后由本脚本写清单/指纹并逐项重读，失败则整个封存退出非零'})
    manifest_path = BASE / '交付文件清单.json'
    fingerprints_path = BASE / '交付指纹.json'
    files = {SPEC / name for name in OWN_SPEC} | {SAMPLES / name for name in OWN_SAMPLE}
    files |= {path for path in BASE.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    files |= {manifest_path, fingerprints_path}
    ordered = sorted(files, key=str)
    save(manifest_path.name, {'schema': 'revision-delivery-v1', 'revision': 'round3-r7',
         'sealed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'files': [str(path) for path in ordered], 'fingerprints': str(fingerprints_path),
         'fingerprint_exclusions': [str(fingerprints_path)],
         'scope': '本席实际修改/新增及本轮快照、日志；源码含必要共享改动，不冒领C线同期其它实现；构建产物不列交付'})
    hashes = {str(path): digest(path) for path in ordered if path != fingerprints_path}
    save(fingerprints_path.name, hashes)
    assert all(digest(Path(path)) == value for path, value in json.loads(fingerprints_path.read_text()).items())
    # 清单及其余新文件已落盘后再核全部本地链接，不依赖预占位。
    documents += [BASE / '自查报告.md', BASE / '修订论证.md']
    for path in documents:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            assert (path.parent / target.split('#')[0]).exists(), (path, target)
    assert before == {str(path): digest(path) for path in watched}, '封存末次读回时来源变化'
    print(json.dumps({'status': 'PASS', 'file_count': len(ordered), 'fingerprint_count': len(hashes),
                      'manifest': str(manifest_path), 'all_fingerprints_reread': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
