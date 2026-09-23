from helpers import *
import re, sys
from guard import digest
p=ROOT/'crates/kernel/src/polling.rs';t=p.read_text();a=t.index('                    *key == &format!(');b=t.index('\n                })',a)
edit('crates/kernel/src/polling.rs',[(t[a:b],'                    *key == &self.memory.sides[*i].label()'),
    ('format!("{}:{}:{:?}", s.unit, s.side, s.axis)','s.label()')])
edit('规格/受限模型声明.md',[
    ('99轴处置保持，','99轴身份保留，桥接器取值和生命周期已同步，'),
    ('已定22项、本版选值44项、由输入全称量化15项、超出覆盖即停18项','已定25项、本版选值42项、由输入全称量化15项、超出覆盖即停17项')])
edit('规格/受限转移定义.md',[
    ('每单位存货侧按“直连分流器每条单级、其余合一级”分组','每单位存货侧（桥按每对边独立）按“直连分流器每条单级、其余合一级”分组'),
    ('级身份用所属单位、侧、成员类别','级身份用所属单位、桥轴（如有）、侧、成员类别')])
sys.path.insert(0,str(ROOT/'数据/样例'))
from runtime_example import profile_projection
for name,source in [('kernel_profile_v1参数赋值.json','混做粉碎机两下游.json'),('分流器三路轮询-参数赋值.json','分流器三路轮询.json')]:
    write(ROOT/'数据/样例'/name,dump(profile_projection(json.loads((ROOT/'数据/样例'/source).read_text()))))
