"""Authoritative extractor for Mezze STAFF (Owl) translatable UI strings.

Owl translates: text nodes + alt|aria-label|aria-placeholder|aria-roledescription|
aria-valuetext|label|placeholder|title (+ data-tooltip added by Odoo web/env.js).
JS strings reach the UI through _t("...").
"""
import io, re, glob, json, sys, os

ATTRS = ('alt','aria-label','aria-placeholder','aria-roledescription',
         'aria-valuetext','label','placeholder','title','data-tooltip')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML = sorted(glob.glob(os.path.join(ROOT, 'static/src/**/*.xml'), recursive=True))
JS  = sorted(glob.glob(os.path.join(ROOT, 'static/src/**/*.js'),  recursive=True))
JS  = [f for f in JS if '/tests/' not in f]

def surface(path):
    if '/cashier/' in path: return 'cashier'
    if '/kds/'     in path: return 'kds'
    if '/floor/'   in path: return 'floor'
    return 'other'

strings = {}          # text -> {'files':set, 'kind':set}
def add(txt, f, kind):
    txt = txt.strip()
    if not txt: return
    if not re.search(r'[A-Za-z]{2}', txt): return          # numbers/symbols only
    if txt.startswith('t-') or '=>' in txt or '${' in txt: return
    e = strings.setdefault(txt, {'files': set(), 'kind': set()})
    e['files'].add(surface(f)); e['kind'].add(kind)

for f in XML:
    src = io.open(f, encoding='utf-8').read()
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    for a in ATTRS:                                        # static attribute values only
        for m in re.finditer(r'(?<![-\w])' + a + r'="([^"{}]*)"', src):
            add(m.group(1), f, 'attr:'+a)
    for m in re.finditer(r'>([^<>{}]+)<', src):            # static text nodes
        add(m.group(1), f, 'text')

STR = r'''"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''''
def unquote(lit):
    body = lit[1:-1]
    return body.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n')

for f in JS:
    src = io.open(f, encoding='utf-8').read()
    src = re.sub(r'//[^\n]*', '', src)
    # _t( "a" + "b" + "c" )  -> ONE msgid: the runtime receives the joined string.
    for m in re.finditer(r'_t\(\s*((?:' + STR + r')(?:\s*\+\s*(?:' + STR + r'))*)', src):
        parts = re.findall(STR, m.group(1))
        add(''.join(unquote(p) for p in parts), f, '_t')

po = io.open(os.path.join(ROOT, 'i18n/ar.po'), encoding='utf-8').read()
pairs = re.findall(r'^msgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"', po, re.M)
# Unescape the SAME way ``unquote`` does for source strings. Unescaping only the
# quotes left an asymmetry: a msgid carrying \n stayed as a literal backslash-n and
# could never match the real newline extracted from the template, so a string that
# WAS translated was reported missing and no amount of translating could fix it.
def _po_unescape(v):
    return v.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n')

have = {_po_unescape(k): _po_unescape(v) for k, v in pairs}

missing = {k: v for k, v in strings.items() if k not in have}
blank   = {k: v for k, v in strings.items() if k in have and not have[k].strip()}
total   = len(strings)
valid   = total - len(missing) - len(blank)

def inventory():
    """(strings, have) for the tests: source strings -> {surfaces}, and msgid -> arabic."""
    return strings, have


if __name__ == '__main__' and '--json' in sys.argv:
    print(json.dumps({
        'total': total, 'valid': valid, 'missing': len(missing), 'blank': len(blank),
        'coverage': round(100.0*valid/max(1,total), 1),
        'missing_list': sorted(missing.keys()),
        'by_surface': {s: sum(1 for v in strings.values() if s in v['files'])
                       for s in ('cashier','kds','floor')},
    }, ensure_ascii=False, indent=1))
elif __name__ == '__main__':
    print('STAFF (Owl) translatable strings: %d | Arabic present: %d | MISSING: %d | blank: %d | coverage %.1f%%'
          % (total, valid, len(missing), len(blank), 100.0*valid/max(1,total)))
    for s in ('cashier','kds','floor'):
        n = sum(1 for v in strings.values() if s in v['files'])
        nm = sum(1 for k, v in strings.items() if s in v['files'] and k in missing)
        print('   %-8s strings=%-4d missing=%d' % (s, n, nm))
