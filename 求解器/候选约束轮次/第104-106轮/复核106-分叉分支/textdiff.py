# 核对第 100 轮版本与第 97 轮版本的文字差别（两段原文从两份报告里按引用块取出）。
import re, json, difflib
D = '/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/'
def quote(path):
    t = open(path, encoding='utf-8').read()
    m = re.findall(r'^> (分叉分支：.*)$', t, re.M)
    return m[0]
v97 = quote(D + '第95-97轮/复核97M.md')
v100 = quote(D + '第98-100轮/复核100R.md')
cand = "分叉分支：一个元件有几个合资格的下游元件可供数层时，对每种单位建造次序得出的接通先后，都须覆盖临时规则允许的每一种数层选择，以及由此到达的循环态。同一单位建成时同一刻形成的几条通道，规则没有给出先后，每一种排法都要覆盖。不得用规则未给出的接通先后、选支对应办法排除不利组合。数层时不绕回自己；只有每一种允许的数法都绕回自己时，层数才仍无法确定。同一轴上相邻两个桥接器之间来回的通道不按成环处理。层数仍未定时，不得填入有利的数值，也不得只因未定就排除这个构型。"
old = '；凡判定先后、轮询起点或取货级的接通时刻要用到这些先后，'
res = {'candidate_equals_100R_quote': cand == v100,
       'v97_with_replacement_equals_v100': v97.replace(old, '，') == v100,
       'opcodes': [(op, v97[a:b], v100[c:d]) for op, a, b, c, d in difflib.SequenceMatcher(None, v97, v100).get_opcodes() if op != 'equal']}
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open('textdiff.json', 'w'), ensure_ascii=False, indent=1)
