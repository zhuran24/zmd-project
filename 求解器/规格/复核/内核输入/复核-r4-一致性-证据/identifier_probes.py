"""最小标识符变异：验证仓库格与运行事件的命名冲突。"""
import json
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[4]
sys.path.insert(0,str(ROOT/'求解器/数据/样例'))
import check_examples as checker
import check_golden_trace as trace
from runtime_record import build_record


def renamed(value,old,new):
    if isinstance(value,dict):return {k:renamed(v,old,new) for k,v in value.items()}
    if isinstance(value,list):return [renamed(v,old,new) for v in value]
    return new if value==old else value


def main():
    data=checker.load_json(trace.INPUT);results=[]
    for label in ('crusher:input:0','feed_belt:transport:0'):
        modified=renamed(data,'warehouse_0',label)
        result={'case':'仓库槽位重命名','new_label':label,'input_validation':checker.check(modified,trace.INPUT)}
        try:
            ticks=trace.run(modified)
            result['summaries']=[t['summary'] for t in ticks]
            result['successful_warehouse_port_moves']=sum(m['channel'].startswith('PC|ore_source:') for t in ticks for m in t['state']['semantic_context']['tick_context']['value']['movements'])
            result['warehouse_loss']=80000-int(ticks[-1]['summary']['warehouse_ore'])
            try:build_record(modified,ticks,checker.load_json(trace.GOLDEN))
            except checker.CheckError as error:result['golden_gate']=str(error)
        except Exception as error:result['execution_error']={'type':type(error).__name__,'message':str(error)}
        results.append(result)
    modified=renamed(data,'build_13','J|0|0|0')
    accepted=checker.check(modified,trace.INPUT);ticks=trace.run(modified)
    history={e['id']:e for e in modified['timeline']['events']}
    results.append({'case':'建造事件重命名','input_validation':accepted,
                    'collisions':[{'input':history[e['event']],'runtime':e} for t in ticks for e in t['events'] if e['event'] in history]})
    (BASE/'标识符变异汇总.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'input_all_accepted':True,'warehouse_loss_vs_ports':[results[0]['warehouse_loss'],results[0]['successful_warehouse_port_moves']],
                      'golden_gate':results[0]['golden_gate'],'transport_collision':results[1]['execution_error'],'event_collisions':len(results[2]['collisions'])},ensure_ascii=False))


if __name__=='__main__':main()
