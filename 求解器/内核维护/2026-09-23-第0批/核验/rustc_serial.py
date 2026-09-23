#!/usr/bin/env python3
import os,sys
os.execvp(sys.argv[1],[sys.argv[1],'-Zthreads=1','-Zno-parallel-backend','-Ccodegen-units=1',*sys.argv[2:]])
