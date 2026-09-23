import os,subprocess,sys
p=[subprocess.Popen([sys.argv[1],"--test-threads=1","--nocapture"],env=os.environ.copy()) for _ in range(2)]
assert all(x.wait()==0 for x in p)
