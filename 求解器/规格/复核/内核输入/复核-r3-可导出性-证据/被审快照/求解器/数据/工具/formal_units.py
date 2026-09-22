"""从正式条文重建单位投影；只作核对预期，不写回共享目录。"""
import re


def unit_projection(rule_text, constraints, quantity):
    # 数值取自条文，坐标及字段名为 static-catalog-v2 的编码约定。
    clauses = {}
    for line in rule_text.splitlines():
        if '：' in line:
            name, body = line.strip().split('：', 1)
            clauses[name] = body
    rules = {r['name']: r['text'] for r in constraints}

    def numbers(pattern, text):
        match = re.search(pattern, text)
        if match is None:
            raise AssertionError(f'正式单位条文无法解析：{pattern}；{text}')
        return tuple(int(value) for value in match.groups())

    def edge(side, role, positions, axis=None):
        return {'side': side, 'positions': [quantity(p, '算术推论') for p in positions],
                'role': role, 'axis': axis}

    def opposed(width):
        return [[edge('south', 'input', range(width)), edge('north', 'output', range(width))]]

    def slot(role, count, capacity, **extra):
        return {'role': role, 'count': None if count is None else quantity(count),
                'capacity': None if capacity is None else quantity(capacity), **extra}

    def unit(name, family, size_text, counts, layouts, inventory, functions, basis,
             port_category='条文直引', **extra):
        width, height = numbers(r'(\d+)x(\d+)', size_text)
        return {'id': name, 'name': name, 'family': family,
                'dimensions': {'width': quantity(width), 'height': quantity(height)},
                'area': quantity(width * height, '算术推论'),
                'ports': {'input_count': quantity(counts[0], port_category),
                          'output_count': quantity(counts[1], port_category), 'layouts': layouts},
                'inventory': inventory, 'power_required': bool(functions),
                'powered_functions': functions, 'basis': basis,
                'inventory_rules': {
                    'same_item_across_slots': 'exempt' if name == '协议储存箱' else 'at_most_one_slot',
                    'excluded_roles': ['buffer'], 'basis': '游戏规则·物品格',
                    'scope': '单位内物品格；缓存格例外。仅在存在物品格时适用。'},
                'switches': [{'function': f, 'settable': True, 'basis': '游戏规则·开关、设定'} for f in functions],
                **extra}

    # 据：规则 L17、L18、L44–57；约束“机型下限”“通道下限”。
    capacity, = numbers(r'放置上限 (\d+)', clauses['存货/取货物品格'])
    if '每个制造单位只有一个' not in clauses['缓存格']:
        raise AssertionError('缓存格单格前提变化，须审查投影')
    channel_parts = rules['通道下限'].split('；')
    units = {}
    for match in re.finditer(r'^    ([小中大]制造单位)：([^\n]+)\n((?:    [^\n：]+\n)+)', rule_text, re.M):
        group, body, members = match.groups()
        width, _ = numbers(r'大小(\d+)x(\d+)', body)
        inputs, outputs = numbers(r'(\d+) 个存货物品格、(\d+) 个取货物品格', body)
        for name in members.split():
            lower = {'basis': ['机型下限', '通道下限']}
            for field, text, pattern in [
                ('machines', rules['机型下限'], re.escape(name) + r' ≥(\d+)'),
                ('input_channels', channel_parts[0], re.escape(name) + r' (\d+)'),
                ('output_channels', channel_parts[1], re.escape(name) + r' (\d+)')]:
                value, = numbers(pattern, text)
                lower[field] = quantity(value)
            inventory = [
                slot('input', inputs, capacity, capacity_scope='unresolved', item_policy='unresolved',
                     note='不限制物品种类已定；单格混装、容量计数域及大机选格由规格参数轴处理；单位内同种跨格唯一仍适用（缓存除外）。'),
                slot('output', outputs, capacity, item_policy='single_item'),
                slot('buffer', 1, None, capacity_status='unlimited', item_policy='unlimited_kinds')]
            units[name] = unit(name, 'manufacturing', body, (width, width), opposed(width), inventory,
                               ['manufacture'], [group, '存货/取货物品格', '缓存格', '制造'],
                               port_category='算术推论', static_lower_bounds=lower)

    # 据：规则 L41；条文的一起点格位减一，换成目录零起点坐标。
    body = clauses['协议核心']
    ins, outs = numbers(r'（共 (\d+) 个）.*（共 (\d+) 个）', body)
    capacity, = numbers(r'每格上限 (\d+)', body)
    first, last = numbers(r'第 (\d+)-(\d+) 格', body)
    output_positions = numbers(r'第 (\d+)、(\d+)、(\d+) 格', body)
    core_layout = [edge(side, 'input', range(first - 1, last)) for side in ['south', 'north']]
    core_layout += [edge(side, 'output', [p - 1 for p in output_positions]) for side in ['west', 'east']]
    units['协议核心'] = unit('协议核心', 'core', body, (ins, outs), [core_layout],
        [slot('warehouse', None, capacity, count_status='unlimited', item_policy='single_item', shared_with='仓库取货口')],
        [], ['协议核心', '仓库', '物品格'])

    # 据：规则 L59–68；中文“一”“三”“两对”按条文结构编码，不从被测目录取值。
    capacity, = numbers(r'上限(\d+)', clauses['运输单位'])
    if '一个物品格' not in clauses['运输单位']:
        raise AssertionError('运输单位格数前提变化，须审查投影')
    layouts = {
        '传送带': [[edge('south', 'input', [0]), edge(side, 'output', [0])] for side in ['north', 'east', 'west']],
        '桥接器': [[edge(a, 'input', [0], 'vertical'), edge(b, 'output', [0], 'vertical'),
                    edge(c, 'input', [0], 'horizontal'), edge(d, 'output', [0], 'horizontal')]
                   for a, b in [('south', 'north'), ('north', 'south')]
                   for c, d in [('west', 'east'), ('east', 'west')]],
        '物品准入口': opposed(1),
        '分流器': [[edge('south', 'input', [0])] + [edge(s, 'output', [0]) for s in ['north', 'east', 'west']]],
        '汇流器': [[edge(s, 'input', [0]) for s in ['south', 'east', 'west']] + [edge('north', 'output', [0])]],
    }
    for name, counts in [('传送带', (1, 1)), ('桥接器', (2, 2)), ('物品准入口', (1, 1)),
                          ('分流器', (1, 3)), ('汇流器', (3, 1))]:
        inventory = [slot('transport', 1, capacity, item_policy='single_item')]
        extra = {}
        if name == '桥接器':
            inventory = [slot(axis, 1, None, capacity_status='unresolved', item_policy='single_item')
                         for axis in ['vertical', 'horizontal']]
            extra = {'port_assignment': 'first_connected_peer',
                     'notes': '两对端口各自拥有物品格，但同种物品在单位内只能占一个物品格，不能把两轴有格读成同种跨格豁免。容量例外的辖域未定；端口类型由先接端决定；轮询及分级按单位。'}
        if name == '物品准入口':
            body = clauses[name]
            low, high, window, window_low, window_high = numbers(
                r'累计收下上限（(\d+)-(\d+)）和每 (\d+) tick 的收下上限（(\d+)-(\d+)）', body)
            extra['settings'] = {
                'allowed_item': {'optional': True, 'domain': '单一物品身份', 'basis': '游戏规则·物品准入口'},
                'total_limit': {'optional': True, 'min': quantity(low), 'max': quantity(high), 'requires': 'allowed_item'},
                'window_limit': {'optional': True, 'min': quantity(window_low), 'max': quantity(window_high), 'requires': 'allowed_item'},
                'window_ticks': quantity(window), 'window_start': '收下第一件起算；走完后由下一件重新起算',
                'blocking': '身份不符或任一上限用尽，断开存货端口通道', 'basis': '游戏规则·物品准入口',
                'unresolved': '阻断恢复、设定变更时计数重置等见规格 T8'}
        units[name] = unit(name, 'transport', clauses[name], counts, layouts[name], inventory, [],
                           ['运输单位', name, '物品格'],
                           port_category='算术推论' if name == '桥接器' else '条文直引', **extra)

    # 据：规则 L36、L72；冷却粒度保留未定，不用容量字段填默认值。
    body = clauses['协议储存箱']
    width, _ = numbers(r'大小(\d+)x(\d+)', body)
    count, capacity = numbers(r'(\d+) 个有编号的物品格（上限 (\d+)）', body)
    cooldown, = numbers(r'(\d+) tick 冷却', clauses['传输'])
    units['协议储存箱'] = unit('协议储存箱', 'storage', body, (width, width), opposed(width),
        [slot('storage', count, capacity, item_policy='single_item_per_slot', numbered=True)],
        ['transfer'], ['协议储存箱', '传输'], port_category='算术推论',
        transfer={'cooldown_ticks': quantity(cooldown), 'switch_settable': True, 'judgment_scope': 'unit',
                  'cooldown_scope': 'unresolved', 'basis': '游戏规则·传输、判定、开关、设定',
                  'note': '全箱一次判定已定；冷却按箱还是按格仍未定，见 T6。'})
    body = clauses['仓库取货口']
    width, _ = numbers(r'大小(\d+)x(\d+)', body)
    units['仓库取货口'] = unit('仓库取货口', 'storage', body, (0, 1),
        [[edge('north', 'output', [(width - 1) // 2])]], [], [], ['仓库取货口'],
        warehouse_reference='取货端口引用协议核心仓库格，不新增本地物品格；south长边贴边界，north朝内')
    body = clauses['供电桩']
    width, height = numbers(r'以自己中心为原点(\d+)x(\d+)', body)
    units['供电桩'] = unit('供电桩', 'power', body, (0, 0), [[]], [], [], ['供电桩', '端口'],
        coverage={'width': quantity(width), 'height': quantity(height), 'origin': 'unit_center',
                  'cell_set_status': 'unresolved', 'note': '覆盖格集合与边界解释由规格参数轴给出'})
    return units
