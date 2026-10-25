# -*- coding: utf-8 -*-
"""把作者本人产出的文档转成可读文本，存入 sources/articles。"""
import os, re, shutil, zipfile, subprocess, sys
from xml.etree import ElementTree as ET

OUT = r"C:\Users\20931\.dsh\skills\ljf-perspective\references\sources\articles"
os.makedirs(OUT, exist_ok=True)
DESK = r"C:\Users\20931\Desktop"

DOCS = [
    # (相对路径, 归档名, 类型, 作者可信度说明)
    (r"刘竞峰\10.14_记录.md", "note-10.14.md", "个人记录", "本人手写/AI协作"),
    (r"刘竞峰\10.15_记录.md", "note-10.15.md", "个人记录", "本人手写/AI协作"),
    (r"刘竞峰\2026-10-15_明日计划与增肌补剂建议.md", "note-10.15-plan.md", "个人计划", "本人手写/AI协作"),
    (r"刘竞峰\2026-10-16_学习与生活要求.md", "note-10.16-rules.md", "自我要求", "本人手写/AI协作"),
    (r"aigcbilibili\deliverables\刘竞峰-简历_含LABiliBili项目.docx", "resume.docx.txt", "简历", "本人定稿"),
    (r"aigcbilibili\deliverables\星火私聊模块改造与简历包装方案.md", "project-xinghuo-plan.md", "项目方案", "AI协作产出"),
    (r"aigcbilibili\deliverables\面试问答-按技术栈分点.md", "interview-qa.md", "面试材料", "AI协作产出"),
    (r"aigcbilibili\README.md", "project-aigcbilibili-README.md", "项目文档", "AI协作产出"),
    (r"aigc\雨落狂流之暗.docx", "fiction-yuluo.docx.txt", "创作", "本人创作"),
    (r"aigc\雨落狂流之暗\雨落狂流之夜分镜.md", "fiction-yuluo-storyboard.md", "创作分镜", "本人创作/AI协作"),
    (r"aigc\月色真美\月がきれい_婚后番外_30s单集制作方案.md", "creative-moon-plan.md", "创作方案", "本人创作/AI协作"),
    (r"AI 技术应用对大湾区传统服务业就业结构的影响研究——基于餐饮零售行业的实证分析\研究\研究1.docx", "research-dawanqu-1.docx.txt", "研究报告", "本人/团队研究"),
    (r"agentProject\single-file-ai-agent\README.MD", "project-single-file-agent-README.md", "项目文档", "AI协作产出"),
]

def docx_text(path):
    z = zipfile.ZipFile(path)
    xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paras = []
    for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        txt = ''.join(t.text or '' for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
        if txt.strip(): paras.append(txt.strip())
    return '\n'.join(paras)

SECRET = [
    (re.compile(r'sk-[A-Za-z0-9_\-]{16,}'), 'sk-***REDACTED***'),
    (re.compile(r'1[3-9]\d{9}'), '***PHONE***'),
]
def redact(t):
    for pat, rep in SECRET: t = pat.sub(rep, t)
    return t

rows = []
for rel, name, kind, trust in DOCS:
    src = os.path.join(DESK, rel)
    if not os.path.exists(src):
        rows.append((name, kind, trust, 'MISSING')); continue
    try:
        if src.lower().endswith('.docx'):
            text = docx_text(src)
        else:
            text = open(src, encoding='utf-8', errors='replace').read()
    except Exception as e:
        rows.append((name, kind, trust, 'ERR ' + str(e))); continue
    text = redact(text)
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as fh:
        fh.write('# 来源: %s\n# 类型: %s  作者可信度: %s\n\n%s\n' % (rel, kind, trust, text))
    rows.append((name, kind, trust, '%d 字符' % len(text)))

with open(os.path.join(OUT, '_MANIFEST.md'), 'w', encoding='utf-8') as fh:
    fh.write('# 著作类素材清单\n\n| 文件 | 类型 | 作者可信度 | 状态 |\n|---|---|---|---|\n')
    for r in rows: fh.write('| %s | %s | %s | %s |\n' % r)
    fh.write('\n> 作者可信度说明：本人定稿 > 本人创作 > 本人手写/AI协作 > AI协作产出。后者可能被AI大幅改写，引用时降低权重。\n')
print('\n'.join('%s | %s | %s' % (a, b, d) for a, b, c, d in rows))
