"""从有竞争流的物理配置构造显式条件种子；非运输年龄选null，不宣称原轨迹逐字段可达。"""
import copy
import round5_scenarios as s
from audit_round5 import read
from runtime_example import decision
source=read(s.OUT/'密集结点闭环核验.json');record=read(s.OUT/'密集结点闭环核验-运行记录-v3-kernel.json')
seed=copy.deepcopy(record['trace']['ticks'][-1]['state']);kinds={u['id']:u['kind']for u in source['layout']['units']}
for row in seed['inventory']:
    if kinds[row['slot'].split(':')[0]]=='协议储存箱':
        for content in row['contents']:content['entered_at']=None
source['initial_state']['nonwarehouse']['value']=seed
source['initial_state']['reachability']=decision({'kind':'conditional_state','document':'第五轮样例说明-kernel.md','scope':'库存/门/物流采用240刻闭环后态；非运输格进入时刻显式选null，是另一个条件种子，不声称与原轨迹完整StateSeed相同或已证明可达'},'输入§6允许非运输entered_at=null；状态族可达性仍未证明')
s.finish(source,'密集结点循环种子核验',100,True)
