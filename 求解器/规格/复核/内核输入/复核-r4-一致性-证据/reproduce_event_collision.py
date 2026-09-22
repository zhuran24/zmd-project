import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('求解器/数据/样例').resolve()))
import check_golden_trace as g
import runtime_example as ex
import runtime_record as rr
import test_runtime_input as t
x=g.checker.load_json(g.INPUT)
ex.write_profile(x)
g.main()
y=g.checker.load_json(g.OUTPUT)
rr.validate_record(y,x)
schema=g.checker.load_json(Path('求解器/规格/内核输出.schema.json'))
t.validate_schema(y,schema,schema)
ids={e['id'] for e in y['input_history']['timeline']['events']}
print(json.dumps({'stored_record_accepted':True,'collisions':[e for k in y['trace']['ticks'] for e in k['events'] if e['event'] in ids]},ensure_ascii=False))
