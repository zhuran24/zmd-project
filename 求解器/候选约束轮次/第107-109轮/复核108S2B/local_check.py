"""局部状态穷举、桥层数枚举和失效读法负对照。"""
from itertools import product
import random,json
from pathlib import Path
from transport import Topology,Transport

def all_layers():
    words=components=0
    for n in range(1,13):
        for word in product('TB',repeat=n):
            tp=Topology([('源','终点','货')],[''.join(word)],pair=False)
            # 与 DFS 不同的编码：连续传送带先压成一个符号，再数后缀。
            compressed=[]
            for x in word:
                if x=='B' or not compressed or compressed[-1]!='T':compressed.append(x)
            expected=list(range(len(compressed),0,-1))
            assert [tp.layers[c] for c in tp.route_components[0]]==expected
            words+=1;components+=len(compressed)
    return {'max_length':12,'words':words,'component_roots':components,'disagreements':0}

def all_states():
    rng=random.Random(108500);cases=0;source_cases=0
    for n in range(1,6):
        for word in product('TB',repeat=n):
            tp=Topology([('源','终点','货')],[''.join(word)],pair=False)
            rank=tp.order(rng)
            for ages in product([None,0,7,8],repeat=n):
                for can_receive in [False,True]:
                    a=Transport(tp,empty=True);b=Transport(tp,True,empty=True)
                    for obj in (a,b):
                        for c,age in enumerate(ages):
                            if age is not None:obj.entered[c]=-age;obj.last[c]=tp.expected_last[c]
                        obj.step(0,rank,lambda r:can_receive)
                    assert a.observable(0)==b.observable(0),(word,ages,can_receive)
                    # 无来源供货和有货、当步补首格两种非运输尾阶段。
                    source_cases+=1
                    if a.entered[0] is None:
                        a.put(0,0,'源');b.put(0,0,'源')
                    assert a.observable(0)==b.observable(0)
                    source_cases+=1;cases+=1
    return {'lengths':[1,5],'age_classes':['empty',0,7,8],'transition_cases':cases,'source_variants':source_cases,'disagreements':0}

def crossing_and_negative():
    tp=Topology([('甲来源','甲终点','甲物品'),('乙来源','乙终点','乙物品')],['TBT','TBTBTBT'],forced_pairs=[(1,4)])
    rng=random.Random(108501);a=Transport(tp);b=Transport(tp,True);bad=Transport(tp)
    bad.negative_whole_bridge_group=True
    rank=tp.order(rng);first_bad=None
    for t in range(4096):
        if t%7==0:
            rank=tp.order(rng)
            if t%14==0:
                for obj in (a,b,bad):obj.reset_history()
        for obj in (a,b,bad):
            obj.step(t,rank,lambda r:True)
            for r,(src,_,_) in enumerate(tp.routes):
                c=tp.paths[r][0]
                if obj.entered[c] is None:obj.put(c,t,src);obj.sent[r]+=1
        assert a.observable(t)==b.observable(t)
        if first_bad is None and a.entered!=bad.entered:first_bad=t
    # 检验的是逐步不等价；不把一个暂态时差误称长期吞吐反例。
    assert first_bad is not None
    # 故意污染来源记录，检测器必须拒绝；不算候选允许的状态。
    q=Topology([('源','终点','货')],['TBBT'],pair=False)
    invalid=Transport(q);invalid.last[1]=q.physical[2]
    caught=False
    try:invalid.step(0,q.order(rng),lambda r:True)
    except AssertionError:caught=True
    assert caught
    return {'steps':4096,'same_physical_bridge':True,'normal_disagreements':0,
            'negative_whole_unit_first_difference':first_bad,'normal_delivery':a.received,
            'negative_whole_unit_delivery':bad.received,'wrong_provenance_detected':caught,
            'negative_is_candidate_counterexample':False}

if __name__=='__main__':
    result={'layers':all_layers(),'states':all_states(),'crossing':crossing_and_negative()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
