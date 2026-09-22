"""第7轮独立局部核验；仅输出JSON，不改任何被审产物。"""
import copy
import importlib.util
import itertools
import json
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh')


def load_revision_probe():
    source = ROOT / '求解器/规格/第6轮修订验证/核对修订回归.py'
    spec = importlib.util.spec_from_file_location('revision_probe', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_warehouse_sequence():
    module = load_revision_probe()
    warehouse = {
        key: {'item': None, 'quantity': 0, 'identity': None}
        for key in ['W0', 'W1']
    }
    order = ['W0', 'W1']
    first_status, first_state = module.transfer({'高容谷地电池': 1}, warehouse, order)
    assert first_status == 'success'
    second_status, second_state = module.transfer(
        {'精选荞愈胶囊': 1}, first_state['warehouse'], order)
    filtered_order = [key for key in order
                      if first_state['warehouse'][key]['quantity'] == 0
                      and first_state['warehouse'][key]['identity'] is None]
    projected_status, projected_state = module.transfer(
        {'精选荞愈胶囊': 1}, first_state['warehouse'], filtered_order)
    assert second_status == 'invalid'
    assert projected_status == 'success'
    # 两次调用代表两次冷却允许的时刻；本辅助函数不模拟时钟与外部进箱。
    return {
        'scope': '第6轮局部回归函数的连续消费；不是生产内核轨迹',
        'original_order': order,
        'initial_warehouse': warehouse,
        'first_status': first_status,
        'first_state': first_state,
        'second_status_with_unchanged_order': second_status,
        'second_state_with_unchanged_order': second_state,
        'current_empty_order': filtered_order,
        'second_status_with_explicit_projection': projected_status,
        'second_state_with_explicit_projection': projected_state,
        'question': '仲裁表属于固定母序还是当前空格投影；若后者，成功落格时需明写更新后效。',
    }


def close_ungraded(cursor, order):
    ready = True
    used = set()
    seen = {(cursor, ready, ())}
    successes = []
    boundaries = []
    for sweep in range(10):
        for edge in order:
            physical = ready and edge not in used
            source_permission = cursor == edge
            target_permission = physical
            if not (source_permission or target_permission):
                continue
            success = source_permission and target_permission
            if success:
                ready = False
                used.add(edge)
                successes.append(edge)
            if source_permission:
                cursor = (edge + 1) % 3
        key = (cursor, ready, tuple(sorted(used)))
        boundaries.append(key)
        if key in seen:
            return cursor, successes, boundaries
        seen.add(key)
    raise AssertionError('局部有限扫描没有闭包')


def check_ungraded_schedule():
    # 只检查无分级三路授权与完整环重复，外部按组供货和腾空另作边界前提。
    # 正式轮询均分的“同级”不能由这里的工程ungraded标签替代证明。
    rows = []
    for order in itertools.permutations(range(3)):
        cursor = 1
        successes = []
        for tick in range(6):
            cursor, emitted, _ = close_ungraded(cursor, order)
            successes.extend(emitted)
        rows.append({'template_order': order, 'successes': successes,
                     'cursor_after_six_groups': cursor})
    assert rows[0]['successes'] == [1, 0, 0, 0, 0, 0]
    return {
        'scope': '固定三路无分级轮询的局部扫描；不是完整可达布局或已证规则反例',
        'rows': rows,
        'disposition': '不列finding：未证明正式轮询均分的同级与无其他移动障碍前件适用。',
    }


def check_corner_geometry():
    # A东边与B南边仅有公共端点，两个单位占格不重叠。
    source_segment = [[11, 10], [11, 11]]
    target_segment = [[11, 11], [12, 11]]
    common_endpoints = sorted(set(map(tuple, source_segment))
                              & set(map(tuple, target_segment)))
    assert common_endpoints == [(11, 11)]
    return {
        'units': [{'id': 'A', 'cell': [10, 10], 'output': 'east'},
                  {'id': 'B', 'cell': [11, 11], 'input': 'south'}],
        'source_segment': source_segment,
        'target_segment': target_segment,
        'common_endpoints': common_endpoints,
        'shared_full_edge': False,
        'scope': '只证角点相交与共边重合是不同谓词，不宣称角接通已获全规则许可。',
    }


if __name__ == '__main__':
    print(json.dumps({'warehouse_sequence': check_warehouse_sequence(),
                      'ungraded_schedule': check_ungraded_schedule(),
                      'corner_geometry': check_corner_geometry()},
                     ensure_ascii=False, indent=2))
