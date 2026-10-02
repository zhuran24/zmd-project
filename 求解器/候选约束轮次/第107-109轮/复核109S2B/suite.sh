#!/bin/bash
# 复核109S2B 整厂套件：3 个并行进程
cd "$(dirname "$0")"
{
for spec in "109001 1 keep no 1.0" "109002 2 clear no 1.0" "109003 4 mix no 0.6" "109004 6 keep no 0.6" \
            "109005 6 clear core_per_side 0.6" "109006 8 mix no 0.8" "109007 12 clear no 1.0" "109008 16 keep no 1.0" \
            "109009 10 mix no 0.5" "109010 3 clear no 0.9" "109011 16 mix core_per_side 0.7" "109012 5 keep no 0.3"; do
  echo $spec
done
} | xargs -P 3 -L 1 bash -c 'timeout 900 python3 -B run_factory.py $0 $1 $2 $3 $4 $5' > suite_results.jsonl 2> suite_err.log
echo done >> suite_err.log
