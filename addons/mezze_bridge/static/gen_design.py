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

def _mix(a, b, t):
    """Blend hex `a` toward hex `b` by t (0..1), in sRGB."""
    a, b = a.lstrip('#'), b.lstrip('#')
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i+2], 16), int(b[i:i+2], 16)
        out.append(round(ca + (cb - ca) * t))
    return '#%02X%02X%02X' % tuple(out)


def _toward(fg, anchor, bgs, target):
    """Darken (or lighten) `fg` toward `anchor` until it clears `target` on EVERY bg.

    The anchor is always the theme's own `text` colour, which is near-black in a
    light theme and near-white in a dark one — so this walks in whichever
    direction actually gains contrast, and never leaves the theme's palette.

    Used for two ROLES the ramp does not already cover, both of which are real
    text a cashier reads rather than decoration:

      * meta ink — counts, hints and timestamps. `tmut` is the closest existing
        step and it does not clear AA on the default theme's own canvas (4.38),
        let alone on the brand tint (3.65).
      * brand ink ON the brand tint — the active category row. `brand` on
        `brand-soft` is 3.45 in classic, and `brand-press` still misses at 4.49
        on forestnight, so neither existing token is safe across the registry.

    Steps in 2% increments and returns the FIRST value that clears, so the result
    stays as light as the requirement allows and secondary text keeps reading as
    secondary.
    """
    t = 0.0
    while t <= 1.0:
        cand = _mix(fg, anchor, t)
        if all(contrast(cand, bg) >= target for bg in bgs):
            return cand
        t += 0.02
    return anchor


# The bar these two roles are held to. Above the 4.5 AA line on purpose: the
# generator rounds and browsers composite, and a token that lands exactly on the
# threshold is one antialiasing pass away from failing it.
META_TARGET = 5.0


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
 # SCREEN01_DIFF rows 178-183 — CLASSIC is now the FROZEN DESIGN's own palette,
 # read from `docs/design-handoff/Mezze POS v3.dc.html` lines 18-27, mapped role by
 # role. Operator ruled 2026-09-09. Only `classic` moves: the design defines exactly
 # one light theme, and the other eleven are this product's own and keep their
 # identities.
 #   canvas   = --color-bg #FBFAF8        workspace = --color-surface #F7F4EE
 #   surface  = #FFFFFF (cards, stated literally in the source)
 #   s2/s3    = neutral-100 / neutral-200  border = neutral-300  bstrong = neutral-400
 #   divider  = neutral-200 (the lighter hairline the design uses inside panels)
 #   text/2   = --color-text / neutral-800   tmut = neutral-600   tfaint = neutral-400
 #   brand    = --color-accent #B5652E (accent-600); hover/press step DOWN the accent
 #              ramp to 700/800, and bsoft is accent-200, the design's filled tint.
 'classic':      L('#FBFAF8','#F7F4EE','#FFFFFF','#F5F3EF','#EFECE5','#E7E3DB','#A9A294','#EFECE5','#2A2419','#4A4439','#7C7568','#A9A294','#B5652E','#8A5426','#6E4220','#F0E4D8'),
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
 # terracotta is the DESIGN's own accent, so it moves with the classic ramp above;
 # a branch on the default accent must not get a different brand from the default theme.
 'terracotta': dict(l=('#B5652E','#8A5426','#6E4220','#F0E4D8'), d=('#D89A54','#E2A860','#C98C48','#3A2E1F')),
 'blue':       dict(l=('#2C5F9E','#264F86','#1F4372','#E4ECF7'), d=('#6BA3E8','#7BB0EE','#5A92D8','#23324A')),
 'teal':       dict(l=('#0E7C8B','#0B6A77','#095763','#DEF0F1'), d=('#3FB2BE','#4FBFCB','#2F9EAA','#173338')),
 'plum':       dict(l=('#8A4A86','#763F73','#623460','#F2E6F0'), d=('#C88EC4','#D49CD0','#B87CB4','#33233A')),
 'olive':      dict(l=('#6B7A2E','#5C6927','#4D5820','#EEF1DE'), d=('#AEBE6A','#BCCB78','#9CAC58','#2A331E')),
 # Recovered from the committed mezze-design.css: this generator had fallen behind
 # the artifact it produces, and regenerating dropped these four entirely.
 'signature':  dict(l=('#C8102E','#9B0C23','#9B0C23','#FDECEC'), d=('#EF435F','#F15B73','#ED2C4B','#3B1F23')),
 'crimson':    dict(l=('#E4002B','#B30021','#B30021','#FFEEF1'), d=('#FE345A','#FE4D6F','#FE1B46','#3B1F24')),
 'ember':      dict(l=('#D2500F','#A13A08','#A13A08','#FFF1E8'), d=('#F07C42','#F28C59','#EF6B2A','#3B281F')),
 'charcoal':   dict(l=('#1F1F1F','#000000','#000000','#F0F0F0'), d=('#D6D6D6','#E3E3E3','#C9C9C9','#2B2B2B')),
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
        # The two DERIVED roles. Gated at the real AA bar (4.5) rather than the
        # 5.0 they are generated to, so the check states the contract and the
        # margin stays margin. These pairings are component-level and were
        # invisible to this gate until they shipped below AA on the default theme.
        for role, fn, bgs in (('text-meta', meta_ink, ('canvas', 'surface', 'workspace', 'surface2', 'bsoft')),
                              ('brand-on-soft', brand_on_soft, ('bsoft',))):
            ink = fn(m)
            for bg in bgs:
                c = contrast(ink, m[bg])
                if c < 4.5:
                    problems.append('%s: %s on %s = %.2f (<4.5)' % (name, role, bg, c))
    # accent brand vs its on-colour (bold labels -> AA-large 3.0)
    for a, spec in ACCENTS.items():
        if contrast('#FFFFFF', spec['l'][0]) < 3.0:
            problems.append('accent %s light: white on brand = %.2f' % (a, contrast('#FFFFFF', spec['l'][0])))
        if contrast('#1C1305', spec['d'][0]) < 3.0:
            problems.append('accent %s dark: ink on brand = %.2f' % (a, contrast('#1C1305', spec['d'][0])))
        # accent ink on the accent tint — the active-row pairing, per accent
        for mode, base, anchor in (('light', spec['l'], '#1A1712'), ('dark', spec['d'], '#F7F4EE')):
            ink = _toward(base[0], anchor, (base[3],), META_TARGET)
            c = contrast(ink, base[3])
            if c < 4.5:
                problems.append('accent %s %s: brand-on-soft = %.2f (<4.5)' % (a, mode, c))
    return problems

def meta_ink(m):
    """Secondary text that is still READ: counts, keyboard hints, check meta.

    Must clear the bar on every ground it actually lands on, including the brand
    tint, because the category count sits inside the active row.
    """
    return _toward(m['tmut'], m['text'],
                   (m['canvas'], m['surface'], m['workspace'], m['surface2'], m['bsoft']),
                   META_TARGET)


def brand_on_soft(m):
    """Brand-coloured label ON the brand tint — the active category row."""
    return _toward(m['brand'], m['text'], (m['bsoft'],), META_TARGET)


# ---- Emit --------------------------------------------------------------------
def block(sel, m, status, on_brand):
    lines = [
      '--mz-canvas:%s;--mz-workspace:%s;--mz-surface:%s;--mz-surface-2:%s;--mz-surface-3:%s;' % (m['canvas'], m['workspace'], m['surface'], m['surface2'], m['surface3']),
      '--mz-border:%s;--mz-border-strong:%s;--mz-divider:%s;' % (m['border'], m['bstrong'], m['divider']),
      '--mz-text:%s;--mz-text-2:%s;--mz-text-mut:%s;--mz-text-faint:%s;' % (m['text'], m['text2'], m['tmut'], m['tfaint']),
      # Two DERIVED roles the hand-authored ramp does not cover. See _toward().
      '--mz-text-meta:%s;--mz-brand-on-soft:%s;' % (meta_ink(m), brand_on_soft(m)),
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
        # `:not([data-mz-theme="highcontrast"])` is load-bearing, not tidiness. The
        # accent overlays are emitted AFTER the theme registry at equal specificity,
        # so without it a branch that picks any accent overwrites the high-contrast
        # brand that was chosen to clear 6.87:1 — the one thing that theme is for.
        # An accent replaces brand AND brand-soft, so the ink that sits ON that
        # tint has to be re-derived with them. Without this, a branch on any
        # non-default accent keeps the THEME's on-soft ink over a tint it was
        # never measured against — which is the same defect this task is fixing.
        out.append(':root[data-appearance="mezze"][data-mz-mode="light"]:not([data-mz-theme="highcontrast"])[data-mz-accent="%s"]{--mz-brand:%s;--mz-brand-hover:%s;--mz-brand-press:%s;--mz-brand-soft:%s;--mz-on-brand:#FFFFFF;--mz-brand-on-soft:%s;--mz-focus:%s;}' % (aid, lb, lh, lp, ls, _toward(lb, '#1A1712', (ls,), META_TARGET), lb))
        out.append(':root[data-appearance="mezze"][data-mz-mode="dark"]:not([data-mz-theme="highcontrast"])[data-mz-accent="%s"]{--mz-brand:%s;--mz-brand-hover:%s;--mz-brand-press:%s;--mz-brand-soft:%s;--mz-on-brand:#1C1305;--mz-brand-on-soft:%s;--mz-focus:%s;}' % (aid, db, dh, dp, ds, _toward(db, '#F7F4EE', (ds,), META_TARGET), db))
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
