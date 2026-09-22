#!/usr/bin/env python3
"""只改测试输出目的地，复跑原转换器与原 Python 负例。"""
import ast
import hashlib
import json
import runpy
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TOOLS = ROOT / '求解器/数据/工具'
sys.path.insert(0, str(TOOLS))


class OutputDirectory(ast.NodeTransformer):
    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == 'OUT' for t in node.targets):
            node.value = ast.Call(func=ast.Name(id='Path', ctx=ast.Load()), args=[ast.Constant(value=str(OUT / '转换复现'))], keywords=[])
        return node


target = OUT / '转换复现'
target.mkdir(exist_ok=True)
script = TOOLS / 'convert_candidate_b.py'
tree = ast.fix_missing_locations(OutputDirectory().visit(ast.parse(script.read_text())))
exec(compile(tree, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__'})
results = {}
for name in ['contract.json', '来源清单.json']:
    actual = (target / name).read_bytes()
    expected = (ROOT / '求解器/数据/候选B' / name).read_bytes()
    assert actual == expected, name
    results[name] = {'byte_identical': True, 'sha256': hashlib.sha256(actual).hexdigest()}
(OUT / '转换复现结果.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False))

# 原负例写临时正式文件副本；将其临时目录强制收在本席可写范围。
original = tempfile.TemporaryDirectory
def review_temp(*args, **kwargs):
    kwargs['dir'] = str(OUT)
    return original(*args, **kwargs)

sys.argv = [str(TOOLS / 'test_formal_catalog.py'), '-v']
with patch.object(tempfile, 'TemporaryDirectory', review_temp):
    runpy.run_path(str(TOOLS / 'test_formal_catalog.py'), run_name='__main__')
