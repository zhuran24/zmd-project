#!/usr/bin/env python3
"""目录回源的负例：错误必须触发，不把重新抄写指纹当成修复。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from formal_catalog import ROOT, SOURCE_NAMES, parse_constraints, verify


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
        directory = ROOT/'数据/修订验证/r3'
        with tempfile.TemporaryDirectory(dir=directory) as name:
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
            else: units['桥接器']['inventory_rules']['same_item_across_slots']='exempt'
            with self.assertRaises(AssertionError,msg=key): verify(c)


if __name__ == '__main__':
    unittest.main()
