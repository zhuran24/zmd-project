"""受限转移§3的分组、起轮、级仲裁及事务级成员迁移。"""
import copy
from fractions import Fraction
import check_examples as checker


def connection_times(data):
    events={e['id']:e for e in data['timeline']['events']}
    return {c['channel']:Fraction(events[c['event']]['time']['value']['value'])
            for c in data['timeline']['connection_events'] if c['action']=='open'}


def build_sides(data, kinds, units, ports, channels, old=None):
    params={a:d for g in ('fixed','offline_mutable','fixedness_unproven') for a,d in data['parameters'][g].items()}
    tie=params['connection.tie']['value']['channels']
    times=connection_times(data)
    old={(s['unit'],s['side'],s.get('axis')):s for s in old['sides']} if old else {}
    result=[]
    for uid,unit in units.items():
        if unit['kind']=='供电桩':continue
        for axis in (["vertical", "horizontal"] if unit["kind"]=="桥接器" else [None]):
            for side,key,peer in [('input','target_port','source_port'),('output','source_port','target_port')]:
                graded=side=='input' or kinds[unit['kind']]['family']!='transport'
                groups={}
                for c in channels:
                    if ports[c[key]]['unit']!=uid or ports[c[key]]['axis']!=axis:continue
                    direct=graded and units[ports[c[peer]]['unit']]['kind']==('分流器' if side=='input' else '汇流器')
                    category='direct:'+c['id'] if direct else ('other' if graded else 'ungraded')
                    groups.setdefault('L|'+uid+('|' + axis if axis else '')+'|'+side+'|'+category,[]).append(c['id'])
                previous={l['id']:l for l in old.get((uid,side,axis),{}).get('levels',[])}
                levels=[]
                for lid,members in sorted(groups.items()):
                    members.sort(key=lambda cid:(times[cid],tie.index(cid)))
                    special=(unit['kind']=='分流器' and side=='output') or (unit['kind']=='汇流器' and side=='input')
                    cursor=members[1] if special and len(members)>=2 else members[0]
                    if lid in previous:
                        p=previous[lid]; prior=p['members']; start=prior.index(p['next_channel'])
                        # 存活位置优先；原位被删则沿旧环找首个存活成员。
                        survivors=[c for c in prior[start:]+prior[:start] if c in members]
                        if survivors:cursor=survivors[0]
                    levels.append({'id':lid,'members':members,'next_channel':cursor})
                result.append({**({'axis':axis} if axis else {}),'unit':uid,'side':side,'graded':graded,'current_level':None,'levels':levels})
    return {'schema':'poll-memory-v1','sides':result}


def refresh_sides(data, sides, movable, level_order):
    """仅在正式级键全等时读取输入级序；返回实际遇到的多可动级平局。"""
    times=connection_times(data); ties=[]
    for s in sides:
        eligible=[l for l in s['levels'] if not s['graded'] or any(movable(c) for c in l['members'])]
        if not eligible:s['current_level']=None;continue
        if not s['graded']:
            checker.require(len(eligible)==1,'运输取货侧须为唯一不分级环')
            s['current_level']=eligible[0]['id'];continue
        # 当前参考域仅在存货侧有多个级；非运输多级取货要实现阻尼再接入。
        checker.require(s['side']=='input' or len(s['levels'])<=1,'unsupported: 多级取货缺阻尼求值')
        keys={l['id']:min(times[c] for c in l['members']) for l in eligible}
        best=min(keys.values()); candidates=[l for l in eligible if keys[l['id']]==best]
        if len(candidates)>1:
            checker.require(all(l['id'] in level_order for l in candidates),'级平局缺显式仲裁')
            ties.append(s['unit']+':'+s['side']+(':'+s['axis'] if s.get('axis') else ''))
        s['current_level']=min(candidates,key=lambda l:level_order.index(l['id']))['id']
    return ties
