"""FINAL-C4 — inventory helper for the two operator-board localization dictionaries.

Imported by the tests so the numbers in the closure report and the numbers the suite
enforces come from the same code and cannot drift apart.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ('courses.html', 'drivethru.html')


def audit(page):
    """-> dict(en=set, ar=set, hooks=set, used=set, src=str) for one static page."""
    src = io.open(os.path.join(ROOT, 'static', page), encoding='utf-8').read()
    m = re.search(r"var T=\{\s*\n?\s*en:\{(.*?)\},\s*\n?\s*ar:\{(.*?)\}\};", src, re.S)
    if not m:
        return None

    def keys(block):
        return set(re.findall(r"(?:^|,|\{)\s*(\w+)\s*:", block))

    hooks = set()
    for attr in ('data-t', 'data-tph', 'data-tal'):
        hooks |= set(re.findall(attr + r'="([^"]+)"', src))
    # (?<![\w.]) so get('token') / createElement('div') are not mistaken for t('key')
    used = set(re.findall(r"(?<![\w.])t\('(\w+)'\)", src))
    return {'en': keys(m.group(1)), 'ar': keys(m.group(2)),
            'hooks': hooks, 'used': used, 'src': src}
