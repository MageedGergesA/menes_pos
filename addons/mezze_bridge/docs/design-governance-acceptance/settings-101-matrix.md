# D3 — 101-Setting Coverage Matrix (source: Settings.html)

| # | Stable ID | Section | Type | Default | Status | Runtime consumer / reason | Migrated from |
|---|---|---|---|---|---|---|---|
| 1 | `app_mode` | Appearance | enum | `system` | **working** | data-theme / colour mode | `mode` |
| 2 | `app_theme` | Appearance | enum | `classic` | **working** | light theme | `lightTheme` |
| 3 | `app_dark_theme` | Appearance | enum | `lounge` | **working** | dark theme | `darkTheme` |
| 4 | `app_dim` | Appearance | bool | `false` | **disabled** | Dim dark surfaces — not yet wired to a runtime effect | — |
| 5 | `app_density` | Appearance | enum | `standard` | **working** | data-mz-density | `density` |
| 6 | `app_scale` | Appearance | enum | `100` | **working** | data-mz-scale (zoom) | `uiScale` |
| 7 | `app_radius` | Appearance | enum | `standard` | **disabled** | Corner radius scale — not yet wired | — |
| 8 | `app_motion` | Appearance | enum | `full` | **working** | data-mz-motion | — |
| 9 | `app_accent` | Appearance | enum | `terracotta` | **working** | data-mz-accent | `accent` |
| 10 | `ws_panel_side` | Workspace | enum | `right` | **working** | data-mz-panel | `panelSide` |
| 11 | `ws_panel_width` | Workspace | enum | `standard` | **working** | data-mz-panel-w | `panelWidth` |
| 12 | `ws_nav_labels` | Workspace | enum | `labels` | **working** | rail label visibility | `navLabels` |
| 13 | `ws_collapse_cat` | Workspace | bool | `false` | **disabled** | Collapsible category rail — not yet wired | — |
| 14 | `ws_landing` | Workspace | enum | `pos` | **working** | landing workspace | `landingView` |
| 15 | `ws_default_order` | Workspace | enum | `dinein` | **disabled** | Default order type — set by service flow, not a pref yet | — |
| 16 | `ws_restore` | Workspace | bool | `true` | **disabled** | Restore last workspace on reload — not yet wired | — |
| 17 | `ws_clock` | Workspace | bool | `true` | **disabled** | Show shift clock in shell — not yet wired | — |
| 18 | `ws_conn` | Workspace | bool | `true` | **disabled** | Show connection indicator — always shown for safety | — |
| 19 | `gr_cols_mode` | Product Grid | enum | `auto` | **working** | data-mz-grid-cols auto vs fixed | `gridCols` |
| 20 | `gr_cols` | Product Grid | int | `4` | **working** | data-mz-grid-cols fixed count | `gridCols` |
| 21 | `gr_gap` | Product Grid | enum | `standard` | **disabled** | Grid gap — density already governs spacing | — |
| 22 | `gr_sort` | Product Grid | enum | `menu` | **disabled** | Product sort — not yet wired | — |
| 23 | `gr_group_cat` | Product Grid | bool | `false` | **disabled** | Group grid by category — not yet wired | — |
| 24 | `gr_hide_86` | Product Grid | bool | `false` | **disabled** | 86 items shown struck-through by policy — toggle not wired | — |
| 25 | `gr_page` | Product Grid | bool | `false` | **disabled** | Paginate grid — grid scrolls today | — |
| 26 | `gr_sticky_cat` | Product Grid | bool | `true` | **disabled** | Sticky category header — not yet wired | — |
| 27 | `cd_img` | Product Cards | enum | `standard` | **working** | data-mz-card image mode | `cardMode` |
| 28 | `cd_ratio` | Product Cards | enum | `square` | **disabled** | Card image ratio — card mode governs today | — |
| 29 | `cd_lazy` | Product Cards | bool | `true` | **disabled** | Lazy image loading — images already lazy | — |
| 30 | `cd_price` | Product Cards | bool | `true` | **disabled** | Show price on card — always shown | — |
| 31 | `cd_add` | Product Cards | bool | `true` | **disabled** | Show quick-add affordance — always shown | — |
| 32 | `cd_tags` | Product Cards | bool | `true` | **disabled** | Show dietary/86 tags — always shown | — |
| 33 | `cd_desc` | Product Cards | bool | `false` | **disabled** | Show description on card — not yet wired | — |
| 34 | `cd_name_lines` | Product Cards | int | `2` | **disabled** | Product name line clamp — fixed at 2 today | — |
| 35 | `or_qty` | Order Panel | enum | `stepper` | **disabled** | Quantity control style — stepper today | — |
| 36 | `or_mods` | Order Panel | bool | `true` | **disabled** | Show modifiers on lines — always shown | — |
| 37 | `or_group_course` | Order Panel | bool | `true` | **disabled** | Group order lines by course — not yet wired | — |
| 38 | `or_seat` | Order Panel | bool | `false` | **disabled** | Seat labels on lines — seat model not durable (see R1) | — |
| 39 | `or_newest` | Order Panel | bool | `false` | **disabled** | Newest line first — oldest-first today | — |
| 40 | `or_tax_break` | Order Panel | bool | `true` | **disabled** | DISPLAY of tax breakdown — never removes tax from totals | — |
| 41 | `or_item_count` | Order Panel | bool | `true` | **disabled** | Show item count — always shown | — |
| 42 | `or_tip` | Order Panel | bool | `true` | **disabled** | Show tip control — governed by payment config | — |
| 43 | `or_pay_default` | Order Panel | enum | `card` | **disabled** | Default tender DISPLAY — never bypasses payment config | — |
| 44 | `or_confirm_void` | Order Panel | bool | `true` | **disabled** | Confirm before void — approval governed by role, not this pref | — |
| 45 | `or_print` | Order Panel | enum | `ask` | **disabled** | Receipt print PROMPT — never bypasses printer policy | — |
| 46 | `se_focus_slash` | Search | bool | `true` | **disabled** | Focus search on "/" — not yet wired | — |
| 47 | `se_enter_add` | Search | bool | `true` | **disabled** | Enter adds top result — not yet wired | — |
| 48 | `se_debounce` | Search | int | `200` | **disabled** | Search debounce ms — fixed today | — |
| 49 | `se_clear` | Search | bool | `true` | **disabled** | Clear search after add — not yet wired | — |
| 50 | `se_scope` | Search | enum | `all` | **disabled** | Search scope — searches all today | — |
| 51 | `se_arabic` | Search | bool | `true` | **disabled** | Arabic-insensitive matching — server search handles this | — |
| 52 | `se_fuzzy` | Search | bool | `true` | **disabled** | Fuzzy matching — not yet wired | — |
| 53 | `se_barcode` | Search | bool | `true` | **disabled** | Barcode/SKU search — scan handled by scanner input | — |
| 54 | `ca_counts` | Categories | bool | `true` | **disabled** | Show item counts on categories — not yet wired | — |
| 55 | `ca_icons` | Categories | bool | `true` | **disabled** | Show category icons — not yet wired | — |
| 56 | `ca_order` | Categories | enum | `menu` | **disabled** | Category order — menu order today | — |
| 57 | `ca_all` | Categories | bool | `true` | **disabled** | Show "All" category — always shown | — |
| 58 | `ca_numkeys` | Categories | bool | `false` | **disabled** | Number-key category switch — not yet wired | — |
| 59 | `ca_remember` | Categories | bool | `true` | **disabled** | Remember last category — not yet wired | — |
| 60 | `fa_enable` | Favorites | bool | `false` | **disabled** | Enable favorites row — not yet wired | — |
| 61 | `fa_count` | Favorites | int | `12` | **disabled** | Favorites count — not yet wired | — |
| 62 | `fa_source` | Favorites | enum | `popular` | **disabled** | Favorites source — not yet wired | — |
| 63 | `fa_long` | Favorites | bool | `true` | **disabled** | Long-press to favorite — not yet wired | — |
| 64 | `fa_shift` | Favorites | bool | `false` | **disabled** | Favorites shift on use — not yet wired | — |
| 65 | `qa_hold` | Quick Actions | bool | `true` | **disabled** | Show Hold quick action — always shown | — |
| 66 | `qa_discount` | Quick Actions | bool | `true` | **disabled** | Show Discount action — permission-governed, not this pref | — |
| 67 | `qa_note` | Quick Actions | bool | `true` | **disabled** | Show Note action — always shown | — |
| 68 | `qa_split` | Quick Actions | bool | `true` | **disabled** | Show Split action — always shown | — |
| 69 | `qa_reprint` | Quick Actions | bool | `true` | **disabled** | Show Reprint action — permission-governed | — |
| 70 | `qa_pos` | Quick Actions | bool | `true` | **disabled** | Show POS action — always shown | — |
| 71 | `qa_confirm` | Quick Actions | bool | `true` | **disabled** | Confirm destructive quick actions — governed by role | — |
| 72 | `kb_search` | Keyboard | key | `/` | **disabled** | Search shortcut — fixed binding today | — |
| 73 | `kb_pay` | Keyboard | key | `F2` | **disabled** | Pay shortcut — fixed binding today | — |
| 74 | `kb_hold` | Keyboard | key | `F3` | **disabled** | Hold shortcut — fixed binding today | — |
| 75 | `kb_new` | Keyboard | key | `F4` | **disabled** | New order shortcut — fixed binding today | — |
| 76 | `kb_cat` | Keyboard | key | `1-9` | **disabled** | Category number keys — fixed binding today | — |
| 77 | `kb_qty` | Keyboard | key | `*` | **disabled** | Quantity shortcut — fixed binding today | — |
| 78 | `kb_del` | Keyboard | key | `Del` | **disabled** | Delete-line shortcut — fixed binding today | — |
| 79 | `kb_enable` | Keyboard | bool | `true` | **disabled** | Enable keyboard shortcuts — always on today | — |
| 80 | `ac_text` | Accessibility | enum | `default` | **disabled** | Text size — UI scale governs today | — |
| 81 | `ac_contrast` | Accessibility | bool | `false` | **working** | high-contrast theme | `highContrast` |
| 82 | `ac_bold` | Accessibility | bool | `false` | **disabled** | Bold text — not yet wired | — |
| 83 | `ac_focus` | Accessibility | bool | `true` | **working** | strong focus ring | `focusRing` |
| 84 | `ac_reduce` | Accessibility | bool | `false` | **working** | data-mz-motion reduced | `reduceMotion` |
| 85 | `ac_touch` | Accessibility | bool | `false` | **disabled** | Larger touch targets — 44px floor already enforced | — |
| 86 | `ac_haptics` | Accessibility | bool | `false` | **disabled** | Haptic feedback — device-dependent, not wired | — |
| 87 | `ac_dir` | Accessibility | enum | `auto` | **working** | reading direction (dir) | `direction` |
| 88 | `pf_virtual` | Performance | bool | `false` | **hidden** | List virtualization — engineering-controlled | — |
| 89 | `pf_img_q` | Performance | enum | `standard` | **disabled** | Image quality — not yet wired | — |
| 90 | `pf_prefetch` | Performance | bool | `true` | **disabled** | Prefetch menu — always on today | — |
| 91 | `pf_anim_low` | Performance | bool | `false` | **disabled** | Low-power animations — reduce-motion covers this | — |
| 92 | `pf_sync` | Performance | enum | `realtime` | **disabled** | Sync cadence — realtime by architecture | — |
| 93 | `pf_offline` | Performance | bool | `true` | **disabled** | Offline mode — always available by architecture | — |
| 94 | `pf_cache` | Performance | bool | `true` | **hidden** | Local cache — engineering-controlled | — |
| 95 | `ad_sync_settings` | Advanced | bool | `true` | **disabled** | Sync settings across my devices — user scope follows user by default | — |
| 96 | `ad_layer` | Advanced | bool | `false` | **hidden** | Layer inspector — engineering only | — |
| 97 | `ad_beta` | Advanced | bool | `false` | **hidden** | Beta features — not exposed to users | — |
| 98 | `ad_debug` | Advanced | bool | `false` | **hidden** | Debug mode — engineering only | — |
| 99 | `ad_grid` | Advanced | bool | `false` | **hidden** | Grid overlay — engineering only | — |
| 100 | `ad_log` | Advanced | enum | `off` | **hidden** | Client log level — engineering only | — |
| 101 | `ad_analytics` | Advanced | bool | `true` | **disabled** | Usage analytics — governed by org policy, not a personal toggle yet | — |

**Totals:** 101 settings — 18 Working, 76 Disabled, 7 Hidden across 13 sections.