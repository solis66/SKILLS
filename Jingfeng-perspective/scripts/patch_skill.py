# -*- coding: utf-8 -*-
import io
p = r"C:\Users\20931\.dsh\skills\ljf-perspective\SKILL.md"
s = io.open(p, encoding='utf-8').read()

# 1) 标题：表达 DNA -> 表达DNA（检查器按字面匹配）
s = s.replace("## 6. 表达 DNA", "## 6. 表达DNA（语言指纹）")

# 2) 诚实边界：编号列表 -> 项目符号列表（检查器只数 - / * 开头的条目）
lines = s.split('\n')
start = next(i for i,l in enumerate(lines) if l.startswith('## 11. 诚实边界'))
end = next(i for i,l in enumerate(lines) if l.startswith('## 12.'))
for i in range(start+1, end):
    if lines[i].startswith('1. '):
        lines[i] = '- ' + lines[i][3:]
    else:
        import re
        m = re.match(r'^(\d+)\. (.*)$', lines[i])
        if m:
            lines[i] = '- ' + m.group(2)
s = '\n'.join(lines)

# 3) 张力标题：把被塞进去的"张力"改回 vs
fixes = {
    "### T1｜证据洁癖 张力 过筛冲动": "### T1｜证据洁癖 vs 过筛冲动",
    "### T3｜「不要编造」张力「帮我补强」": "### T3｜「不要编造」vs「帮我补强」",
    "### T4｜计划精细 张力 兑现率低": "### T4｜计划精细 vs 兑现率低",
    "### T5｜抗拒稳定路线 张力 走稳定路线": "### T5｜抗拒稳定路线 vs 走稳定路线",
    "### T6｜自我低估 张力 实际产出": "### T6｜自我低估 vs 实际产出",
}
for a,b in fixes.items():
    s = s.replace(a,b)

io.open(p,'w',encoding='utf-8').write(s)
print('patched. lines =', s.count('\n')+1)
