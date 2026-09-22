"""当前覆盖表逐行回源、9条发现及输入接口辖域自查。"""
import json
import re
from pathlib import Path

BASE=Path(__file__).resolve().parent
SOLVER=BASE.parents[1]
ROOT=SOLVER.parent


def main():
    results=[]
    for table in (SOLVER/'规格/规则覆盖表.md',SOLVER/'数据/规则覆盖表.md'):
        sections=table.read_text().split('## ')
        for index,name in ((1,'《明日方舟：终末地》游戏规则.txt'),(2,'求解任务.txt')):
            rows=[line.split('|')[1:-1] for line in sections[index].splitlines() if re.match(r'^\| \d+ \|',line)]
            source=(ROOT/name).read_text().splitlines()
            assert len(rows)==len(source)
            for number,(row,line) in enumerate(zip(rows,source),1):
                assert int(row[0])==number and row[1].strip()==(line.strip() or '（空行）')
                assert all(cell.strip() for cell in row[2:])
            results.append({'table':str(table),'source':name,'lines':len(rows),'status':'逐行通过'})
    source=[(i,line.split('：',1)[0]) for i,line in enumerate((ROOT/'求解约束.txt').read_text().splitlines(),1)
            if '：' in line and not line.startswith(' ') and not line.endswith('：')]
    rows=[line.split('|')[1:-1] for line in (SOLVER/'规格/规则覆盖表.md').read_text().split('## ')[3].splitlines()
          if re.match(r'^\| \d+ \|',line)]
    assert len(rows)==len(source)==56
    for number,(row,(line,name)) in enumerate(zip(rows,source),1):
        assert int(row[0])==number and int(row[1])==line and row[2].strip()=='约束·'+name
    results.append({'table':'规格/规则覆盖表.md','clauses':56,'status':'约束名及源行通过'})
    catalog=json.loads((SOLVER/'数据/正式静态目录.json').read_text())
    contract_rows=[line.split('|')[1:-1] for line in (SOLVER/'数据/规则覆盖表.md').read_text().split('## ')[3].splitlines() if '`constraints[' in line]
    assert len(contract_rows)==len(catalog['constraints'])==56
    for index,(row,rule) in enumerate(zip(contract_rows,catalog['constraints'])):
        assert row[0].strip()==rule['name'] and f'`constraints[{index}]`' in row[2]
    results.append({'table':'数据/规则覆盖表.md','clauses':56,'status':'目录条目映射通过'})
    body=(SOLVER/'规格/内核输入.md').read_text()
    axis_pattern=r'^\| `([a-z_]+\.[a-z_]+)` \|'
    axes=re.findall(axis_pattern,(SOLVER/'规格/选择点参数轴.md').read_text().split('## 2.')[1].split('## 3.')[0],re.M)
    inputs=re.findall(axis_pattern,body.split('## 5. ')[1].split('### 5.1')[0],re.M)
    assert len(axes)==len(inputs)==99 and set(axes)==set(inputs)
    ids={f'K3-r3-L{seat}-{index:02}' for seat,count in ((1,2),(2,3),(3,4)) for index in range(1,count+1)}
    logged=re.findall(r'^\| (K3-r3-L\d-\d+) \|',(SOLVER/'规格/内核输入-修订记录.md').read_text(),re.M)
    assert len(logged)==len(ids)==9 and set(logged)==ids
    for phrase in ('当前版本只支持逐时刻有限历史','无限或符号函数需另增函数编码',
                   'phase=before_boundary/after_closure','更一般中途恢复还需已审阶段去重状态'):
        assert phrase not in body,phrase
    for phrase in ('event-order-v2','slot_width','in_boundary','in_closure','seen_boundaries','无身份空格集合从当前 warehouse'):
        assert phrase in body,phrase
    output=(SOLVER/'规格/内核输出.md').read_text()
    assert 'kernel-output-v1' not in output and all(s in output for s in ('coverage_status','parameter_projection','完整重算'))
    results.append({'axis_count':99,'findings':9,'status':'全集、修订记录及已定位旧句检查通过'})
    docs=[SOLVER/'规格'/name for name in ('内核输入.md','内核输出.md','内核输入-修订记录.md','内核输入-对参数轴的修改请求.md')]
    docs += [BASE/'存活发现处理.md',BASE/'自查报告.md']
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            assert (doc.parent/target.split('#')[0]).exists(),(doc,target)
    result={'status':'通过','checks':results,'scope':'逐行覆盖/引用与已定位旧句，不是语义穷尽证明；共享§6请求已有第6轮答复，本检查不替代语义穷尽证明'}
    (BASE/'规则覆盖自查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
