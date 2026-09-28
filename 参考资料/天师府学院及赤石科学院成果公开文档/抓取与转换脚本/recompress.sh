#!/bin/bash
# 无损重压 PNG：像素逐一相同才替换（compare AE=0），不去掉色彩元数据
f="$1"; t="${f%.png}.tmp.png"
op=$(magick identify -format "%[opaque]" "$f[0]" 2>/dev/null)
if [ "$op" = "True" ]; then A="-alpha off"; else A=""; fi
magick "$f" $A -define png:compression-level=9 -define png:compression-filter=5 -define png:compression-strategy=1 "$t" 2>/dev/null || { rm -f "$t"; echo "ERR $f"; exit 0; }
ae=$(magick compare -metric AE "$f" "$t" null: 2>&1 | awk '{print $1}')
a=$(stat -c %s "$f"); b=$(stat -c %s "$t")
if [ "$ae" = "0" ] && [ "$b" -lt "$a" ]; then mv "$t" "$f"; echo "OK $a $b $f"; else rm -f "$t"; echo "KEEP $a $b ae=$ae $f"; fi
