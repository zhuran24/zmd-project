# 完整性批评席自写的篡改负例：落盘记录改一处，验收必须拒收。
import json, sys, copy
from pathlib import Path
ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
sys.path.insert(0, str(ROOT/'crates/kernel/tests'))
sys.path.insert(0, str(ROOT/'数据/样例'))
import verify_outputs as V
import check_examples as checker
from check_golden_trace import run

name='分流器三路轮询'
data=checker.load_json(ROOT/f'数据/样例/{name}.json')
expected=run(data)
src=ROOT/f'数据/样例/{name}-运行记录-kernel.json'
base=json.loads(src.read_text())
tmp=Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/crit/tampered.json')
tmp.parent.mkdir(parents=True,exist_ok=True)

def attempt(label, mutate):
    r=copy.deepcopy(base); mutate(r)
    tmp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    try:
        V.verify(tmp, data, expected); print(f'{label}: 未被拒收  <<< 问题')
    except Exception as e:
        print(f'{label}: 拒收 ({type(e).__name__}: {str(e)[:70]})')

attempt('1 事件结局 failure->no_request', lambda r: r['trace']['ticks'][3]['events'][5].__setitem__('outcome','no_request'))
attempt('2 覆盖轴冒报 exercised', lambda r: [a.update({'coverage_status':'exercised','evidence':['J|999|0|999']}) for a in r['uncovered_axes'] if a['axis']=='transfer.judgment'])
attempt('3 摘要 warehouse_ore 少一件', lambda r: r['trace']['ticks'][11]['summary'].__setitem__('warehouse_ore','79900'))
attempt('4 闭包轮数 +1', lambda r: r['trace']['ticks'][2]['closure'].__setitem__('scan_rounds', r['trace']['ticks'][2]['closure']['scan_rounds']+1))
attempt('5 指纹表删一项', lambda r: r['fingerprints'].pop())
attempt('6 端口预算多记一件', lambda r: r['trace']['ticks'][4]['state']['semantic_context']['tick_context']['value']['port_usage'][0]['quantity'].__setitem__('value','2'))
attempt('7 未改动（对照）', lambda r: None)
