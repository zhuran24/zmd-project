#!/usr/bin/env python3
"""第四轮§5：原CLI回归主体原样运行，仅把写入目录重定向到本轮复核证据。"""
import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
TESTS=ROOT/'crates/kernel/tests'
sys.path.insert(0,str(TESTS))
sys.argv=['review',str(OUT/'target/release/kernel')]
SPEC=importlib.util.spec_from_file_location('review_cli',TESTS/'revision_cli.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MODULE.EVIDENCE=OUT/'cli'
MODULE.OUT=MODULE.EVIDENCE/'tmp'
MODULE.main()
