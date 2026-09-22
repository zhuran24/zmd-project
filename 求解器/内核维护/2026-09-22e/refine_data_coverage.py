from pathlib import Path
import json,re,subprocess
R=Path(__file__).resolve().parents[2]
p=R/'数据/规则覆盖表.md'
old=subprocess.check_output(['git','show','HEAD:求解器/数据/规则覆盖表.md'],cwd=R).decode().split('## ')
new=p.read_text().split('## ');cat=json.loads((R/'数据/正式静态目录.json').read_text())
for i,source in enumerate(cat['sources'][:2],1):
 previous=[line.split('|')[1:-1] for line in old[i].splitlines() if re.match(r'^\| \d+ \|',line)]
 by_name={row[1].strip().split('：',1)[0]:row[2].strip() for row in previous}
 rows=[]
 for n,line in enumerate(source['lines'],1):
  content=line.strip() or '（空行）';dest=by_name.get(content.split('：',1)[0],f'`sources[{i-1}].lines[{n-1}]` 完整转录；task.conditions；实际拿取行为由规格承接，尚无运行证书')
  dest=re.sub(r'sources\[\d+\]\.lines\[\d+\]',f'sources[{i-1}].lines[{n-1}]',dest)
  rows.append(f'| {n} | {content} | {dest} |')
 lines=new[i].splitlines();ix=[j for j,l in enumerate(lines) if re.match(r'^\| \d+ \|',l)]
 new[i]='\n'.join(lines[:ix[0]]+rows+lines[ix[-1]+1:])+'\n'
p.write_text('## '.join(new))
print('preserved existing per-rule destinations while updating text/line indices')
