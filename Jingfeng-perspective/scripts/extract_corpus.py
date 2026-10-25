# -*- coding: utf-8 -*-
"""提取 claude / dsh 会话中的真实用户发言，脱敏后落盘。"""
import json, os, re, glob, subprocess, sys, collections

OUT = r"C:\Users\20931\.dsh\skills\ljf-perspective\references\sources\transcripts"
os.makedirs(OUT, exist_ok=True)

CLAUDE_GLOB = r"C:\Users\20931\.claude\projects\**\*.jsonl"
DSH_GLOB = r"C:\Users\20931\.dsh\sessions\**\*.zstd"

SECRET = [
    (re.compile(r'sk-[A-Za-z0-9_\-]{16,}'), 'sk-***REDACTED***'),
    (re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'), 'gh***REDACTED***'),
    (re.compile(r'AKIA[0-9A-Z]{16}'), 'AKIA***REDACTED***'),
    (re.compile(r'(?i)(authorization|api[_-]?key|token|password|secret)\s*[:=]\s*["\']?[A-Za-z0-9\-_\.]{12,}'), r'\1=***REDACTED***'),
    (re.compile(r'1[3-9]\d{9}'), '***PHONE***'),
]
def redact(t):
    for pat, rep in SECRET:
        t = pat.sub(rep, t)
    return t

SKIP_PREFIX = ('<command-', '<local-command', 'Caveat:', '<system-reminder', 'This session is being continued')
def clean(t):
    t = t.strip()
    if not t: return ''
    if t.startswith(SKIP_PREFIX): return ''
    if t.count('<system-reminder') and len(t) < 600: return ''
    t = re.sub(r'<system-reminder>[\s\S]*?</system-reminder>', '', t).strip()
    return t

def texts_from_content(c):
    if isinstance(c, str): return [c]
    out = []
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str):
                out.append(b['text'])
    return out

records = []          # (ts, source, cwd, text)
sess_meta = collections.OrderedDict()

# ---- Claude Code sessions ----
for path in glob.glob(CLAUDE_GLOB, recursive=True):
    sid = os.path.basename(path).replace('.jsonl', '')
    cwd, last_ts, n = None, None, 0
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                try: o = json.loads(line)
                except Exception: continue
                if o.get('cwd'): cwd = o['cwd']
                if o.get('timestamp'): last_ts = o['timestamp']
                if o.get('type') != 'user': continue
                m = o.get('message')
                if not isinstance(m, dict) or m.get('role') != 'user': continue
                for t in texts_from_content(m.get('content')):
                    t = clean(t)
                    if len(t) < 2: continue
                    records.append((o.get('timestamp') or '', 'claude', cwd or '', redact(t)))
                    n += 1
    except Exception as e:
        print('ERR claude', path, e, file=sys.stderr)
    if n:
        sess_meta['claude:' + sid] = dict(source='claude', cwd=cwd, msgs=n, last=last_ts or '')

# ---- DSH sessions ----
for path in glob.glob(DSH_GLOB, recursive=True):
    try:
        raw = subprocess.run(['zstd', '-dc', path], capture_output=True, timeout=120).stdout
    except Exception as e:
        print('ERR zstd', path, e, file=sys.stderr); continue
    sid = os.path.basename(os.path.dirname(path))
    cwd, first_ts, n = None, None, 0
    for line in raw.decode('utf-8', 'replace').splitlines():
        try: o = json.loads(line)
        except Exception: continue
        t = o.get('type')
        if t == 'session':
            cwd = o.get('cwd') or cwd
            continue
        if t in ('agent/inbox/spliced',):
            d = o.get('data') or {}
            if d.get('target') not in (None, 'next-turn'): continue
            for item in d.get('inserted') or []:
                if not isinstance(item, dict): continue
                src = item.get('source') or {}
                role = item.get('role')
                if role != 'user' and src.get('kind') != 'user': continue
                ts = item.get('id') and ''
                for x in texts_from_content(item.get('content')):
                    x = clean(x)
                    if len(x) < 2: continue
                    records.append((str(o.get('time') or ''), 'dsh', cwd or '', redact(x)))
                    n += 1
        elif t == 'system/message':
            m = (o.get('data') or {}).get('message') or {}
            if m.get('role') == 'user':
                for x in texts_from_content(m.get('content')):
                    x = clean(x)
                    if len(x) < 2: continue
                    records.append((str(o.get('time') or ''), 'dsh', cwd or '', redact(x)))
                    n += 1
    if n:
        sess_meta['dsh:' + sid] = dict(source='dsh', cwd=cwd, msgs=n, last=str(first_ts or ''))

print('user messages:', len(records), 'sessions with msgs:', len(sess_meta))
print('chars:', sum(len(r[3]) for r in records))

# 去重（同文本相邻）
dedup = []
seen = set()
for r in records:
    key = r[3][:300]
    if key in seen and len(r[3]) < 4000:
        continue
    seen.add(key)
    dedup.append(r)
print('after dedup:', len(dedup))

with open(os.path.join(OUT, 'user-turns.jsonl'), 'w', encoding='utf-8') as fh:
    for ts, src, cwd, txt in dedup:
        fh.write(json.dumps(dict(ts=ts, source=src, cwd=cwd, text=txt), ensure_ascii=False) + '\n')

with open(os.path.join(OUT, 'sessions-index.md'), 'w', encoding='utf-8') as fh:
    fh.write('# 会话索引\n\n| 来源 | 会话/工作目录 | 用户发言数 | 最后活动 |\n|---|---|---|---|\n')
    for k, v in sorted(sess_meta.items(), key=lambda kv: -kv[1]['msgs']):
        fh.write('| %s | %s | %d | %s |\n' % (v['source'], (v['cwd'] or '?'), v['msgs'], v['last']))

print('written:', OUT)
