import sys,json
from guard import ROOT,OUT
sys.path.insert(0,str(ROOT/'数据/样例'))
from test_runtime_input import validate_schema
schema=json.loads((ROOT/'规格/内核输出.schema.json').read_text())
def strip(v):
    if isinstance(v,dict):
        v.pop('description',None)
        for child in v.values():strip(child)
    elif isinstance(v,list):
        for child in v:strip(child)
strip(schema)
record=json.loads((OUT/'positive/positive-run-final.json').read_text())
validate_schema(record,schema['$defs']['RunRecord'],schema)
