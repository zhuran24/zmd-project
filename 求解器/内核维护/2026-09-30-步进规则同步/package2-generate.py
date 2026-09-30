from guard import ROOT,guard,save,digest
from work import write,json_text
import sys
sys.path.insert(0,str(ROOT/'数据/工具'))
from step_samples import generate_all,SOURCES

label=sys.argv[1]
guard(label+'-before')
try:
    rows=generate_all()
    for path,data in rows.items():write(str(path.relative_to(ROOT)),json_text(data))
    save('package2-samples.json',{'sources':{p:digest(ROOT.parent/p) for p in SOURCES},'inputs':{str(p.relative_to(ROOT)):digest(p) for p in rows}})
    print('generated',len(rows),'inputs')
finally:guard(label+'-after')
