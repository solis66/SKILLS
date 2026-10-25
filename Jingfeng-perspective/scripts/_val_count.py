# -*- coding: utf-8 -*-
"""定量校验：统计语料总量与关键词命中数（保真度记分卡的底层数据）。

输出两块：
- AI  ：user-turns.jsonl 总条数 + 各口头禅/关键表述出现次数
- CHAT：微信语料中本人（from=='me'）消息总数 + 敏感话题词频
（CHAT 部分需要本地完整版 wechat 语料，公开仓库中为 0 属预期）
"""
import json, glob, re
ut=[json.loads(l) for l in open('references/sources/transcripts/user-turns.jsonl',encoding='utf-8')]
txt=[d.get('text') or '' for d in ut]
print('AI turns:', len(ut))
for kw in ['不要编造代码无法支持的行为','先不要改简历','谢谢','感谢','麻烦','辛苦','包装','外包','私活','兼职','接单']:
    n=sum(1 for t in txt if kw in t)
    print(f'AI  {kw}\t{n}')
files=sorted(glob.glob('references/sources/wechat/*/*.jsonl'))
me=[]
for f in files:
    for l in open(f,encoding='utf-8'):
        d=json.loads(l)
        if d.get('from')=='me': me.append(d.get('text') or '')
print('me msgs:', len(me))
for kw in ['外包','私活','兼职','接单','包装','造假','考研','大厂','学历','简历']:
    n=sum(1 for t in me if kw in t)
    print(f'CHAT {kw}\t{n}')
