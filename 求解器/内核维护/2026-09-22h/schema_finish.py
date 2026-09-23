from helpers import *
from guard import guard
guard('schema-edit-before')
p=ROOT/'规格/内核输出.schema.json';schema=json.loads(p.read_text())
def walk(v):
    if isinstance(v,dict):
        props=v.get('properties',{})
        if {'item','quantity','entered_at'} <= props.keys():
            props['last_unit']={'type':['string','null']}
        for child in v.values():walk(child)
    elif isinstance(v,list):
        for child in v:walk(child)
walk(schema);write(p,dump(schema))
guard('schema-edit-after')
