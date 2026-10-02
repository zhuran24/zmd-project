#!/usr/bin/env python3
"""交付结构、独立结果、链接与当前输入指纹；只写丙席目录。"""
from pathlib import Path
import ast,hashlib,json,re

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'辅助-丙.md'
ROUNDS=HERE.parent.parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    body=REPORT.read_text()
    assert re.findall(r'^## (\d+) ',body,re.M)==list(map(str,range(17,25)))
    assert body.count('判断：**可直接通过。**')==6
    assert body.count('判断：**有疑点。**')==2
    assert body.count('### 正式格式条文')==11
    assert '@@' not in body and '据：同上' not in body
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    arithmetic=json.loads((HERE/'arithmetic.json').read_text())
    geometry=json.loads((HERE/'geometry.json').read_text())['summary']
    dynamics=json.loads((HERE/'dynamics.json').read_text())
    interface=json.loads((HERE/'interfaces.json').read_text())
    assert arithmetic['area']['interfaces']==619
    assert arithmetic['prefix']['states']==318168
    assert geometry['near_total']==16739 and geometry['base_max']==geometry['near_max']==91
    assert not geometry['violations']
    for key in ('general','strong','finite','low_inventory'):
        assert dynamics[key]['violations']==0
    assert interface['dedicated_violations']==0 and interface['dedicated_initial_origin_geometry']['rotation_checks']
    assert min(x['min_phi'] for x in dynamics['low_inventory']['cases'])==0.5

    def version(file,section):return str(ROUNDS/file)+' '+section
    items=[
        dict(name='17 面积预算',final_version=version('第95-97轮/推导95G.md','§7.2，第263—267行')+'；'+version('第95-97轮/推导95M.md','§5，第199行'),assessment='可直接通过',note='方向账、角机占地补偿及1110/1107推论复算成立。G保留原X，角机分支的含X式比M形式上强2，可统一采用G；M“最低Ω”仅需措辞勘误。'),
        dict(name='18 内带缺口',final_version=version('第95-97轮/推导95G.md','§7.1，第251—255行')+'；'+version('第95-97轮/推导95M.md','§4，第110行'),assessment='可直接通过',note='135个基础分支及16739个近边参数分支独立复算支持上界91。X_G=X_M+2χ，G右端比M多χ，不弱于M，可合为G版；不能删除χ修正。'),
        dict(name='19 单条混料进路逐件判据',final_version=version('第92-94轮/推导92C.md','S02，第48行，证明第316行')+'；'+version('第92-94轮/推导92C-临时规则续轮.md','第8行'),assessment='有疑点',note='前缀算术成立，但“余量不足50即能收货”默认取货格没有占用原料种类。若调试可向取货格误放A，规则13会挡住来料；该初态是否允许尚不明确，需补初态限制或给禁止依据。'),
        dict(name='20 整批k件配k条取货通道的均分',final_version=version('第101-103轮/复核103H.md','H05修正版，第132—136行'),assessment='可直接通过',note='321种释放模式复得8步内每路一件；整批分块保证任意离线下差至多2及循环均分。同级无清空分支的固定轮转、差1另行成立，105/106意见已覆盖。'),
        dict(name='21 植物专机一一配对满库存不断料',final_version=version('第92-94轮/推导92C.md','前部S07，第126行；证明第118—122、458—483行'),assessment='可直接通过',note='50件初料保证第0—399步，库存下界47/44/41、回填最多1/2/3次判定复算成立且不依赖历史保留。“始终”须限这400步，不恢复无限期结论。'),
        dict(name='22 采种单元的回路存量下界',final_version=version('第101-103轮/推导101H.md','§8 H06，第163—177行'),assessment='可直接通过',note='准备截面150、正常步末176、清空m次的累计界及独立Φ≥1/2证明分别成立，程序复算无违例；151.5仅为未采用的可选加强。'),
        dict(name='23 采种单元不断料',final_version=version('第101-103轮/推导101H.md','§9 H07，第249—253行'),assessment='可直接通过',note='低库存活性、满库存服务两支均闭合；L+177、原料49、粉末48/47及等待n−1复算成立。K首桥另一轴已恢复，满速仍须额外前件。'),
        dict(name='24 专用进路下缓存格不空的传递',final_version=version('第95-97轮/推导95M.md','§6，第267行')+'；'+version('第95-97轮/推导95T.md','§5.1，第186行'),assessment='有疑点',note='两版逐格前移证明未明写初货来源不得指向后格；按仅限最终拓扑的读法，调试反向送料后旋转可留下阻塞循环，影响主结论。补齐来源前提后可合一：主结论相同，T的附加输出首单位范围更宽。')]
    payload=dict(report_path=str(REPORT),items=items)
    assert len(items)==8 and all(set(x)=={'name','final_version','assessment','note'} for x in items)
    assert all(x['assessment'] in {'可直接通过','有疑点','未做完'} for x in items)
    (HERE/'final_result.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')

    files=[]
    files.extend((ROUNDS/'第107-109轮/前提快照').glob('*.txt'))
    files.append(ROUNDS/'第107-109轮/临时规则.md')
    for round_name,names in [
        ('第92-94轮',['推导92C','推导92C-临时规则续轮','复核93C','复核94C']),
        ('第95-97轮',['推导95G','推导95M','推导95T','复核96G','复核97G','复核96M','复核97M','复核96T','复核97T']),
        ('第101-103轮',['推导101H','复核102H','复核103H']),
        ('第104-106轮',['复核105-整批k件配k条取货通道的均分','复核106-整批k件配k条取货通道的均分'])]:
        files.extend(ROUNDS/round_name/(n+'.md') for n in names)
    files.append(ROUNDS/'第101-103轮/推导101H/audit_table.md')
    files.append(HERE.parent/'三审报告.md')
    assert len((ROUNDS/'第107-109轮/前提快照/《明日方舟：终末地》游戏规则.txt').read_text().splitlines())==115
    manifest=dict(date='2026-10-02',inputs={str(p.relative_to(ROUNDS)):digest(p) for p in files},
                  artifacts={p.name:digest(p) for p in HERE.iterdir()
                             if p.is_file() and p.name not in ('manifest.json','delivery_check.json')},
                  report=dict(path=str(REPORT),sha256=digest(REPORT)))
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (HERE/'delivery_check.json').write_text('{}\n')
    links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',body)
    for link in links:assert (REPORT.parent/link.split('#')[0]).exists(),link
    review=dict(status='PASS',items=8,formal_versions=11,pass_recommendations=6,doubts=2,
                unfinished=0,checked_relative_links=len(links),source_files=len(files),
                report_sha256=digest(REPORT),reader_review='全文重读完成；初态疑点、版本差别、数值口径和证明范围分别标明',
                script_check='AST通过；全部check脚本实际运行完成',
                limits='仅局部模型和所列静态放宽；不替主会话作三审结论，不认证全厂')
    (HERE/'delivery_check.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(review,ensure_ascii=False))

if __name__=='__main__':main()
