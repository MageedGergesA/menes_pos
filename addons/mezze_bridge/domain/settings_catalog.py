"""D3 — the AUTHORITATIVE 101-setting catalog from ``Settings.html`` (13 sections).

Single source of truth for the setting IDs, types, defaults, allowed values and —
critically — each setting's honest STATUS: ``working`` (changes real runtime
behaviour, wired to a runtime consumer), ``disabled`` (shown read-only with an
accurate reason; never persists a no-effect value), or ``hidden`` (not presented
until implemented). ``old_id`` maps a pre-D3 engine key onto its stable ID for the
idempotent migration. This module is imported by the model catalog and exported to
the front-end so the running app and the server agree on every id.
"""

# (id, section, type, default, opts_or_range, status, consumer|reason, old_id)
#   type: enum | bool | int | key
#   status: working | disabled | hidden
CATALOG_101 = [
    # ---- Appearance (9) ----
    ('app_mode', 'Appearance', 'enum', 'system', 'system,light,dark', 'working', 'data-theme / colour mode', 'mode'),
    ('app_theme', 'Appearance', 'enum', 'classic', 'classic,corporate,coastal,forest,coffeehouse,highcontrast', 'working', 'light theme', 'lightTheme'),
    ('app_dark_theme', 'Appearance', 'enum', 'lounge', 'midnight,lounge,graphite,forestnight,slate,highcontrast', 'working', 'dark theme', 'darkTheme'),
    ('app_dim', 'Appearance', 'bool', 'false', '', 'disabled', 'Dim dark surfaces — not yet wired to a runtime effect', None),
    ('app_density', 'Appearance', 'enum', 'standard', 'compact,standard,comfortable', 'working', 'data-mz-density', 'density'),
    ('app_scale', 'Appearance', 'enum', '100', '80,90,100,110,120,140', 'working', 'data-mz-scale (zoom)', 'uiScale'),
    ('app_radius', 'Appearance', 'enum', 'standard', 'sharp,standard,round', 'disabled', 'Corner radius scale — not yet wired', None),
    ('app_motion', 'Appearance', 'enum', 'full', 'full,reduced', 'working', 'data-mz-motion', None),
    ('app_accent', 'Appearance', 'enum', 'terracotta', 'terracotta,blue,teal,plum,olive', 'working', 'data-mz-accent', 'accent'),
    # ---- Workspace (9) ----
    ('ws_panel_side', 'Workspace', 'enum', 'right', 'right,left', 'working', 'data-mz-panel', 'panelSide'),
    ('ws_panel_width', 'Workspace', 'enum', 'standard', 'narrow,standard,wide', 'working', 'data-mz-panel-w', 'panelWidth'),
    ('ws_nav_labels', 'Workspace', 'enum', 'labels', 'labels,icons', 'working', 'rail label visibility', 'navLabels'),
    ('ws_collapse_cat', 'Workspace', 'bool', 'false', '', 'disabled', 'Collapsible category rail — not yet wired', None),
    ('ws_landing', 'Workspace', 'enum', 'pos', 'pos,floor,kds,manager,reports', 'working', 'landing workspace', 'landingView'),
    ('ws_default_order', 'Workspace', 'enum', 'dinein', 'dinein,takeaway,delivery', 'disabled', 'Default order type — set by service flow, not a pref yet', None),
    ('ws_restore', 'Workspace', 'bool', 'true', '', 'disabled', 'Restore last workspace on reload — not yet wired', None),
    ('ws_clock', 'Workspace', 'bool', 'true', '', 'disabled', 'Show shift clock in shell — not yet wired', None),
    ('ws_conn', 'Workspace', 'bool', 'true', '', 'disabled', 'Show connection indicator — always shown for safety', None),
    # ---- Product Grid (8) ----
    ('gr_cols_mode', 'Product Grid', 'enum', 'auto', 'auto,fixed', 'working', 'data-mz-grid-cols auto vs fixed', 'gridCols'),
    ('gr_cols', 'Product Grid', 'int', '4', '2..8', 'working', 'data-mz-grid-cols fixed count', 'gridCols'),
    ('gr_gap', 'Product Grid', 'enum', 'standard', 'tight,standard,roomy', 'disabled', 'Grid gap — density already governs spacing', None),
    ('gr_sort', 'Product Grid', 'enum', 'menu', 'menu,name,price,popular', 'disabled', 'Product sort — not yet wired', None),
    ('gr_group_cat', 'Product Grid', 'bool', 'false', '', 'disabled', 'Group grid by category — not yet wired', None),
    ('gr_hide_86', 'Product Grid', 'bool', 'false', '', 'disabled', '86 items shown struck-through by policy — toggle not wired', None),
    ('gr_page', 'Product Grid', 'bool', 'false', '', 'disabled', 'Paginate grid — grid scrolls today', None),
    ('gr_sticky_cat', 'Product Grid', 'bool', 'true', '', 'disabled', 'Sticky category header — not yet wired', None),
    # ---- Product Cards (8) ----
    ('cd_img', 'Product Cards', 'enum', 'standard', 'text,compact,standard,large', 'working', 'data-mz-card image mode', 'cardMode'),
    ('cd_ratio', 'Product Cards', 'enum', 'square', 'square,wide,tall', 'disabled', 'Card image ratio — card mode governs today', None),
    ('cd_lazy', 'Product Cards', 'bool', 'true', '', 'disabled', 'Lazy image loading — images already lazy', None),
    ('cd_price', 'Product Cards', 'bool', 'true', '', 'disabled', 'Show price on card — always shown', None),
    ('cd_add', 'Product Cards', 'bool', 'true', '', 'disabled', 'Show quick-add affordance — always shown', None),
    ('cd_tags', 'Product Cards', 'bool', 'true', '', 'disabled', 'Show dietary/86 tags — always shown', None),
    ('cd_desc', 'Product Cards', 'bool', 'false', '', 'disabled', 'Show description on card — not yet wired', None),
    ('cd_name_lines', 'Product Cards', 'int', '2', '1..3', 'disabled', 'Product name line clamp — fixed at 2 today', None),
    # ---- Order Panel (11) ----
    ('or_qty', 'Order Panel', 'enum', 'stepper', 'stepper,tap', 'disabled', 'Quantity control style — stepper today', None),
    ('or_mods', 'Order Panel', 'bool', 'true', '', 'disabled', 'Show modifiers on lines — always shown', None),
    ('or_group_course', 'Order Panel', 'bool', 'true', '', 'disabled', 'Group order lines by course — not yet wired', None),
    ('or_seat', 'Order Panel', 'bool', 'false', '', 'disabled', 'Seat labels on lines — seat model not durable (see R1)', None),
    ('or_newest', 'Order Panel', 'bool', 'false', '', 'disabled', 'Newest line first — oldest-first today', None),
    ('or_tax_break', 'Order Panel', 'bool', 'true', '', 'disabled', 'DISPLAY of tax breakdown — never removes tax from totals', None),
    ('or_item_count', 'Order Panel', 'bool', 'true', '', 'disabled', 'Show item count — always shown', None),
    ('or_tip', 'Order Panel', 'bool', 'true', '', 'disabled', 'Show tip control — governed by payment config', None),
    ('or_pay_default', 'Order Panel', 'enum', 'card', 'cash,card,split', 'disabled', 'Default tender DISPLAY — never bypasses payment config', None),
    ('or_confirm_void', 'Order Panel', 'bool', 'true', '', 'disabled', 'Confirm before void — approval governed by role, not this pref', None),
    ('or_print', 'Order Panel', 'enum', 'ask', 'ask,auto,never', 'disabled', 'Receipt print PROMPT — never bypasses printer policy', None),
    # ---- Search (8) ----
    ('se_focus_slash', 'Search', 'bool', 'true', '', 'disabled', 'Focus search on "/" — not yet wired', None),
    ('se_enter_add', 'Search', 'bool', 'true', '', 'disabled', 'Enter adds top result — not yet wired', None),
    ('se_debounce', 'Search', 'int', '200', '0..500', 'disabled', 'Search debounce ms — fixed today', None),
    ('se_clear', 'Search', 'bool', 'true', '', 'disabled', 'Clear search after add — not yet wired', None),
    ('se_scope', 'Search', 'enum', 'all', 'all,category,menu', 'disabled', 'Search scope — searches all today', None),
    ('se_arabic', 'Search', 'bool', 'true', '', 'disabled', 'Arabic-insensitive matching — server search handles this', None),
    ('se_fuzzy', 'Search', 'bool', 'true', '', 'disabled', 'Fuzzy matching — not yet wired', None),
    ('se_barcode', 'Search', 'bool', 'true', '', 'disabled', 'Barcode/SKU search — scan handled by scanner input', None),
    # ---- Categories (6) ----
    ('ca_counts', 'Categories', 'bool', 'true', '', 'disabled', 'Show item counts on categories — not yet wired', None),
    ('ca_icons', 'Categories', 'bool', 'true', '', 'disabled', 'Show category icons — not yet wired', None),
    ('ca_order', 'Categories', 'enum', 'menu', 'menu,alpha,custom', 'disabled', 'Category order — menu order today', None),
    ('ca_all', 'Categories', 'bool', 'true', '', 'disabled', 'Show "All" category — always shown', None),
    ('ca_numkeys', 'Categories', 'bool', 'false', '', 'disabled', 'Number-key category switch — not yet wired', None),
    ('ca_remember', 'Categories', 'bool', 'true', '', 'disabled', 'Remember last category — not yet wired', None),
    # ---- Favorites (5) ----
    ('fa_enable', 'Favorites', 'bool', 'false', '', 'disabled', 'Enable favorites row — not yet wired', None),
    ('fa_count', 'Favorites', 'int', '12', '4..24', 'disabled', 'Favorites count — not yet wired', None),
    ('fa_source', 'Favorites', 'enum', 'popular', 'manual,auto,popular', 'disabled', 'Favorites source — not yet wired', None),
    ('fa_long', 'Favorites', 'bool', 'true', '', 'disabled', 'Long-press to favorite — not yet wired', None),
    ('fa_shift', 'Favorites', 'bool', 'false', '', 'disabled', 'Favorites shift on use — not yet wired', None),
    # ---- Quick Actions (7) ----
    ('qa_hold', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show Hold quick action — always shown', None),
    ('qa_discount', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show Discount action — permission-governed, not this pref', None),
    ('qa_note', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show Note action — always shown', None),
    ('qa_split', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show Split action — always shown', None),
    ('qa_reprint', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show Reprint action — permission-governed', None),
    ('qa_pos', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Show POS action — always shown', None),
    ('qa_confirm', 'Quick Actions', 'bool', 'true', '', 'disabled', 'Confirm destructive quick actions — governed by role', None),
    # ---- Keyboard (8) — shortcut bindings, shown read-only until the keymap is user-editable ----
    ('kb_search', 'Keyboard', 'key', '/', '', 'disabled', 'Search shortcut — fixed binding today', None),
    ('kb_pay', 'Keyboard', 'key', 'F2', '', 'disabled', 'Pay shortcut — fixed binding today', None),
    ('kb_hold', 'Keyboard', 'key', 'F3', '', 'disabled', 'Hold shortcut — fixed binding today', None),
    ('kb_new', 'Keyboard', 'key', 'F4', '', 'disabled', 'New order shortcut — fixed binding today', None),
    ('kb_cat', 'Keyboard', 'key', '1-9', '', 'disabled', 'Category number keys — fixed binding today', None),
    ('kb_qty', 'Keyboard', 'key', '*', '', 'disabled', 'Quantity shortcut — fixed binding today', None),
    ('kb_del', 'Keyboard', 'key', 'Del', '', 'disabled', 'Delete-line shortcut — fixed binding today', None),
    ('kb_enable', 'Keyboard', 'bool', 'true', '', 'disabled', 'Enable keyboard shortcuts — always on today', None),
    # ---- Accessibility (8) ----
    ('ac_text', 'Accessibility', 'enum', 'default', 'default,large,xlarge', 'disabled', 'Text size — UI scale governs today', None),
    ('ac_contrast', 'Accessibility', 'bool', 'false', '', 'working', 'high-contrast theme', 'highContrast'),
    ('ac_bold', 'Accessibility', 'bool', 'false', '', 'disabled', 'Bold text — not yet wired', None),
    ('ac_focus', 'Accessibility', 'bool', 'true', '', 'working', 'strong focus ring', 'focusRing'),
    ('ac_reduce', 'Accessibility', 'bool', 'false', '', 'working', 'data-mz-motion reduced', 'reduceMotion'),
    ('ac_touch', 'Accessibility', 'bool', 'false', '', 'disabled', 'Larger touch targets — 44px floor already enforced', None),
    ('ac_haptics', 'Accessibility', 'bool', 'false', '', 'disabled', 'Haptic feedback — device-dependent, not wired', None),
    ('ac_dir', 'Accessibility', 'enum', 'auto', 'auto,ltr,rtl', 'working', 'reading direction (dir)', 'direction'),
    # ---- Performance (7) ----
    ('pf_virtual', 'Performance', 'bool', 'false', '', 'hidden', 'List virtualization — engineering-controlled', None),
    ('pf_img_q', 'Performance', 'enum', 'standard', 'low,standard,high', 'disabled', 'Image quality — not yet wired', None),
    ('pf_prefetch', 'Performance', 'bool', 'true', '', 'disabled', 'Prefetch menu — always on today', None),
    ('pf_anim_low', 'Performance', 'bool', 'false', '', 'disabled', 'Low-power animations — reduce-motion covers this', None),
    ('pf_sync', 'Performance', 'enum', 'realtime', 'realtime,periodic,manual', 'disabled', 'Sync cadence — realtime by architecture', None),
    ('pf_offline', 'Performance', 'bool', 'true', '', 'disabled', 'Offline mode — always available by architecture', None),
    ('pf_cache', 'Performance', 'bool', 'true', '', 'hidden', 'Local cache — engineering-controlled', None),
    # ---- Advanced (7) ----
    ('ad_sync_settings', 'Advanced', 'bool', 'true', '', 'disabled', 'Sync settings across my devices — user scope follows user by default', None),
    ('ad_layer', 'Advanced', 'bool', 'false', '', 'hidden', 'Layer inspector — engineering only', None),
    ('ad_beta', 'Advanced', 'bool', 'false', '', 'hidden', 'Beta features — not exposed to users', None),
    ('ad_debug', 'Advanced', 'bool', 'false', '', 'hidden', 'Debug mode — engineering only', None),
    ('ad_grid', 'Advanced', 'bool', 'false', '', 'hidden', 'Grid overlay — engineering only', None),
    ('ad_log', 'Advanced', 'enum', 'off', 'off,error,verbose', 'hidden', 'Client log level — engineering only', None),
    ('ad_analytics', 'Advanced', 'bool', 'true', '', 'disabled', 'Usage analytics — governed by org policy, not a personal toggle yet', None),
]

SECTION_ORDER = ['Appearance', 'Workspace', 'Product Grid', 'Product Cards', 'Order Panel',
                 'Search', 'Categories', 'Favorites', 'Quick Actions', 'Keyboard',
                 'Accessibility', 'Performance', 'Advanced']

# migration: pre-D3 engine key -> stable D3 id
MIGRATION_MAP = {c[7]: c[0] for c in CATALOG_101 if c[7]}
# add the composite gridCols split explicitly (auto -> gr_cols_mode; N -> gr_cols)
MIGRATION_MAP['gridCols'] = 'gr_cols_mode'

STATUS = {c[0]: c[5] for c in CATALOG_101}
WORKING = [c[0] for c in CATALOG_101 if c[5] == 'working']
DISABLED = [c[0] for c in CATALOG_101 if c[5] == 'disabled']
HIDDEN = [c[0] for c in CATALOG_101 if c[5] == 'hidden']


def as_rows():
    """(key, category, value_type, default, options_csv, effect, status, reason, old_id)."""
    out = []
    for cid, sec, typ, dv, opts, status, reason, old in CATALOG_101:
        # int ranges are stored as "min..max" in options; enums as csv
        out.append((cid, sec, typ, dv, opts, ('live' if status == 'working' else 'pref'),
                    status, reason, old))
    return out


assert len({c[0] for c in CATALOG_101}) == 101, "catalog must hold exactly 101 unique ids"
