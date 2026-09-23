from helpers import *
p=ROOT/'crates/topology/tests/validation.rs';t=p.read_text()
old='''            "桥接器",
            1,
            1,
            2,
            2,
            false,
            vec![("vertical", Some(1), None), ("horizontal", Some(1), None)],'''
new='''            "桥接器",
            1,
            1,
            4,
            4,
            false,
            vec![("vertical", Some(1), Some(1)), ("horizontal", Some(1), Some(1))],'''
a=t.index('            "桥接器" =>');b=t.index('            "分流器" =>',a)
edit('crates/topology/tests/validation.rs',[(old,new),(t[a:b],'''            "桥接器" => vec![vec![
                edge("south", "bidirectional", vec![0]),
                edge("north", "bidirectional", vec![0]),
                edge("west", "bidirectional", vec![0]),
                edge("east", "bidirectional", vec![0]),
            ]],
''')])
p=ROOT/'规格/内核输出.schema.json';s=json.loads(p.read_text())
s['$defs']['Content']['properties']['last_unit']={'type':['string','null'],'description':'桥格物品刚离开的单位；初态未移动时可省略'}
write(p,dump(s))
