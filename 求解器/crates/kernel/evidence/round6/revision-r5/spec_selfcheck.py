"""只读执行S线嵌入的现行schema生成比对与结构回归。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
path = ROOT / '规格/对内核的修改请求.md'
code = path.read_text().split('<!-- round6-schema-tool -->\n```python\n', 1)[1].split('\n```', 1)[0]
sys.argv = [str(path), '--check']
exec(compile(code, str(path) + ':round6-schema-tool', 'exec'), {'__file__': str(path), '__name__': '__main__'})
