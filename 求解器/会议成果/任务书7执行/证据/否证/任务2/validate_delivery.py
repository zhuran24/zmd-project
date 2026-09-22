#!/usr/bin/env python3
"""只写本席结构化结果与交付校验；正文是findings的单一来源。"""
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]
BASE=ROOT/'求解器/会议成果/任务书7执行'
DOC=BASE/'复核/否证-任务2.md'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    body=DOC.read_text()
    findings=[]; arguments=[]
    for match in re.finditer(r'^### (T2-\d+) ([^\n]+)\n(.*?)(?=^### |^## |\Z)',body,re.M|re.S):
        identifier,title,section=match.groups()
        finding={key:re.search(r'\*\*'+key+r'：\*\* ([^\n]+)',section).group(1)
                 for key in ('target','verdict','reason')}
        assert finding['verdict'] in {'否证成立','否证不成立','无法判定'}
        findings.append(finding)
        paragraph=section.split('**reason：** ',1)[1].split('\n\n',1)[1].strip()
        assert len(paragraph)>120
        arguments.append({'id':identifier,'title':title,'text':paragraph})
    assert [a['id'] for a in arguments]==[f'T2-{i:02}' for i in range(1,14)]
    counts={v:sum(f['verdict']==v for f in findings) for v in ('否证成立','否证不成立','无法判定')}
    assert counts=={'否证成立':0,'否证不成立':8,'无法判定':5}
    inputs=[]
    for manifest in ('输入指纹.json','补充来源指纹.json'):
        for entry in json.loads((HERE/manifest).read_text())['files']:
            p=Path(entry['path'])
            if not p.is_absolute():p=ROOT/p
            actual=sha(p); assert actual==entry['sha256'],str(p)
            inputs.append({'path':str(p),'sha256':actual,'same':True})
    old=BASE/'证据/复核推导/核算结果.json'
    assert json.loads(old.read_text())==json.loads((HERE/'derivation-arithmetic-0.json').read_text())
    runs=json.loads((HERE/'重跑日志.json').read_text())
    assert [r['exit_status'] for r in runs]==[1,0,0,0]
    assert 'source bytes changed' in runs[0]['stderr']
    owner_section=body.split('**for_owner（仅登记，未发送询问）：**',1)[1].split('## 4.',1)[0]
    owner=[re.sub(r'^\d+\. ','',line) for line in owner_section.splitlines() if re.match(r'^\d+\. ',line)]
    summary='任务2独立否证已完成：13项中否证成立0项、否证不成立8项、无法判定5项。仓库条件化非干扰、分物种收支及两个周期对应方向未被击穿；具体键覆盖、恢复安全、箱传输后效、规格版本接续和重锁历史生成链仍须补齐。原算术及21609组新增算术通过；原仓库脚本因5份规格指纹变化退出1，作为版本核验停止记录。未运行内核，L/U不变。'
    expected_files={str(p) for p in HERE.iterdir() if p.is_file()}
    expected_files.update(str(HERE/n) for n in ('结构化结果.json','交付校验.json','执行日志.json'))
    result={'status':'done','file':str(DOC),'findings':findings,'summary':summary,
        'arguments':arguments,'files':[str(DOC)]+sorted(expected_files),
        'for_owner':owner,'error':None,'counts':counts,'main_sha256':sha(DOC)}
    save('结构化结果.json',result)
    links=[]
    for p in (DOC,HERE/'README.md'):
        for dest in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in dest:continue
            target=(p.parent/dest.split('#')[0]).resolve()
            assert target.exists(),str(target)
            links.append({'from':str(p),'to':str(target)})
    assert all(p.suffix in {'.py','.json','.log','.md'} for p in HERE.iterdir() if p.is_file())
    for p in HERE.glob('*.json'):json.loads(p.read_text())
    artifacts=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
               for p in [DOC,*sorted(HERE.iterdir())] if p.is_file() and p.name not in {'交付校验.json','执行日志.json'}]
    check={'status':'pass','findings':len(findings),'counts':counts,
        'argument_extraction':'verbatim_from_main_document','original_source_checks':inputs,
        'local_links':links,'artifacts':artifacts,
        'excluded_from_hash_list':['交付校验.json (self-reference)','执行日志.json (wrapper writes after command)'],
        'derivation_result_identical':True,'actual_script_exit_codes':[1,0,0,0]}
    save('交付校验.json',check)
    print(json.dumps({'status':'pass','findings':len(findings),'counts':counts,
        'source_checks':len(inputs),'links':len(links),'files':len(result['files']),
        'main_sha256':sha(DOC)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
