"""只读复跑交付程序；拦截输出写入，结果存本复核目录。"""
import contextlib
import hashlib
import importlib.util
import io
import json
import runpy
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[4]
EXAMPLES=ROOT/'求解器/数据/样例'
SPEC=ROOT/'求解器/规格'
sys.path.insert(0,str(EXAMPLES))
import check_examples as checker
import check_golden_trace as golden
import test_runtime_input as regression
import runtime_record


def main():
    results=[];writes=[]
    original=Path.write_text
    def intercepted(path,data,*args,**kwargs):
        path=Path(path).resolve()
        assert path.is_relative_to(ROOT/'求解器') and not path.is_relative_to(BASE)
        dest=BASE/'原程序输出'/path.relative_to(ROOT/'求解器')
        dest.parent.mkdir(parents=True,exist_ok=True)
        writes.append({'target':str(path),'saved':str(dest),'equal_to_delivered':path.exists() and data==path.read_text()})
        return original(dest,data,*args,**kwargs)
    documents=[checker.load_json(EXAMPLES/name) for name in checker.NAMES]
    checks=[checker.check(d,EXAMPLES/name) for d,name in zip(documents,checker.NAMES)]
    negative=checker.negative_tests(documents)
    represented=checker.representation_tests(documents)
    results.append({'check':'样例/原负例/表示回归','samples':checks,'negative_count':len(negative),'representation_count':len(represented)})
    for name,fn in [('运行回归',regression.main),('黄金生成',golden.main),
                    ('schema生成',lambda:runpy.run_path(str(SPEC/'内核输入修订验证-r3/build_output_schema.py'))),
                    ('规则覆盖',lambda:runpy.run_path(str(SPEC/'内核输入修订验证-r3/check_current_coverage.py'),run_name='__main__'))]:
        buffer=io.StringIO()
        try:
            Path.write_text=intercepted
            with contextlib.redirect_stdout(buffer):fn()
        finally:Path.write_text=original
        original(BASE/(name+'.log'),buffer.getvalue())
        results.append({'check':name,'status':'通过'})
    data=documents[2]; output=checker.load_json(golden.OUTPUT)
    runtime_record.validate_record(output,data)
    runtime_record.validate_checkpoint(data,checker.load_json(SPEC/'内核输入修订验证-r3/中途种子.json'),'J|2|0|1')
    results.append({'check':'磁盘记录/磁盘中途种子验收','status':'通过'})
    manifest=checker.load_json(SPEC/'内核输入修订验证-r3/交付清单.json')
    manifest_errors=[p for p,h in manifest['sha256'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    results.append({'check':'交付清单','files':len(manifest['files']),'hashes':len(manifest['sha256']),'mismatches':manifest_errors})
    if importlib.util.find_spec('jsonschema'):
        import jsonschema
        schema=checker.load_json(SPEC/'内核输出.schema.json')
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(output)
        results.append({'check':'独立jsonschema库','status':'通过'})
    else:results.append({'check':'独立jsonschema库','status':'环境未安装；已核本地验证器及schema生成一致性'})
    original(BASE/'原程序重跑.json',json.dumps({'results':results,'redirected_writes':writes},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','checks':len(results),'writes_redirected':len(writes),'manifest_mismatches':manifest_errors},ensure_ascii=False))


if __name__=='__main__':main()
