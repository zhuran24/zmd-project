#!/usr/bin/env python3
import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
v=Path(__file__).resolve().parent
sys.path.insert(0,str(v.parents[2]/'数据/工具'))
import test_formal_catalog
original=tempfile.TemporaryDirectory
def isolated_temp(*args, **kwargs):
    kwargs['dir']=str(v/'tmp')
    return original(*args, **kwargs)
with patch.object(test_formal_catalog.tempfile,'TemporaryDirectory',isolated_temp):
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_formal_catalog))
sys.exit(not result.wasSuccessful())
