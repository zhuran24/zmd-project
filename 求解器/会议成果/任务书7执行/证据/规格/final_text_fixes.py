from pathlib import Path
import json,difflib,hashlib
R=Path('/home/zhuran24/zmd-research-fresh/求解器'); E=R/'会议成果/任务书7执行/证据/规格'; edits=[]
for name in ['内核输入.md','选择点参数轴.md','内核输出.md','四件前置义务对照.md']:
 p=R/'规格'/name; old=p.read_text(); new=old.replace('旧正式循环对应名目撤下','旧“级二”名目撤下').replace('生产部分生产部分周期','生产部分周期')
 if name=='内核输出.md':
  new=new.replace('各处置数量按当前内核配置统计，旧55本版选值、18停止轴、11已定属于2026-09-20史料；','当前配置共99轴：18项已定、47项本版选值、19项工程停止、15项输入量化；')
 if name=='内核输入.md':new=new.replace('T12；T12；open','T12；open')
 if new!=old:
  p.write_text(new); edits.append({'path':str(p),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'diff':list(difflib.unified_diff(old.splitlines(),new.splitlines(),lineterm='',n=1))})
(E/'reader-fixes.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('reader fixes',len(edits))
