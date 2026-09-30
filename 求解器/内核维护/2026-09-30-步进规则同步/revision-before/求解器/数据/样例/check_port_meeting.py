"""两种端口相遇谓词的实例级比较；不把待审读法许可为游戏行为。"""
import json
from pathlib import Path
import check_examples as checker


def segment(port):
    x, y = port['cell']
    dx, dy = port['normal']
    if dx:
        return (x + (dx > 0), y), (x + (dx > 0), y + 1)
    return (x, y + (dy > 0)), (x + 1, y + (dy > 0))


def compare_meeting(data, catalog):
    _, _, ports, channels, _, _ = checker.geometry(data, catalog)
    shared = sorted(c['id'] for c in channels)
    closed = []
    for source, a in ports.items():
        if a['role'] != 'output':
            continue
        for target, b in ports.items():
            if b['role'] != 'input' or a['unit'] == b['unit'] or 'transport' not in (a['family'], b['family']):
                continue
            # 不强加相反法向；直接核轴表“闭边段非空交集”的较广谓词。
            sa, sb = segment(a), segment(b)
            if all(max(sa[0][i], sb[0][i]) <= min(sa[1][i], sb[1][i]) for i in (0, 1)):
                closed.append(f'PC|{source}|{target}')
    closed.sort()
    opposite = [cid for cid in closed if ports[cid.split('|')[1]]['normal'] == tuple(-v for v in ports[cid.split('|')[2]]['normal'])]
    checker.require(set(shared) <= set(closed), '闭线段谓词应包含共边相向谓词')
    extras = sorted(set(closed) - set(shared))
    return {'shared_edge_opposite': shared, 'closed_segment_touch': closed,
            'closed_touch_with_opposite_normals': opposite,
            'same_pc_set': shared == closed, 'corner_pairs': extras,
            'status': '两读法下PC集合相同' if not extras else '两读法下PC集合不同，不能登记为共同轨迹',
            'scope': '谓词算术比较；closed_segment_touch仍待全规则审查'}


def main():
    base = Path(__file__).resolve().parent
    catalog = checker.load_json(base.parent / '正式静态目录.json')
    report = {name: compare_meeting(checker.load_json(base / name), catalog) for name in checker.NAMES}
    target = base.parents[1] / '规格/第四轮前置验证/端口相遇比较.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({name: {'same_pc_set': row['same_pc_set'], 'counts': [len(row['shared_edge_opposite']), len(row['closed_segment_touch'])]} for name, row in report.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
