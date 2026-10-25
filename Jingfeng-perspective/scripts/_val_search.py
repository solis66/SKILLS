# -*- coding: utf-8 -*-
"""关键词回查：在语料中检索关键词，输出 文件名#行号 形式的引用证据。

用法: python _val_search.py "关键词1|关键词2" [ai|chat|both] [条数上限]
- scope=ai   只搜 references/sources/transcripts/user-turns.jsonl（本人对 AI 的发言）
- scope=chat 只搜 references/sources/wechat/*/*.jsonl（需本地完整版语料）
输出行可直接用于 SKILL.md / 研究底稿里的 [文件#L行号] 引用。
"""
import json, glob, sys, re, os
BASE='.'
UT='references/sources/transcripts/user-turns.jsonl'
def ut_lines():
    return open(UT, encoding='utf-8').read().splitlines()
def chat_files():
    return sorted(glob.glob('references/sources/wechat/*/*.jsonl'))
def search_terms(terms, scope='both', who='me', ctx=0, limit=200):
    pat = re.compile('|'.join(terms))
    out=[]
    if scope in ('both','ai'):
        ls = ut_lines()
        for i,l in enumerate(ls,1):
            try: d=json.loads(l)
            except: continue
            t=d.get('text') or ''
            if pat.search(t):
                out.append(('AI', 'user-turns.jsonl', i, d.get('ts',''), t.replace('\n','\\n')))
    if scope in ('both','chat'):
        for f in chat_files():
            ls=open(f,encoding='utf-8').read().splitlines()
            for i,l in enumerate(ls,1):
                try: d=json.loads(l)
                except: continue
                if who=='me' and d.get('from')!='me': continue
                t=d.get('text') or ''
                if pat.search(t):
                    rel=f.replace('references/sources/wechat/','wechat/').replace('\\','/')
                    out.append(('CHAT', rel, i, d.get('iso',''), t.replace('\n','\\n')))
    return out
if __name__=='__main__':
    terms=sys.argv[1].split('|')
    scope=sys.argv[2] if len(sys.argv)>2 else 'both'
    lim=int(sys.argv[3]) if len(sys.argv)>3 else 60
    res=search_terms(terms, scope)
    print('TOTAL', len(res))
    for r in res[:lim]:
        print(f"{r[0]}\t{r[1]}#L{r[2]}\t{r[3]}\t{r[4][:220]}")
