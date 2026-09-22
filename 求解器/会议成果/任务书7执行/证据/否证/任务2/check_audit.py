#!/usr/bin/env python3
"""任务2否证席：只写本目录；不装载内核，不修改被审脚本或指纹。"""
import contextlib
import hashlib
import io
import itertools
import json
from fractions import Fraction
from pathlib import Path
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
BASE = ROOT / '求解器/会议成果/任务书7执行'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def run_readonly(relative, mode):
    """读取原脚本字节执行，所有 Path.write_text 捕获到内存，再保存至本席。

    warehouse-arithmetic 模式仅替换 digest 的返回值为旧登记值，以跨过已明确
    报告的陈旧输入门槛；此模式只复算算术，绝不计为原版完整复现通过。
    """
    source = BASE / relative
    stdout, stderr = io.StringIO(), io.StringIO()
    writes = {}
    original = Path.write_text
    def capture(path, data, *args, **kwargs):
        if path.parent != source.parent or path.suffix != '.json':
            raise AssertionError('unexpected write: ' + str(path))
        writes[str(path)] = data
        return len(data)
    ns = {'__file__': str(source), '__name__': '__main__'}
    status, error = 0, None
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        Path.write_text = capture
        try:
            if mode == 'warehouse-arithmetic':
                ns['__name__'] = 'audit_loaded_warehouse'
                exec(compile(source.read_text(), str(source), 'exec'), ns)
                recorded = {e['path']: e['sha256'] for e in
                            json.loads((source.parent/'输入指纹.json').read_text())['sources']}
                original_digest = ns['digest']
                ns['digest'] = lambda p: recorded.get(str(p), original_digest(p))
                report = ns['run']()
                # 保存真实当前来源检查，绝不保留替代函数生成的假 same 字段。
                report['source_checks'] = [dict(path=p, expected=h, actual=sha(Path(p)),
                    same=sha(Path(p)) == h) for p,h in recorded.items()]
                report['status'] = 'arithmetic_only_pass'
                report['independent_review'] = 'only bounded arithmetic and live document checks'
                writes['warehouse-arithmetic.json'] = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
                print(json.dumps({'status': report['status'], 'cases': report['checks'][0]['cases'],
                                  'source_gate_overridden': True}, ensure_ascii=False))
            else:
                exec(compile(source.read_text(), str(source), 'exec'), ns)
        except SystemExit as exc:
            status = exc.code or 0
        except Exception as exc:
            status = 1
            error = f'{type(exc).__name__}: {exc}'
            traceback.print_exc()
        finally:
            Path.write_text = original
    artifacts = []
    for i,(declared_path,content) in enumerate(writes.items()):
        output = f'{mode}-{i}.json'
        (HERE/output).write_text(content)
        artifacts.append({'attempted_path': declared_path, 'captured_as': output})
    return {'source':str(source), 'source_sha256':sha(source), 'mode':mode,
            'exit_status':status, 'stdout':stdout.getvalue(), 'stderr':stderr.getvalue(),
            'error':error, 'captured_outputs':artifacts}

def main():
    # 全部被审材料与保护文件开始指纹到复核时点的比较。
    baseline = json.loads((HERE/'输入指纹.json').read_text())['files']
    unchanged = [{**e,'current_sha256':sha(ROOT/e['path']),
                  'same':sha(ROOT/e['path']) == e['sha256']} for e in baseline]
    assert all(e['same'] for e in unchanged)
    manifests = {
        'warehouse': (BASE/'证据/仓库/输入指纹.json', 'sources'),
        'derivation': (BASE/'证据/复核推导/输入指纹.json', 'files'),
        'derivation_extra': (BASE/'证据/复核推导/补充来源指纹.json', None),
    }
    dependencies = {}
    for name,(p,key) in manifests.items():
        data = json.loads(p.read_text()); entries = data[key] if key else data
        dependencies[name] = [dict(path=e['path'], expected=e['sha256'],
            actual=sha(Path(e['path'])), same=sha(Path(e['path']))==e['sha256']) for e in entries]

    # 与原脚本不同域：容量含0，待送0..6，两物种分别有不同容量。
    cases = 0
    for caps in itertools.product(range(6), repeat=2):
        for q in itertools.product(*(range(c+1) for c in caps)):
            for offered in itertools.product(range(7), repeat=2):
                got = tuple(min(offered[i], caps[i]-q[i]) for i in range(2))
                assert all(0 <= q[i]+got[i] <= caps[i] for i in range(2))
                assert all(got[i] == offered[i] or q[i]+got[i] == caps[i] for i in range(2))
                residual = tuple(offered[i]-got[i] for i in range(2))
                assert all(got[i]+residual[i] == offered[i] for i in range(2))
                cases += 1
    # 正式容量的局部数值；不作接收环境的定量阈值。
    edge = {'stock':[79999,80000], 'box':[2,3], 'received':[1,0], 'residual':[1,3]}
    assert edge['received']==[min(b,80000-q) for b,q in zip(edge['box'],edge['stock'])]
    # 非零成品净变、错误合并两种账、相同端点不同前缀。
    ledger = {'I':[12,11],'P':[11,12],'delta':[1,-1], 'aggregate_delta':0,
              'period':20, 'rates':[str(Fraction(12,20)),str(Fraction(11,20))]}
    assert [i-p for i,p in zip(ledger['I'],ledger['P'])] == ledger['delta']
    assert ledger['rates']==['3/5','11/20']
    # 这只是完整允许后态集合的算术，未给无线扣格选择法律地位。
    allocation = [x for x in itertools.product(range(3), repeat=3)
                  if sum(x)==1 and all(a<=b for a,b in zip(x,[1,0,1]))]
    assert allocation==[(0,0,1),(1,0,0)]
    # 再核旧报告计数与需用的最低产能算术。
    assert 2*51*51 == 5202
    assert 49*50+50*51+51*50 == 7550
    assert sum((c+1)**2*16 for c in range(1,6)) == 1440
    assert Fraction(18)+34+Fraction(11,2)+Fraction(21,2) == 68
    assert 34+17 == 51

    catpath=ROOT/'求解器/数据/正式静态目录.json'
    cat=json.loads(catpath.read_text())
    lock=[]
    for row in cat['sources']:
        path=ROOT/row['path']
        lock.append(dict(path=str(path), sha_same=row['sha256']==sha(path),
                         lines_same=row['lines']==path.read_text().splitlines()))
    assert all(x['sha_same'] and x['lines_same'] for x in lock)
    relock=BASE/'证据/规格/relock_sources.py'
    recorded=json.loads((BASE/'证据/规格/source-relock.json').read_text())
    provenance={
        'current_script_sha256':sha(relock),
        'script_catalog_before_algorithm':'sha256(json.dumps(old,ensure_ascii=False).encode())',
        'script_note':'catalog_before is parsed-value serialization digest; original byte digest is before.json.',
        'recorded_note':recorded['note'],
        'recorded_catalog_before_matches_before_json': recorded['catalog_before']==next(
            x['sha256'] for x in json.loads((BASE/'证据/规格/before.json').read_text())['files']
            if x['path']==str(catpath)),
        'interpretation':'当前脚本与结果说明采用不同前像摘要口径；核的是记录事实和当前正式源，未重跑有修改作用的重锁脚本。',
    }

    runs=[run_readonly('证据/仓库/check_warehouse.py','warehouse-original'),
          run_readonly('证据/仓库/check_warehouse.py','warehouse-arithmetic'),
          run_readonly('证据/复核推导/check_derivation.py','derivation-arithmetic'),
          run_readonly('证据/复核推导/validate_deliverables.py','derivation-validation')]
    dump('重跑日志.json',runs)
    result={'status':'pass','scope':'本席独立算术与证据链检查；各原脚本实际退出码见重跑日志',
        'initial_inputs_stable':unchanged,'dependency_checks':dependencies,
        'arithmetic_cases':cases,'capacity_edge':edge,'species_ledger':ledger,
        'partial_box_possible_deductions':allocation,'catalog_current':lock,
        'relock_provenance':provenance,'kernel':{'built':False,'loaded':False,'stepped':False}}
    dump('核对结果.json',result)
    print(json.dumps({'status':result['status'],'arithmetic_cases':cases,
        'dependency_mismatches':{k:sum(not e['same'] for e in v) for k,v in dependencies.items()},
        'script_runs':[{k:r[k] for k in ('mode','exit_status','error')} for r in runs],
        'input_files_stable':len(unchanged),'kernel_steps':0},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
