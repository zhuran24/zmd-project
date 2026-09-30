"""每次启动新父进程，仅计被测命令的RUSAGE_CHILDREN峰值和完整墙钟。"""
import json,resource,subprocess,sys,time
start=time.perf_counter_ns()
p=subprocess.run(sys.argv[1:],capture_output=True,text=True)
print(json.dumps(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,wall_ns=time.perf_counter_ns()-start,max_rss_kb=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)))
