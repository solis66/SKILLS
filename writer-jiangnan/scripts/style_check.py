#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_check.py — 江南体稿件体检

用法:
    python style_check.py 稿件.txt
    python style_check.py 稿件.txt --mode b
    python style_check.py 稿件.txt --mode c --json

mode:
    a = 校园回忆体（此间的少年）
    b = 末日第一人称（上海堡垒）        <- 默认
    c = 都市奇幻（龙族）
    d = 东方史诗（九州·缥缈录）
    x = 不设目标，只出数字

它只测"形状"，不测"好坏"。指标全对但读起来假，说明人物动机出了问题。
"""

import argparse
import json
import re
import statistics
import sys

HAN = re.compile(r'[\u4e00-\u9fff]')
DIALOGUE = re.compile(r'“([^”]{0,2000})”')
METAPHOR_WORDS = ['像是', '好像', '仿佛', '如同', '似的', '犹如', '宛如', '好比']

# 目标区间 (low, high, unit_note)
TARGETS = {
    'a': {
        'single_sentence_pct': (36.0, 45.0, '单句成段占比 %'),
        'dialogue_pct':        (16.0, 26.0, '引号对话占汉字 %'),
        'metaphor_per_10k':    (5.0, 12.0, '比喻标记 /万字'),
        'exclaim_per_10k':     (10.0, 18.0, '感叹号 /万字'),
        'huran_per_10k':       (2.0, 8.0, '"忽然" /万字'),
        'qishi_per_10k':       (2.0, 8.0, '"其实/原来/所谓" /万字'),
        'sent_median':         (20.0, 27.0, '句长中位数'),
        'para_median':         (28.0, 40.0, '段落中位字数'),
        'ellipsis_per_10k':    (15.0, 28.0, '省略号 /万字'),
    },
    'b': {
        'single_sentence_pct': (40.0, 52.0, '单句成段占比 %'),
        'dialogue_pct':        (18.0, 30.0, '引号对话占汉字 %'),
        'metaphor_per_10k':    (22.0, 32.0, '比喻标记 /万字'),
        'exclaim_per_10k':     (0.0, 3.0,  '感叹号 /万字'),
        'huran_per_10k':       (5.0, 12.0, '"忽然" /万字'),
        'qishi_per_10k':       (4.0, 11.0, '"其实/原来/所谓" /万字'),
        'sent_median':         (17.0, 23.0, '句长中位数'),
        'para_median':         (25.0, 36.0, '段落中位字数'),
        'ellipsis_per_10k':    (20.0, 32.0, '省略号 /万字'),
    },
    'c': {
        'single_sentence_pct': (30.0, 48.0, '单句成段占比 %'),
        'dialogue_pct':        (26.0, 44.0, '引号对话占汉字 %'),
        'metaphor_per_10k':    (12.0, 28.0, '比喻标记 /万字'),
        'exclaim_per_10k':     (15.0, 70.0, '感叹号 /万字'),
        'huran_per_10k':       (5.0, 12.0,  '"忽然" /万字'),
        'qishi_per_10k':       (4.0, 11.0,  '"其实/原来/所谓" /万字'),
        'sent_median':         (13.0, 26.0, '句长中位数'),
        'para_median':         (22.0, 42.0, '段落中位字数'),
        'ellipsis_per_10k':    (15.0, 38.0, '省略号 /万字'),
    },
    'd': {
        'single_sentence_pct': (32.0, 40.0, '单句成段占比 %'),
        'dialogue_pct':        (30.0, 42.0, '引号对话占汉字 %'),
        'metaphor_per_10k':    (16.0, 24.0, '比喻标记 /万字'),
        'exclaim_per_10k':     (30.0, 55.0, '感叹号 /万字'),
        'huran_per_10k':       (4.0, 9.0,  '"忽然" /万字'),
        'qishi_per_10k':       (2.0, 8.0,  '"其实/原来/所谓" /万字'),
        'sent_median':         (19.0, 26.0, '句长中位数'),
        'para_median':         (28.0, 45.0, '段落中位字数'),
        'ellipsis_per_10k':    (12.0, 24.0, '省略号 /万字'),
    },
    'x': {},
}



ADDRESS_TERMS = ['师兄', '师姐', '师弟', '师妹', '学长', '学姐', '学弟', '学妹']
PAIRS = [('师兄', '师弟'), ('师姐', '师妹'), ('学长', '学弟'), ('学姐', '学妹')]


def address_report(text, names):
    '''同人称呼体检：把每个称呼连同上下文列出来，让人工逐条确认说话人。'''
    lines = text.replace('\r\n', '\n').split('\n')
    hits = []
    for i, ln in enumerate(lines, 1):
        for term in ADDRESS_TERMS:
            start = 0
            while True:
                j = ln.find(term, start)
                if j < 0:
                    break
                lo, hi = max(0, j - 26), min(len(ln), j + len(term) + 26)
                ctx = ln[lo:hi].strip()
                hits.append((i, term, ctx))
                start = j + len(term)
    print(BAR)
    print('同人核查 · 称呼扫描')
    print(BAR)
    if not hits:
        print('  全文没有出现称呼词。')
        print('  ⚠ 若这是同人，先确认：这些人之间本来就不叫称呼，还是漏了？')
        print(BAR)
        return
    if names:
        order = [n.strip() for n in names if n.strip() and n != '>']
        if len(order) >= 2:
            print('  届别（按 --canon 给出的先后，从高届到低届）：%s' % ' > '.join(order))
            print('  推导规则：低届的叫高届的「师兄/师姐」，高届的叫低届的「师弟/师妹」。')
            print('             「师兄/师弟」按对方性别选，不是按说话人性别选。')
            print('             相邻两届成立，**不要跨届直接推**。')
            print('')
        missing = [n for n in order if n not in text]
        if missing:
            print('  ⚠ 以下人物在稿子里完全没有出现：%s' % '、'.join(missing))
    print('  共 %d 处，逐条确认「说话人是谁、他叫谁、有没有把届别写反」：' % len(hits))
    print('')
    for i, term, ctx in hits:
        print('   L%-4d [%s] %s' % (i, term, ctx))
    print('')
    for a, b in PAIRS:
        for i, ln in enumerate(lines, 1):
            if a in ln and b in ln:
                print('   ⚠ L%d 同一段里同时出现「%s」和「%s」，先确认是不是写反了。' % (i, a, b))
    print(BAR)
    print('  手工必查：')
    print('   1. 每一格的称呼都有原作依据（不是推出来的）')
    print('   2. 群像场景里，配角与配角之间的称呼也核过')
    print('   3. 专有名词逐字核对（不是「差不多」）')
    print('   4. 这个时间点上，谁还不知道真相')
    print(BAR)
def read_text(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'gb18030', 'utf-16'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='ignore')


def zh(s):
    return len(HAN.findall(s))


def per10k(n, z):
    return round(n / z * 10000, 1) if z else 0.0


def analyse(text):
    text = text.replace('\r\n', '\n')
    z = zh(text)
    if z == 0:
        raise SystemExit('文件里没有中文字符，检查路径或编码。')

    paras = [p.strip() for p in re.split(r'\n+', text) if zh(p) > 2]
    n_paras = len(paras) or 1
    single = sum(1 for p in paras if len(re.findall(r'[。！？…]', p)) <= 1)
    plens = [zh(p) for p in paras] or [0]

    sents = [s for s in re.split(r'[。！？…]+', text) if zh(s) > 0]
    slens = [zh(s) for s in sents] or [0]
    slens.sort()

    dzh = sum(zh(x) for x in DIALOGUE.findall(text))
    meta = sum(len(re.findall(w, text)) for w in METAPHOR_WORDS)

    def cnt(p):
        return per10k(len(re.findall(p, text)), z)

    m = {
        'hanzi': z,
        'paragraphs': len(paras),
        'single_sentence_pct': round(single / n_paras * 100, 1),
        'dialogue_pct': round(dzh / z * 100, 1),
        'sent_median': statistics.median(slens),
        'sent_mean': round(sum(slens) / len(slens), 1),
        'sent_p90': slens[int(len(slens) * 0.9)],
        'para_median': statistics.median(plens),
        'para_mean': round(sum(plens) / len(plens), 1),
        'metaphor_per_10k': per10k(meta, z),
        'huran_per_10k': cnt('忽然'),
        'turan_per_10k': cnt('突然'),
        'qishi_per_10k': cnt('其实') + cnt('原来') + cnt('所谓'),
        'fangfo_per_10k': cnt('仿佛'),
        'ellipsis_per_10k': cnt('……'),
        'dash_per_10k': cnt('——'),
        'exclaim_per_10k': cnt('！'),
        'wo_per_10k': cnt('我'),
    }
    return m


BAR = '─' * 62


def report(m, mode):
    print(BAR)
    print('江南体 · 风格体检报告    模式 = %s' % mode.upper())
    print(BAR)
    print('汉字 %d ｜ 段落 %d' % (m['hanzi'], m['paragraphs']))
    if m['hanzi'] < 5000:
        print('⚠ 样本不足 5000 汉字：密度类指标（比喻/忽然/省略号）波动很大，')
        print('  只看方向，不要当结论。全文体检请在完整稿上跑。')
    print(BAR)

    targets = TARGETS.get(mode, {})
    bad = []
    if not targets:
        for k, v in m.items():
            if k in ('hanzi', 'paragraphs'):
                continue
            print('  %-22s %s' % (k, v))
        print(BAR)
        return 0

    for key, (lo, hi, note) in targets.items():
        val = m.get(key, 0)
        if val < lo:
            flag, mark = 'LOW ', '↓'
            bad.append((note, val, lo, hi, mark))
        elif val > hi:
            flag, mark = 'HIGH', '↑'
            bad.append((note, val, lo, hi, mark))
        else:
            flag, mark = 'OK  ', ' '
        print('  [%s] %-26s %6.1f   (目标 %g–%g)' % (flag, note, val, lo, hi))

    print(BAR)
    extra = [
        ('"突然" /万字（应接近 0）', m['turan_per_10k']),
        ('"仿佛" /万字(a<=2 b<=2 c<=3 d<=6)', m['fangfo_per_10k']),
        ('破折号 /万字', m['dash_per_10k']),
        ('"我" /万字', m['wo_per_10k']),
        ('句长 P90', m['sent_p90']),
    ]
    for note, v in extra:
        print('  参考  %-30s %s' % (note, v))
    print(BAR)

    if bad:
        print('需要处理 %d 项：' % len(bad))
        for note, val, lo, hi, mark in bad:
            if mark == '↑':
                print('  ↑ %s = %.1f，高于 %g' % (note, val, hi))
            else:
                print('  ↓ %s = %.1f，低于 %g' % (note, val, lo))
        print()
        print('提示：指标只是形状。若形状全对但读起来假，')
        print('     回去查人物动机（SKILL.md §4）。')
    else:
        print('形状全部落在目标区间。')
        print('下一步：手工过 SKILL.md §6.1 的十六条清单。')
        print('      同人稿请加 --canon 人物名，再扫一遍称呼与届别。')
    print(BAR)
    return len(bad)


def main():
    ap = argparse.ArgumentParser(description='江南体稿件体检')
    ap.add_argument('path', help='稿件路径（.txt / .md）')
    ap.add_argument('--mode', default='b', choices=list(TARGETS.keys()),
                    help='a 校园 / b 第一人称 / c 都市奇幻 / d 史诗 / x 只看数字')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    ap.add_argument('--canon', default='', metavar='NAMES',
                    help='同人核查：逗号分隔的人物名，额外扫一遍称呼（例：楚子航,路明非,夏弥）')
    args = ap.parse_args()

    text = read_text(args.path)
    m = analyse(text)

    if args.json:
        print(json.dumps({'mode': args.mode, 'metrics': m}, ensure_ascii=False, indent=2))
        return 0

    if args.canon:
        names = [x.strip() for x in args.canon.replace('，', ',').split(',') if x.strip()]
        address_report(text, names)

    return 0 if report(m, args.mode) == 0 else 0


if __name__ == '__main__':
    sys.exit(main())