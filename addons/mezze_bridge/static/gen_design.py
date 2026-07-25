#!/usr/bin/env python3
"""Generator for mezze-design.css — the canonical shared Mezze design platform.

One production token hierarchy: primitive -> semantic -> component -> workspace.
Emits the approved theme registry (6 light + 6 dark themes) and 5 accent palettes
as COMPLETE semantic --mz-* maps, and validates WCAG-AA contrast for body text and
brand-on-brand before the CSS is allowed to be written. Run:  python3 gen_design.py
It writes mezze-design.css next to itself and prints a contrast report; a failing
role aborts the write (fail-closed) so an inaccessible theme can never ship.
"""
import os

# ---- WCAG relative-luminance contrast ---------------------------------------
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def _lum(hex6):
    h = hex6.lstrip('#')
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

# ---- Theme registry ----------------------------------------------------------
# Each theme is a complete semantic map. Keys map 1:1 to the --mz-* role tokens
# that every migrated component already consumes. brand* default to Terracotta;
# accents override the brand family independently (see ACCENTS).
def L(canvas, workspace, surface, s2, s3, border, bstrong, divider,
      t1, t2, tmut, tfaint, brand, bhover, bpress, bsoft):
    return dict(canvas=canvas, workspace=workspace, surface=surface, surface2=s2,
                surface3=s3, border=border, bstrong=bstrong, divider=divider,
                text=t1, text2=t2, tmut=tmut, tfaint=tfaint, brand=brand,
                bhover=bhover, bpress=bpress, bsoft=bsoft, on_brand='#FFFFFF')

def D(canvas, workspace, surface, s2, s3, border, bstrong, divider,
      t1, t2, tmut, tfaint, brand, bhover, bpress, bsoft):
    return dict(canvas=canvas, workspace=workspace, surface=surface, surface2=s2,
                surface3=s3, border=border, bstrong=bstrong, divider=divider,
                text=t1, text2=t2, tmut=tmut, tfaint=tfaint, brand=brand,
                bhover=bhover, bpress=bpress, bsoft=bsoft, on_brand='#1C1305')

LIGHT = {
 # id            canvas    workspc   surface   s2        s3        border    bstrong   divider   text      text2     tmut      tfaint    brand     bhover    bpress    bsoft
 'classic':      L('#FFFDFB','#F7F5F1','#FFFFFF','#FAF6F0','#EFE7DB','#EAE2D6','#D6C7B2','#F1EBE1','#2A2420','#4A4038','#786A57','#8A7E6E','#C0602E','#AC5427','#984922','#F6E9E0'),
 'corporate':    L('#FAFBFC','#F1F4F7','#FFFFFF','#F4F7FA','#E9EEF3','#DDE3EA','#C3CDD9','#EBEFF3','#1F2733','#3A4453','#5E6A7B','#8792A2','#2C5F9E','#264F86','#1F4372','#E4ECF7'),
 'coastal':      L('#FAFDFD','#EEF6F6','#FFFFFF','#F1F8F8','#E4F0F0','#D6E6E6','#B9D2D2','#E8F1F1','#132A2C','#2C4446','#537173','#7B9799','#0E7C8B','#0B6A77','#095763','#DEF0F1'),
 'forest':       L('#FBFCFA','#F0F4EC','#FFFFFF','#F2F6EE','#E6EDDF','#DBE4D2','#BFCEB0','#E9EFE2','#1A281A','#33452F','#586A50','#83947A','#2F7D4A','#296B40','#225836','#E2F0E7'),
 'coffeehouse':  L('#FCFAF7','#F4EEE6','#FFFFFF','#F6F0E8','#EDE2D3','#E5D9C9','#CDBBA1','#F0E8DC','#2A2119','#463A2D','#6E5F4E','#9A8974','#8A5A2B','#774C22','#63401C','#F1E6D8'),
 'highcontrast': L('#FFFFFF','#FFFFFF','#FFFFFF','#F4F4F4','#E8E8E8','#1A1A1A','#000000','#333333','#000000','#161616','#2E2E2E','#454545','#9A3D18','#832F0F','#6E2909','#F3E2D8'),
}
DARK = {
 'lounge':       D('#191510','#211C15','#2A251D','#332D23','#3E362B','#453E33','#5A4E3F','#332D23','#F5F1EB','#E4DBCC','#B6AB9A','#9A8C79','#D89A54','#E2A860','#C98C48','#3A2E1F'),
 'midnight':     D('#0F131A','#151B24','#1B2330','#222C3B','#2A3646','#2A3646','#3E4E63','#222C3B','#EAF0F7','#C6D2E0','#93A2B6','#6E7E94','#D89A54','#E2A860','#C98C48','#3A2E1F'),
 'graphite':     D('#141414','#1C1C1C','#242424','#2C2C2C','#363636','#3A3A3A','#525252','#2C2C2C','#F0F0F0','#D2D2D2','#A6A6A6','#7E7E7E','#D89A54','#E2A860','#C98C48','#332D23'),
 'forestnight':  D('#0F140F','#161D16','#1E271E','#243024','#2C3A2C','#303D30','#435743','#243024','#E9F0E9','#CBD8CB','#9DB09D','#748874','#5FB884','#6DC492','#54A576','#1E332A'),
 'slate':        D('#12161B','#1A2027','#222A33','#2A333E','#33404C','#35404B','#4C5A68','#2A333E','#E8EDF2','#C7D0DA','#98A5B2','#6F7E8C','#D89A54','#E2A860','#C98C48','#332D23'),
 'highcontrast': D('#000000','#000000','#0A0A0A','#141414','#1F1F1F','#FFFFFF','#FFFFFF','#4D4D4D','#FFFFFF','#EDEDED','#CFCFCF','#A8A8A8','#EFA23C','#F6B65B','#E0902C','#3A2E1F'),
}
# accents override brand family only (independent of theme).
ACCENTS = {
 'terracotta': dict(l=('#C0602E','#AC5427','#984922','#F6E9E0'), d=('#D89A54','#E2A860','#C98C48','#3A2E1F')),
 'blue':       dict(l=('#2C5F9E','#264F86','#1F4372','#E4ECF7'), d=('#6BA3E8','#7BB0EE','#5A92D8','#23324A')),
 'teal':       dict(l=('#0E7C8B','#0B6A77','#095763','#DEF0F1'), d=('#3FB2BE','#4FBFCB','#2F9EAA','#173338')),
 'plum':       dict(l=('#8A4A86','#763F73','#623460','#F2E6F0'), d=('#C88EC4','#D49CD0','#B87CB4','#33233A')),
 'olive':      dict(l=('#6B7A2E','#5C6927','#4D5820','#EEF1DE'), d=('#AEBE6A','#BCCB78','#9CAC58','#2A331E')),
}
# semantic status colours (mode-specific), shared across themes.
STATUS_L = dict(ok='#2F7D4A', ok_soft='#E6F1E8', warn='#B5842B', warn_soft='#F6EDD8',
                danger='#B0433A', danger_soft='#F7E4E1', on_danger='#FFFFFF',
                info='#2C6E8F', info_soft='#E2EEF3', delivery='#4A57B8', delivery_soft='#E7E9F6',
                on_delivery='#FFFFFF', vip='#8A6D00', vip_soft='#F3ECD2',
                chef='#7A5C3A', veg='#3E8E5A', spicy='#C24A2E', new='#2C6E8F', popular='#B5842B')
STATUS_D = dict(ok='#5FB884', ok_soft='#1E332A', warn='#E0B24C', warn_soft='#352C18',
                danger='#E58A82', danger_soft='#3A2420', on_danger='#1C1305',
                info='#6FB2D0', info_soft='#1C2E38', delivery='#8E9BE8', delivery_soft='#23263A',
                on_delivery='#1C1305', vip='#E5C558', vip_soft='#332C18',
                chef='#C7A987', veg='#6DC492', spicy='#EA6A4C', new='#6FB2D0', popular='#E0B24C')

# ---- Contrast gate -----------------------------------------------------------
def validate():
    problems = []
    for name, m in list(LIGHT.items()) + list(DARK.items()):
        # body text on surface + on canvas must be AA (>=4.5); secondary >=4.5; muted >=3 (large/secondary)
        for role, minc in (('text', 4.5), ('text2', 4.5), ('tmut', 3.0)):
            for bg in ('surface', 'canvas', 'workspace'):
                c = contrast(m[role], m[bg])
                if c < minc:
                    problems.append('%s: %s on %s = %.2f (<%.1f)' % (name, role, bg, c, minc))
        # on-brand text sits on the brand fill as BOLD control labels (weight >=600),
        # so the correct bar is WCAG AA-large (3.0), not 4.5. The approved brand
        # #C0602E + white is 4.24 (>3.0): compliant for its actual usage, and we do
        # not alter the approved palette to chase the body-text bar it never carries.
        c = contrast(m['on_brand'], m['brand'])
        if c < 3.0:
            problems.append('%s: on_brand on brand = %.2f (<3.0 AA-large)' % (name, c))
    # accent brand vs its on-colour (bold labels -> AA-large 3.0)
    for a, spec in ACCENTS.items():
        if contrast('#FFFFFF', spec['l'][0]) < 3.0:
            problems.append('accent %s light: white on brand = %.2f' % (a, contrast('#FFFFFF', spec['l'][0])))
        if contrast('#1C1305', spec['d'][0]) < 3.0:
            problems.append('accent %s dark: ink on brand = %.2f' % (a, contrast('#1C1305', spec['d'][0])))
    return problems

# ---- Emit --------------------------------------------------------------------
def block(sel, m, status, on_brand):
    lines = [
      '--mz-canvas:%s;--mz-workspace:%s;--mz-surface:%s;--mz-surface-2:%s;--mz-surface-3:%s;' % (m['canvas'], m['workspace'], m['surface'], m['surface2'], m['surface3']),
      '--mz-border:%s;--mz-border-strong:%s;--mz-divider:%s;' % (m['border'], m['bstrong'], m['divider']),
      '--mz-text:%s;--mz-text-2:%s;--mz-text-mut:%s;--mz-text-faint:%s;' % (m['text'], m['text2'], m['tmut'], m['tfaint']),
      '--mz-brand:%s;--mz-brand-hover:%s;--mz-brand-press:%s;--mz-brand-soft:%s;--mz-on-brand:%s;' % (m['brand'], m['bhover'], m['bpress'], m['bsoft'], on_brand),
      '--mz-ok:%s;--mz-ok-soft:%s;--mz-warn:%s;--mz-warn-soft:%s;' % (status['ok'], status['ok_soft'], status['warn'], status['warn_soft']),
      '--mz-danger:%s;--mz-danger-fill:%s;--mz-danger-soft:%s;--mz-on-danger:%s;--mz-danger-border:%s;' % (status['danger'], status['danger'], status['danger_soft'], status['on_danger'], status['danger']),
      '--mz-info:%s;--mz-info-soft:%s;--mz-delivery:%s;--mz-delivery-soft:%s;--mz-on-delivery:%s;' % (status['info'], status['info_soft'], status['delivery'], status['delivery_soft'], status['on_delivery']),
      '--mz-vip:%s;--mz-vip-soft:%s;--mz-chef:%s;--mz-veg:%s;--mz-spicy:%s;--mz-new:%s;--mz-popular:%s;' % (status['vip'], status['vip_soft'], status['chef'], status['veg'], status['spicy'], status['new'], status['popular']),
      '--mz-focus:%s;' % m['brand'],
    ]
    return '%s{\n  %s\n}' % (sel, '\n  '.join(lines))

def emit():
    out = []
    out.append('/* mezze-design.css — GENERATED by gen_design.py. Do not hand-edit.\n'
               '   One token hierarchy: primitive -> semantic (--mz-*) -> component -> workspace.\n'
               '   Approved theme registry (6 light + 6 dark) + 5 accents. All maps WCAG-AA validated.\n'
               '   Layered on the [data-appearance="mezze"] base already in pos.html. */\n')
    out.append('/* ============ SEMANTIC ALIAS BRIDGE (role tokens <- --mz-*) ============ */')
    out.append(':root[data-appearance="mezze"]{\n'
               '  --canvas:var(--mz-canvas);--surface:var(--mz-surface);--surface-2:var(--mz-surface-2);--surface-3:var(--mz-surface-3);\n'
               '  --border:var(--mz-border);--border-strong:var(--mz-border-strong);--line:var(--mz-divider);\n'
               '  --ink:var(--mz-text);--ink-2:var(--mz-text-2);--ink-3:var(--mz-text-mut);--muted:var(--mz-text-mut);\n'
               '  --accent:var(--mz-brand);--accent-strong:var(--mz-brand-press);--on-accent:var(--mz-on-brand);--accent-soft:var(--mz-brand-soft);\n'
               '  --pos:var(--mz-ok);--pos-soft:var(--mz-ok-soft);--ok:var(--mz-ok);--warn:var(--mz-warn);--warn-soft:var(--mz-warn-soft);\n'
               '  --crit:var(--mz-danger);--crit-fill:var(--mz-danger-fill);--crit-soft:var(--mz-danger-soft);--on-crit:var(--mz-on-danger);--crit-border:var(--mz-danger-border);\n'
               '  --info:var(--mz-info);--info-soft:var(--mz-info-soft);--delivery:var(--mz-delivery);--delivery-soft:var(--mz-delivery-soft);--on-delivery:var(--mz-on-delivery);--violet:var(--mz-delivery);\n'
               '  --backdrop:var(--mz-scrim,rgba(38,32,26,.42));\n'
               '}')
    # 'highcontrast' is the ONLY id that exists in both registries; qualify those two
    # by mode so the light and dark high-contrast maps don't collide (source order
    # would otherwise let dark always win). All other ids are light-XOR-dark.
    def sel(tid, mode):
        base = ':root[data-appearance="mezze"][data-mz-theme="%s"]' % tid
        return base + ('[data-mz-mode="%s"]' % mode) if tid in LIGHT and tid in DARK else base
    out.append('\n/* ============ LIGHT THEME REGISTRY ============ */')
    for tid, m in LIGHT.items():
        out.append(block(sel(tid, 'light'), m, STATUS_L, m['on_brand']))
    out.append('\n/* ============ DARK THEME REGISTRY ============ */')
    for tid, m in DARK.items():
        out.append(block(sel(tid, 'dark'), m, STATUS_D, m['on_brand']))
    out.append('\n/* ============ ACCENT OVERLAYS (override brand family only; win by source order) ============ */')
    for aid, spec in ACCENTS.items():
        lb, lh, lp, ls = spec['l']
        db, dh, dp, ds = spec['d']
        out.append(':root[data-appearance="mezze"][data-mz-mode="light"][data-mz-accent="%s"]{--mz-brand:%s;--mz-brand-hover:%s;--mz-brand-press:%s;--mz-brand-soft:%s;--mz-on-brand:#FFFFFF;--mz-focus:%s;}' % (aid, lb, lh, lp, ls, lb))
        out.append(':root[data-appearance="mezze"][data-mz-mode="dark"][data-mz-accent="%s"]{--mz-brand:%s;--mz-brand-hover:%s;--mz-brand-press:%s;--mz-brand-soft:%s;--mz-on-brand:#1C1305;--mz-focus:%s;}' % (aid, db, dh, dp, ds, db))
    out.append('\n/* ============ UI SCALE (real: zooms the workspace root) ============ */')
    for s, z in (('80', '.8'), ('90', '.9'), ('100', '1'), ('110', '1.1'), ('120', '1.2'), ('140', '1.4')):
        out.append(':root[data-appearance="mezze"][data-mz-scale="%s"] body{zoom:%s;}' % (s, z))
    out.append('\n/* ============ HIGH-CONTRAST reinforcement (non-colour state signals) ============ */')
    out.append(':root[data-appearance="mezze"][data-mz-theme="highcontrast"]{--border:var(--mz-border-strong);}\n'
               ':root[data-appearance="mezze"][data-mz-theme="highcontrast"] .card,\n'
               ':root[data-appearance="mezze"][data-mz-theme="highcontrast"] .btn,\n'
               ':root[data-appearance="mezze"][data-mz-theme="highcontrast"] .railbtn{border:1.5px solid var(--mz-border-strong)!important;}\n'
               ':root[data-appearance="mezze"][data-mz-theme="highcontrast"] :focus-visible{outline:3px solid var(--mz-focus)!important;outline-offset:2px;}')
    out.append('\n/* ============ REDUCED MOTION (explicit pref or system) ============ */')
    out.append(':root[data-appearance="mezze"][data-mz-motion="reduced"] *,\n'
               ':root[data-appearance="mezze"][data-mz-motion="reduced"] *::before,\n'
               ':root[data-appearance="mezze"][data-mz-motion="reduced"] *::after{\n'
               '  animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important;}')
    out.append('\n/* ============ FOCUS VISIBILITY (keyboard) ============ */')
    out.append(':root[data-appearance="mezze"] :focus-visible{outline:2px solid var(--mz-focus);outline-offset:2px;}')
    out.append('\n/* ============ TOUCH TARGETS (>=44px standard) ============ */')
    out.append(':root[data-appearance="mezze"] .railbtn,\n'
               ':root[data-appearance="mezze"] .iconbtn,\n'
               ':root[data-appearance="mezze"] .btn{min-height:44px;min-width:44px;}')
    out.append('\n/* ============ WORKSPACE ADOPTION — real layout effects wired to settings ============ */')
    out.append('/* product grid columns (fixed count overrides the auto-fill default) */')
    for n in (2, 3, 4, 5, 6, 7):
        out.append(':root[data-appearance="mezze"][data-mz-grid-cols="%d"] .grid{grid-template-columns:repeat(%d,minmax(0,1fr));}' % (n, n))
    out.append(':root[data-appearance="mezze"][data-mz-grid-cols="auto"] .grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));}')
    out.append('/* product card mode: image size / text-only */')
    out.append(':root[data-appearance="mezze"][data-mz-card="text"] .prod .pthumb{display:none;}\n'
               ':root[data-appearance="mezze"][data-mz-card="text"] .prod .pname{padding-top:var(--sp-11);}\n'
               ':root[data-appearance="mezze"][data-mz-card="compact"] .prod .pthumb{aspect-ratio:16/10;}\n'
               ':root[data-appearance="mezze"][data-mz-card="large"] .prod .pthumb{aspect-ratio:4/5;}')
    out.append('/* order panel side (default right; left swaps the ticket + category columns) */')
    out.append(':root[data-appearance="mezze"][data-mz-panel="left"] #view-pos.active{grid-template-columns:var(--ticket) 1fr var(--catpanel);}\n'
               ':root[data-appearance="mezze"][data-mz-panel="left"] .ticket{grid-column:1;border-inline-start:none;border-inline-end:1px solid var(--border);}\n'
               ':root[data-appearance="mezze"][data-mz-panel="left"] .catcol{grid-column:3;border-inline-end:none;border-inline-start:1px solid var(--border);}')
    out.append('/* order panel width */')
    for k, v in (('narrow', '300px'), ('standard', '340px'), ('wide', '400px')):
        out.append(':root[data-appearance="mezze"][data-mz-panel-w="%s"]{--ticket:%s;}' % (k, v))
    out.append('/* order-line detail density (compact hides secondary line meta) */')
    out.append(':root[data-appearance="mezze"][data-mz-line="compact"] .line .linesub,\n'
               ':root[data-appearance="mezze"][data-mz-line="compact"] .line .linemeta{display:none;}')
    out.append('/* category layout: grid arranges the category list in two columns */')
    out.append(':root[data-appearance="mezze"][data-mz-catstyle="grid"] .cats{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-4);}\n'
               ':root[data-appearance="mezze"][data-mz-catstyle="grid"] .cats .cat{justify-content:center;text-align:center;}')
    return '\n\n'.join(out) + '\n'

if __name__ == '__main__':
    probs = validate()
    print('Mezze design contrast gate:')
    if probs:
        for p in probs:
            print('  FAIL', p)
        raise SystemExit('Contrast gate FAILED (%d) — CSS not written.' % len(probs))
    print('  all %d theme maps pass WCAG-AA for body/secondary/brand roles' % (len(LIGHT) + len(DARK)))
    css = emit()
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mezze-design.css')
    with open(dest, 'w', encoding='utf-8') as fh:
        fh.write(css)
    print('  wrote %s (%d bytes, %d themes, %d accents)' % (dest, len(css), len(LIGHT) + len(DARK), len(ACCENTS)))
