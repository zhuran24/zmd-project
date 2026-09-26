#!/usr/bin/env python3
"""目录回源的负例：错误必须触发，不把重新抄写指纹当成修复。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from formal_catalog import ROOT, SOURCE_NAMES, formal_projection, parse_constraints, source_snapshot, verify


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*path, key))
    elif isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from leaves(child, (*path, index))
    else:
        yield path, value


def mutate(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


class FormalCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT/'数据/正式静态目录.json').read_text())

    def test_basis_and_section_are_normative(self):
        original = next(s for s in self.catalog['sources'] if s['path']=='求解约束.txt')
        text = '\n'.join(original['lines'])
        for changed in [text.replace('据：蓝图、离线','据：蓝图'), text.replace('目标须对其每种取值都达成','目标只须对一种取值达成')]:
            self.assertNotEqual(parse_constraints(changed), self.catalog['constraints'])

    def test_any_source_byte_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='kernel-formal-catalog-', dir='/tmp') as name:
            repo = Path(name)
            for source in self.catalog['sources']:
                (repo/source['path']).write_bytes((ROOT.parent/source['path']).read_bytes())
            verify(self.catalog,repo)
            for filename in SOURCE_NAMES:
                p = repo/filename
                original = p.read_bytes()
                p.write_bytes(original+b'\n')
                with self.assertRaises(AssertionError):
                    verify(self.catalog,repo)
                p.write_bytes(original)

    def test_threshold_target_and_unit_domains_cannot_drift(self):
        for key in ['threshold','target','gate','cooldown','bridge']:
            c = copy.deepcopy(self.catalog)
            units = {u['id']:u for u in c['units']}
            if key == 'threshold': c['static_checks']['constants']['transport_s']['quantity']['value']='1'
            elif key == 'target': c['task']['targets']['精选荞愈胶囊']['value']='3/5'
            elif key == 'gate': units['物品准入口']['settings']['total_limit']['max']['value']='5001'
            elif key == 'cooldown': units['协议储存箱']['transfer']['cooldown_ticks']['value']='4'
            else: units['桥接器']['inventory_rules']['same_item_across_slots']='at_most_one_slot'
            with self.assertRaises(AssertionError,msg=key): verify(c)

    def test_live_catalog_passes(self):
        verify(self.catalog)

    def test_projection_succeeds_without_plant_trigger(self):
        snapshot = source_snapshot()
        mineral_rule = next(r for r in parse_constraints('\n'.join(snapshot[2]['lines']))
                            if r['name'] == '矿系不入库')
        self.assertNotIn('种植机', mineral_rule['text'])
        projection = formal_projection(snapshot)
        self.assertNotIn('plant_trigger', projection['static_checks']['constants'])
        self.assertEqual(len(projection['constraints']), 77)
        self.assertEqual(projection['static_checks'], self.catalog['static_checks'])
        verify(self.catalog)

    def test_stale_plant_trigger_constant_is_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed['static_checks']['constants']['plant_trigger'] = {
            'quantity': {'value': '32', 'category': '条文直引'},
            'basis': '求解约束·矿系不入库', 'source_excerpt': '种植机恰 32 台',
        }
        with self.assertRaisesRegex(AssertionError, r'static_checks.constants'):
            verify(changed)

    def test_every_unit_and_recipe_leaf_is_guarded(self):
        counts = {}
        for section in ['units', 'recipes']:
            count = 0
            for path, old in leaves(self.catalog[section], (section,)):
                # 类别换成另一个合法类别，不能靠“枚举非法”误报挡住。
                if path[-1] == 'category':
                    replacement = '候选' if old != '候选' else '条文直引'
                elif path[-1] == 'value':
                    replacement = str(int(old) + 1)
                elif isinstance(old, bool):
                    replacement = not old
                elif isinstance(old, str):
                    replacement = old + '变异'
                elif old is None:
                    replacement = {'value': '0', 'category': '条文直引'}
                else:
                    replacement = ['unexpected']
                with self.subTest(path=path):
                    changed = copy.deepcopy(self.catalog)
                    mutate(changed, path, replacement)
                    with self.assertRaises(AssertionError):
                        verify(changed)
                count += 1
            counts[section] = count
        print('逐叶变异全部拒绝：' + json.dumps(counts, ensure_ascii=False))

    def test_collections_and_unknown_fields_are_guarded(self):
        for section in ['units', 'recipes']:
            for operation in ['missing', 'duplicate', 'extra_field', 'missing_field', 'extra_entry']:
                with self.subTest(section=section, operation=operation):
                    changed = copy.deepcopy(self.catalog)
                    rows = changed[section]
                    if operation == 'missing':
                        rows.pop()
                    elif operation == 'duplicate':
                        rows.append(copy.deepcopy(rows[0]))
                    elif operation == 'extra_field':
                        rows[0]['unexpected'] = '未知字段'
                    elif operation == 'missing_field':
                        del rows[0]['kind' if section == 'recipes' else 'ports']
                    else:
                        extra = copy.deepcopy(rows[0])
                        extra['id'] = '未知条目'
                        rows.append(extra)
                    with self.assertRaises(AssertionError):
                        verify(changed)


if __name__ == '__main__':
    unittest.main()
