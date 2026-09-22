#!/usr/bin/env python3
"""只从环带循环起点及条款手推20刻；不调用内核转移或Python参考执行器。"""
import copy
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def q(n, category='算术推论'):
    return {'value':str(n),'category':category}
def tv(n):
    return {'kind':'rational','value':q(n,'候选')}
def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    cert=json.loads((OUT/'生产循环环带-fresh-cycle.json').read_text())
    cycle=cert['cycle']
    assert cycle['start_time']==tv(0) and cycle['period']==q(20)
    start=copy.deepcopy(cycle['start_state'])
    state=copy.deepcopy(start)
    channels=['PC|a:east:0|b:south:0','PC|b:east:0|c:south:0',
              'PC|c:east:0|d:south:0','PC|d:east:0|a:south:0']
    move_basis=['规则 L13、L15–17、L23–25、L29–32','约束端口速率',
                '受限模型声明 polling.both_failure','内核输入 §5.2、§6.3']
    transfer_basis=['规则 L20–21、L36','受限转移定义 §4.3']
    ledger_fields=['core_inbound','wireless_inbound','port_outbound','external_supply',
                   'player_withdrawal','representative_adjustment']
    products=['精选荞愈胶囊','高容谷地电池']
    pos=1
    entered=0
    cooldown=5
    expected=[]
    table=[]
    for t in range(1,21):
        # 两矿不出入；胶囊5件属于t=0前缀，首步代表化独立扣除，不记入库。
        adjustment=[]
        for row in state['warehouse']['slots']:
            if row['item'] in products and int(row['quantity']['value']):
                item=row['item'];n=int(row['quantity']['value'])
                adjustment.append({'item':item,'quantity':q(n),'reason':'production_representative'})
                row.update(item=None,quantity=q(0),empty_identity={
                    'status':'specified','value':item,'basis':['受限转移§6.1：生产代表保留身份']})
        cooldown=max(cooldown-1,0)
        events=[]
        movements=[]
        # 每侧单成员：所有源取货侧授权自身，任何失败不改变游标。
        # 每刻只有一件可动货，进入下一格后因年龄0不能再动；第二轮无状态变化即闭包。
        for sweep in range(2):
            for i,ch in enumerate(channels):
                if pos!=i:
                    outcome,detail='failure','source_empty'
                elif entered==t:
                    outcome,detail='failure','residence'
                else:
                    outcome,detail='success',''
                    pos=(i+1)%4;entered=t
                    movements.append(dict(channel=ch,event=f'J|{t}|{sweep}|{i}',item='高容谷地电池',quantity=q(1)))
                events.append(dict(event=f'J|{t}|{sweep}|{i}',operation='move',target=ch,
                                   outcome=outcome,detail=detail,basis=move_basis))
            outcome,detail=('success','empty_box') if cooldown==0 else ('guard_false','cooldown')
            if cooldown==0:cooldown=5
            events.append(dict(event=f'J|{t}|{sweep}|4',operation='transfer',target='box',
                               outcome=outcome,detail=detail,basis=transfer_basis))
        assert len(movements)==1
        occupied='abcd'[pos]+':transport:0'
        for row in state['inventory']:
            row['contents']=[dict(item='高容谷地电池',quantity=q(1),entered_at=tv(t))] if row['slot']==occupied else []
        state['progress'][0]['cooldowns'][0]['remaining']=tv(cooldown)
        state['environment']['time']=tv(t)
        sc=state['semantic_context']
        sc['judgment_context']['value']['instant']=tv(t)
        source,target=movements[0]['channel'].split('|')[1:]
        sc['tick_context']['value']=dict(window_start=tv(t),window_end=tv(t+1),movements=movements,
             port_usage=[dict(port=p,quantity=q(1)) for p in sorted([source,target])],internal_passages=[])
        ledger={f:[] for f in ledger_fields}
        ledger['representative_adjustment']=adjustment
        ledger['totals']=[dict(item=item,**{f:q(5 if f=='representative_adjustment' and item=='精选荞愈胶囊' and t==1 else 0)
            for f in ledger_fields+['actual_inbound']}) for item in products]
        row=dict(time=tv(t),state=copy.deepcopy(state),events=events,warehouse_ledger=ledger,
            closure=dict(kind='no_success_state_repeat',scan_rounds=2,basis=['受限模型声明 time.instant_end','内核输入 §5.2']))
        expected.append(row)
        table.append(dict(tick=t,move=movements[0]['channel'],occupied=occupied,cooldown=cooldown,
                          empty_transfer=(t%5==0),inbound=0,representative_adjustment=5 if t==1 else 0))
    save('manual-expected.json',expected)
    actual=[{k:r[k] for k in expected[0]} for r in cert['run_record']['trace']['ticks'][1:]]
    # 任一差异保留具体路径；类别与据也参与完整状态比较。
    def diff(a,b,path=''):
        if type(a)!=type(b):return [dict(path=path,expected=a,actual=b)]
        if isinstance(a,dict):
            if a.keys()!=b.keys():return [dict(path=path,expected=list(a),actual=list(b))]
            return [d for k in a for d in diff(a[k],b[k],path+'/'+k)]
        if isinstance(a,list):
            if len(a)!=len(b):return [dict(path=path,expected=len(a),actual=len(b))]
            return [d for i,(x,y) in enumerate(zip(a,b))for d in diff(x,y,path+'/'+str(i))]
        return [] if a==b else [dict(path=path,expected=a,actual=b)]
    differences=diff(expected,actual)
    save('manual-period-check.json',dict(status='pass' if not differences else 'fail',period=20,
        compared_fields=list(expected[0]),ticks=20,events=200,table=table,differences=differences))
    print(json.dumps(dict(differences=len(differences),first=differences[:3]),ensure_ascii=False))
    assert not differences

if __name__=='__main__':main()
