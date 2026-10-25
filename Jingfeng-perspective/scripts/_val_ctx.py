# -*- coding: utf-8 -*-
"""上下文回查：打印某条语料（文件#行号）前后各 N 行，用于人工核对引用是否断章取义。

用法: python _val_ctx.py <语料文件路径> <行号> [前几行] [后几行]
>> 标记目标行；每行显示 时间/说话人/文本前160字。
"""
import json, sys
def show(f, ln, before=4, after=4):
    ls=open(f, encoding='utf-8').read().splitlines()
    for i in range(max(1,ln-before), min(len(ls), ln+after)+1):
        d=json.loads(ls[i-1])
        mark='>>' if i==ln else '  '
        print(f"{mark}L{i}\t{d.get('iso','')}\t{d.get('from','')}\t{(d.get('text') or '')[:160]}")
if __name__=='__main__':
    show(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv)>3 else 4, int(sys.argv[4]) if len(sys.argv)>4 else 4)
