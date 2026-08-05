/* mezze-design.js — Mezze Design Platform runtime engine (D1).
 *
 * Responsibilities:
 *  - Default the app to the approved Mezze appearance + apply the resolved
 *    presentation settings (mode/theme/accent/density/scale/direction/motion and
 *    the workspace layout settings) onto <html> data-* attributes. No reload.
 *  - Own the approved THEME REGISTRY: only registry ids may activate; arbitrary
 *    user colours are impossible (there is no colour input, and setTheme rejects
 *    anything not in the registry).
 *  - Resolve effective settings via the backend cascade
 *    (platform->org->brand->branch->role->user->device) with provenance, cache
 *    them to localStorage for offline terminals, and persist user overrides.
 *  - Render the User Settings workspace and the Admin Console workspace as real
 *    in-shell screens (#view-settings / #view-admin).
 *
 * Exposes window.MezzeDesign. Safe to load after the host app; self-mounts.
 */
(function () {
  'use strict';

  // ---- approved registry (mirrors mezze-design.css; the CSS is the source of the maps) ----
  var LIGHT_THEMES = [
    { id: 'classic', label: 'Mezze Classic' }, { id: 'corporate', label: 'Corporate' },
    { id: 'coastal', label: 'Coastal' }, { id: 'forest', label: 'Forest' },
    { id: 'coffeehouse', label: 'Coffee House' }, { id: 'highcontrast', label: 'High Contrast' }
  ];
  var DARK_THEMES = [
    { id: 'midnight', label: 'Midnight' }, { id: 'lounge', label: 'Lounge' },
    { id: 'graphite', label: 'Graphite' }, { id: 'forestnight', label: 'Forest Night' },
    { id: 'slate', label: 'Slate' }, { id: 'highcontrast', label: 'High Contrast' }
  ];
  var ACCENTS = [
    { id: 'terracotta', label: 'Terracotta' }, { id: 'blue', label: 'Blue' },
    { id: 'teal', label: 'Teal' }, { id: 'plum', label: 'Plum' }, { id: 'olive', label: 'Olive' }
  ];
  var LIGHT_IDS = LIGHT_THEMES.map(function (t) { return t.id; });
  var DARK_IDS = DARK_THEMES.map(function (t) { return t.id; });
  var ACCENT_IDS = ACCENTS.map(function (a) { return a.id; });

  // ---- D3: the AUTHORITATIVE catalog is the backend's 101-setting source of truth
  //      (Settings.html), fetched into state.catalog with per-setting status
  //      (working|disabled|hidden). This local WORKING map holds only the 18 settings
  //      with a real runtime effect — used for apply() and offline defaults. The
  //      Settings UI renders every section from state.catalog. ----
  var WORKING = {
    app_mode:       { type: 'enum', def: 'system', options: ['system', 'light', 'dark'], label: 'Colour mode' },
    app_theme:      { type: 'enum', def: 'classic', options: LIGHT_IDS, label: 'Light theme' },
    app_dark_theme: { type: 'enum', def: 'lounge', options: DARK_IDS, label: 'Dark theme' },
    app_accent:     { type: 'enum', def: 'terracotta', options: ACCENT_IDS, label: 'Accent palette' },
    app_density:    { type: 'enum', def: 'standard', options: ['compact', 'standard', 'comfortable'], label: 'Density' },
    app_scale:      { type: 'enum', def: '100', options: ['80', '90', '100', '110', '120', '140'], label: 'UI scale' },
    app_motion:     { type: 'enum', def: 'full', options: ['full', 'reduced'], label: 'Motion' },
    ws_nav_labels:  { type: 'enum', def: 'labels', options: ['labels', 'icons'], label: 'Navigation labels' },
    ws_landing:     { type: 'enum', def: 'pos', options: ['pos', 'floor', 'kds', 'manager', 'reports'], label: 'Landing screen' },
    ws_panel_side:  { type: 'enum', def: 'right', options: ['right', 'left'], label: 'Panel side' },
    ws_panel_width: { type: 'enum', def: 'standard', options: ['narrow', 'standard', 'wide'], label: 'Panel width' },
    gr_cols_mode:   { type: 'enum', def: 'auto', options: ['auto', 'fixed'], label: 'Grid columns mode' },
    gr_cols:        { type: 'int', def: '4', min: 2, max: 8, label: 'Grid columns' },
    cd_img:         { type: 'enum', def: 'standard', options: ['text', 'compact', 'standard', 'large'], label: 'Card style' },
    ac_contrast:    { type: 'bool', def: false, label: 'High contrast' },
    ac_focus:       { type: 'bool', def: true, label: 'Strong focus ring' },
    ac_reduce:      { type: 'bool', def: false, label: 'Reduce motion' },
    ac_dir:         { type: 'enum', def: 'auto', options: ['auto', 'ltr', 'rtl'], label: 'Reading direction' }
  };
  // pre-D3 engine key -> stable id (localStorage migration)
  var MIGRATE = { mode: 'app_mode', lightTheme: 'app_theme', darkTheme: 'app_dark_theme',
    accent: 'app_accent', density: 'app_density', uiScale: 'app_scale', navLabels: 'ws_nav_labels',
    landingView: 'ws_landing', panelSide: 'ws_panel_side', panelWidth: 'ws_panel_width',
    cardMode: 'cd_img', highContrast: 'ac_contrast', focusRing: 'ac_focus', direction: 'ac_dir',
    reduceMotion: 'ac_reduce' };
  var SECTION_ORDER = ['Appearance', 'Workspace', 'Product Grid', 'Product Cards', 'Order Panel',
    'Search', 'Categories', 'Favorites', 'Quick Actions', 'Keyboard', 'Accessibility', 'Performance', 'Advanced'];
  var DEF = {};
  var META = {};
  Object.keys(WORKING).forEach(function (id) { DEF[id] = WORKING[id].def; META[id] = WORKING[id]; META[id].id = id; });

  // Build the visible section list from the backend 101-catalog (state.catalog):
  // 'hidden' settings are omitted; 'working' render interactive, 'disabled' read-only.
  function sections() {
    var cat = (state.catalog && Object.keys(state.catalog).length) ? state.catalog : null;
    var out = SECTION_ORDER.map(function (s) { return { cat: s, items: [] }; });
    var byName = {}; out.forEach(function (o) { byName[o.cat] = o; });
    if (cat) {
      Object.keys(cat).forEach(function (id) {
        var d = cat[id];
        if (d.status === 'hidden') return;
        var grp = byName[d.category]; if (!grp) return;
        grp.items.push({ id: id, type: d.type, options: d.options || [], range: d.range || null,
          status: d.status, reason: d.reason || '', label: (WORKING[id] && WORKING[id].label) || id });
      });
    } else {
      Object.keys(WORKING).forEach(function (id) {
        var w = WORKING[id]; var grp = byName[w.category || sectionOfWorking(id)];
        (grp || byName.Appearance).items.push({ id: id, type: w.type, options: w.options || [], status: 'working', reason: '', label: w.label });
      });
    }
    return out.filter(function (o) { return o.items.length; });
  }
  function sectionOfWorking(id) {
    if (id.indexOf('app_') === 0) return 'Appearance';
    if (id.indexOf('ws_') === 0) return 'Workspace';
    if (id.indexOf('gr_') === 0) return 'Product Grid';
    if (id.indexOf('cd_') === 0) return 'Product Cards';
    if (id.indexOf('ac_') === 0) return 'Accessibility';
    return 'Appearance';
  }

  var LS_KEY = 'mzSettings.v1';           // user overrides (offline authority)
  var LS_EFF = 'mzEffective.v1';          // last resolved effective+provenance (offline)
  var LS_LEGACY = 'mzAppearance';         // pre-D1 key we migrate from

  var state = {
    overrides: {},      // user's personal overrides {id: value}
    effective: {},      // resolved effective values {id: value}
    provenance: {},     // {id: {scope, source, lock}}
    locks: {},          // {id: 'free'|'bounded'|'locked'}
    catalog: {},        // D3 backend 101-catalog {id: {status, category, ...}}
    ready: false,
    isAdmin: false,
    adminCaps: []
  };

  // ---- storage helpers ----
  function jget(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function jset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  // ---- token (same convention as pos.html) ----
  function readCookie(n) { var m = document.cookie.match('(^|;)\\s*' + n + '\\s*=\\s*([^;]+)'); return m ? decodeURIComponent(m.pop()) : ''; }
  function token() {
    var q = new URLSearchParams(location.search);
    return q.get('token') || readCookie('mezze_pos_token') || '';
  }
  function apiBase() { var q = new URLSearchParams(location.search); return (q.get('base') || '') + '/mezze/api/v1'; }

  function call(path, body) {
    return fetch(apiBase() + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ token: token() }, body || {}))
    }).then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .catch(function () { return { ok: false, offline: true }; });
  }

  // ---- resolution ----
  function effectiveVal(id) {
    // user override wins unless the setting is locked by a higher scope
    if (state.locks[id] === 'locked') return state.effective[id];
    if (Object.prototype.hasOwnProperty.call(state.overrides, id)) return state.overrides[id];
    if (Object.prototype.hasOwnProperty.call(state.effective, id)) return state.effective[id];
    return DEF[id];
  }
  function isLocked(id) { return state.locks[id] === 'locked'; }

  function resolvedMode() {
    var m = effectiveVal('app_mode');
    if (m === 'system') {
      return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    }
    return m === 'dark' ? 'dark' : 'light';
  }

  function activeTheme(mode) {
    if (effectiveVal('ac_contrast')) return 'highcontrast';
    if (mode === 'dark') { var d = effectiveVal('app_dark_theme'); return DARK_IDS.indexOf(d) >= 0 ? d : 'lounge'; }
    var l = effectiveVal('app_theme'); return LIGHT_IDS.indexOf(l) >= 0 ? l : 'classic';
  }

  function resolvedDirection() {
    var d = effectiveVal('ac_dir');
    if (d === 'ltr' || d === 'rtl') return d;
    // auto: follow document language
    var lang = (document.documentElement.getAttribute('lang') || '').toLowerCase();
    return lang.indexOf('ar') === 0 ? 'rtl' : 'ltr';
  }

  // ---- apply (no reload) ----
  function apply() {
    var el = document.documentElement;
    var mode = resolvedMode();
    var theme = activeTheme(mode);
    el.setAttribute('data-appearance', 'mezze');
    el.setAttribute('data-theme', mode);
    el.setAttribute('data-mz-mode', mode);
    el.setAttribute('data-mz-theme', theme);
    var accent = effectiveVal('app_accent'); if (ACCENT_IDS.indexOf(accent) < 0) accent = 'terracotta';
    el.setAttribute('data-mz-accent', accent);
    el.setAttribute('data-mz-density', effectiveVal('app_density'));
    el.setAttribute('data-mz-scale', effectiveVal('app_scale'));
    // grid columns: mode auto vs a fixed count
    el.setAttribute('data-mz-grid-cols', effectiveVal('gr_cols_mode') === 'fixed' ? String(effectiveVal('gr_cols')) : 'auto');
    el.setAttribute('data-mz-card', effectiveVal('cd_img'));
    el.setAttribute('data-mz-panel', effectiveVal('ws_panel_side'));
    el.setAttribute('data-mz-panel-w', effectiveVal('ws_panel_width'));
    el.setAttribute('data-mz-navlabels', effectiveVal('ws_nav_labels'));
    // direction
    var dir = resolvedDirection();
    el.setAttribute('dir', dir);
    // motion: explicit pref OR system reduced-motion
    var sysReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var motionReduced = effectiveVal('ac_reduce') || effectiveVal('app_motion') === 'reduced' || sysReduced;
    el.setAttribute('data-mz-motion', motionReduced ? 'reduced' : 'full');
    // nav labels: hide the rail text labels when 'icons'
    injectNavLabelCss(effectiveVal('ws_nav_labels'));
    fire('applied', { mode: mode, theme: theme, accent: accent, dir: dir });
  }

  var _navStyle;
  function injectNavLabelCss(mode) {
    if (!_navStyle) { _navStyle = document.createElement('style'); document.head.appendChild(_navStyle); }
    _navStyle.textContent = mode === 'icons'
      ? '[data-appearance="mezze"][data-mz-navlabels="icons"] .rail .rllbl{display:none!important;}'
      : '';
  }

  // ---- events ----
  var listeners = {};
  function on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); }
  function fire(ev, d) { (listeners[ev] || []).forEach(function (fn) { try { fn(d); } catch (e) {} }); }

  // ---- validation: only registry values may be set; arbitrary colours impossible ----
  function validate(id, val) {
    var m = META[id];
    if (!m) return { ok: false, reason: 'unknown_setting' };
    if (m.type === 'bool') return { ok: (val === true || val === false), reason: 'not_bool' };
    if (m.type === 'enum') return { ok: m.options.indexOf(String(val)) >= 0, reason: 'not_in_registry' };
    return { ok: true };
  }

  // ---- public setters ----
  function statusOf(id) {
    if (state.catalog && state.catalog[id]) return state.catalog[id].status || 'working';
    return WORKING[id] ? 'working' : 'disabled';   // offline: only the 18 are working
  }
  function set(id, val, opts) {
    opts = opts || {};
    var v = validate(id, val);
    if (!v.ok) { console.warn('[MezzeDesign] rejected', id, val, v.reason); return false; }
    // D3 — only a 'working' setting may be set. disabled = read-only, hidden = absent;
    // set() refuses non-working ids so no interactive control persists a no-effect value.
    if (statusOf(id) !== 'working') { console.warn('[MezzeDesign] not writable (status):', id); return false; }
    if (isLocked(id)) { console.warn('[MezzeDesign] locked by higher scope:', id); return false; }
    state.overrides[id] = val;
    jset(LS_KEY, state.overrides);
    apply();
    if (!opts.noPersist) call('/settings/save', { values: keyVal(id, val) });
    return true;
  }
  function keyVal(id, val) { var o = {}; o[id] = val; return o; }

  function resetSection(cat) {
    var g = sections().filter(function (x) { return x.cat === cat; })[0];
    if (!g) return;
    g.items.forEach(function (it) { if (!isLocked(it.id)) delete state.overrides[it.id]; });
    jset(LS_KEY, state.overrides); apply();
    call('/settings/reset', { section: cat });
  }
  function resetAll() {
    Object.keys(state.overrides).forEach(function (id) { if (!isLocked(id)) delete state.overrides[id]; });
    jset(LS_KEY, state.overrides); apply();
    call('/settings/reset', { section: 'all' });
  }

  function exportPersonal() { return JSON.stringify({ v: 1, overrides: state.overrides }, null, 2); }
  function importPersonal(json) {
    var data; try { data = JSON.parse(json); } catch (e) { return { ok: false, error: 'bad_json' }; }
    if (!data || !data.overrides) return { ok: false, error: 'no_overrides' };
    var applied = 0, rejected = 0;
    Object.keys(data.overrides).forEach(function (id) {
      var val = data.overrides[id];
      if (validate(id, val).ok && !isLocked(id)) { state.overrides[id] = val; applied++; } else { rejected++; }
    });
    jset(LS_KEY, state.overrides); apply();
    call('/settings/save', { values: state.overrides });
    return { ok: true, applied: applied, rejected: rejected };
  }

  // ---- migration from pre-D1 localStorage ----
  function migrateLegacy() {
    // D3 — rename any pre-D3 personal-override keys onto their stable ids so a user's
    // saved preferences survive the 101-catalog adoption (idempotent).
    if (jget('mzMigrated.v3', false)) return;
    var o = jget(LS_KEY, {}); var changed = false;
    Object.keys(MIGRATE).forEach(function (old) {
      if (Object.prototype.hasOwnProperty.call(o, old)) {
        var stable = MIGRATE[old];
        if (old === 'gridCols') {                    // split auto vs fixed+count
          if (String(o[old]) === 'auto') { o.gr_cols_mode = 'auto'; }
          else { o.gr_cols_mode = 'fixed'; o.gr_cols = String(o[old]); }
        } else if (old === 'reduceMotion') {
          o.ac_reduce = (o[old] === true || o[old] === 'true');
        } else if (!Object.prototype.hasOwnProperty.call(o, stable)) {
          o[stable] = o[old];
        }
        delete o[old]; changed = true;
      }
    });
    if (changed) jset(LS_KEY, o);
    jset('mzMigrated.v3', true);
  }

  // ---- boot ----
  function boot() {
    migrateLegacy();
    state.overrides = jget(LS_KEY, {});
    var cachedEff = jget(LS_EFF, null);
    if (cachedEff) { state.effective = cachedEff.effective || {}; state.provenance = cachedEff.provenance || {}; state.locks = cachedEff.locks || {}; state.catalog = cachedEff.catalog || {}; }
    apply();                      // immediate — from cache/defaults, no flash, offline-safe
    // then reconcile with the backend cascade
    call('/settings/effective', {}).then(function (d) {
      if (d && d.ok) {
        state.effective = d.effective || {};
        state.provenance = d.provenance || {};
        state.locks = d.locks || {};
        state.catalog = d.catalog || {};                 // D3 101-catalog + status
        state.isAdmin = !!d.is_admin;
        state.adminCaps = d.admin_caps || [];
        if (d.overrides && Object.keys(state.overrides).length === 0) state.overrides = d.overrides;
        jset(LS_EFF, { effective: state.effective, provenance: state.provenance, locks: state.locks, catalog: state.catalog });
        state.ready = true;
        apply();
        fire('ready', state);
        refreshAdminRail();
      }
    });
    // react to system changes without reload
    if (window.matchMedia) {
      try {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', apply);
        window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', apply);
      } catch (e) { /* Safari <14 */ }
    }
    mountUi();
  }

  // ---- UI: Settings + Admin workspaces (mounted into the shell) ----
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }

  function mountUi() {
    if (!document.getElementById('app')) { document.addEventListener('DOMContentLoaded', mountUi); return; }
    if (document.getElementById('view-settings')) return; // once
    injectUiCss();
    addRailButton('settings', 'Settings', 'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-2.77.66 1.65 1.65 0 00-1.63 1.31V22a2 2 0 11-4 0v-.09A1.65 1.65 0 007 20.6a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.66-2.77 1.65 1.65 0 00-1.31-1.63H2a2 2 0 110-4h.09A1.65 1.65 0 003.4 7a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 002.77-.66V2a2 2 0 114 0v.09a1.65 1.65 0 001.63 1.31 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.66 2.77 1.65 1.65 0 001.31 1.63H22a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z', true);
    addRailButton('admin', 'Admin Console', 'M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6zM9 12l2 2 4-4', false);
    buildSettingsView();
    buildAdminView();
    // integrate with the host router: intercept rail clicks for our views
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('.railbtn[data-view="settings"],.railbtn[data-view="admin"]');
      if (!b) return;
      ev.preventDefault(); ev.stopPropagation();
      openView(b.getAttribute('data-view'));
    }, true);
  }

  function addRailButton(view, label, path, before) {
    var rail = document.querySelector('.rail'); if (!rail) return;
    if (rail.querySelector('.railbtn[data-view="' + view + '"]')) return;
    var b = el('button', 'railbtn mz-railbtn');
    b.setAttribute('data-view', view);
    b.setAttribute('aria-label', label);
    b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="' + path + '"/></svg>'
      + '<span class="railtip">' + label + '</span><span class="rllbl">' + (view === 'admin' ? 'Admin' : 'Settings') + '</span>';
    if (view === 'admin') b.style.display = 'none';       // shown only for admins
    var spacer = rail.querySelector('.spacer');
    if (spacer) rail.insertBefore(b, spacer); else rail.appendChild(b);
  }

  function refreshAdminRail() {
    var b = document.querySelector('.rail .railbtn[data-view="admin"]');
    if (b) b.style.display = state.isAdmin ? '' : 'none';
  }

  function openView(view) {
    // hide host .view screens, show ours (reuse the shell's absolute-fill pattern)
    Array.prototype.forEach.call(document.querySelectorAll('.view'), function (v) { v.classList.remove('active'); });
    Array.prototype.forEach.call(document.querySelectorAll('.mz-view'), function (v) { v.classList.remove('active'); });
    var target = document.getElementById('view-' + view);
    if (target) target.classList.add('active');
    Array.prototype.forEach.call(document.querySelectorAll('.railbtn[data-view]'), function (x) {
      x.setAttribute('aria-current', x.getAttribute('data-view') === view);
    });
    if (view === 'settings') renderSettings();
    if (view === 'admin') renderAdmin();
  }
  // when the host navigates elsewhere, drop our active screens
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.railbtn[data-view]');
    if (!b) return;
    var v = b.getAttribute('data-view');
    if (v !== 'settings' && v !== 'admin') {
      Array.prototype.forEach.call(document.querySelectorAll('.mz-view'), function (x) { x.classList.remove('active'); });
    }
  }, false);

  function buildSettingsView() {
    var main = document.querySelector('.main'); if (!main) return;
    var v = el('section', 'view mz-view', '');
    v.id = 'view-settings';
    v.innerHTML =
      '<div class="mz-ws"><header class="mz-wshead"><h1>Settings</h1>'
      + '<div class="mz-wsactions">'
      + '<button class="mz-btn" data-mz-act="export">Export</button>'
      + '<button class="mz-btn" data-mz-act="import">Import</button>'
      + '<button class="mz-btn mz-btn--danger" data-mz-act="resetAll">Reset all</button></div></header>'
      + '<div class="mz-settings-body"><nav class="mz-cats" id="mz-cats"></nav>'
      + '<div class="mz-panel" id="mz-panel"></div></div></div>';
    main.appendChild(v);
    v.addEventListener('click', function (ev) {
      var a = ev.target.closest('[data-mz-act]'); if (!a) return;
      var act = a.getAttribute('data-mz-act');
      if (act === 'export') { downloadText('mezze-settings.json', exportPersonal()); }
      else if (act === 'import') { pickImport(); }
      else if (act === 'resetAll') { if (confirm('Reset all personal settings to inherited defaults?')) { resetAll(); renderSettings(); } }
      else if (act === 'resetSection') { resetSection(a.getAttribute('data-cat')); renderSettings(); }
    });
  }

  function renderSettings() {
    var cats = document.getElementById('mz-cats'); var panel = document.getElementById('mz-panel');
    if (!cats || !panel) return;
    var secs = sections();
    cats.innerHTML = secs.map(function (g, i) {
      return '<button class="mz-cat' + (i === 0 ? ' on' : '') + '" data-cat="' + esc(g.cat) + '">' + esc(g.cat) + '</button>';
    }).join('');
    if (!cats.getAttribute('data-init')) {
      cats.setAttribute('data-init', '1');
      cats.addEventListener('click', function (ev) {
        var b = ev.target.closest('.mz-cat'); if (!b) return;
        Array.prototype.forEach.call(cats.children, function (c) { c.classList.remove('on'); });
        b.classList.add('on'); renderCategory(b.getAttribute('data-cat'));
      });
    }
    var active = cats.querySelector('.mz-cat.on');
    renderCategory(active ? active.getAttribute('data-cat') : (secs[0] && secs[0].cat));
  }

  function renderCategory(cat) {
    var panel = document.getElementById('mz-panel'); if (!panel) return;
    var g = sections().filter(function (x) { return x.cat === cat; })[0]; if (!g) return;
    var rows = g.items.map(function (it) {
      var cur = effectiveVal(it.id);
      var locked = isLocked(it.id);
      var unimpl = (it.status !== 'working');        // disabled: read-only + reason
      var disabled = locked || unimpl;
      var prov = state.provenance[it.id] || { scope: 'default', source: '', lock: state.locks[it.id] || 'free' };
      var hasOverride = Object.prototype.hasOwnProperty.call(state.overrides, it.id);
      var control;
      if (it.type === 'bool') {
        control = '<button class="mz-toggle' + (cur === true || cur === 'true' ? ' on' : '') + '" role="switch" aria-checked="' + (cur === true || cur === 'true') + '"'
          + (disabled ? ' disabled aria-disabled="true"' : '') + ' data-id="' + esc(it.id) + '" data-type="bool"><span class="mz-knob"></span></button>';
      } else if (it.type === 'int') {
        var r = it.range || [1, 12];
        control = '<input class="mz-select" type="number" min="' + r[0] + '" max="' + r[1] + '" value="' + esc(String(cur)) + '"'
          + (disabled ? ' disabled aria-disabled="true"' : '') + ' data-id="' + esc(it.id) + '" data-type="int" style="min-width:90px">';
      } else if (it.type === 'key') {
        control = '<code class="admin-badge">' + esc(String(cur)) + '</code>';   // shortcut binding, read-only
      } else {
        control = '<select class="mz-select" data-id="' + esc(it.id) + '" data-type="enum"' + (disabled ? ' disabled aria-disabled="true"' : '') + '>'
          + it.options.map(function (o) { return '<option value="' + esc(o) + '"' + (String(cur) === String(o) ? ' selected' : '') + '>' + esc(labelFor(o)) + '</option>'; }).join('')
          + '</select>';
      }
      var badges = '';
      if (locked) badges += '<span class="admin-badge lock" title="Locked by ' + esc(prov.scope) + '">🔒 ' + esc(prov.scope) + '</span>';
      else if (unimpl) badges += '<span class="admin-badge pref" title="' + esc(it.reason) + '">Not available yet</span>';
      else if (hasOverride) badges += '<span class="admin-badge me">Personal</span>';
      else badges += '<span class="admin-badge inh">Inherited · ' + esc(prov.scope || 'default') + '</span>';
      var provLine = '<div class="mz-prov">effective=<b>' + esc(String(cur)) + '</b> · scope=' + esc(prov.scope || 'default')
        + ' · source=' + esc(prov.source || '—') + ' · policy=' + esc(prov.lock || state.locks[it.id] || 'free')
        + (unimpl ? ' · ' + esc(it.reason) : '') + '</div>';
      return '<div class="mz-row"><div class="mz-rowmain"><label>' + esc(it.label) + ' <span style="opacity:.5;font-weight:400;font-size:11px">' + esc(it.id) + '</span></label><div class="admin-badges">' + badges + '</div>' + provLine + '</div>'
        + '<div class="mz-ctl">' + control + '</div></div>';
    }).join('');
    panel.innerHTML = '<div class="mz-cathead"><h2>' + esc(cat) + '</h2><button class="mz-btn mz-btn--sm" data-mz-act="resetSection" data-cat="' + esc(cat) + '">Reset section</button></div>' + rows;
    panel.querySelectorAll('[data-id]').forEach(function (ctl) {
      var id = ctl.getAttribute('data-id'); var ty = ctl.getAttribute('data-type');
      if (ty === 'bool') {
        ctl.addEventListener('click', function () { if (statusOf(id) !== 'working' || isLocked(id)) return; set(id, !(effectiveVal(id) === true || effectiveVal(id) === 'true')); renderCategory(cat); });
      } else if (ty === 'int') {
        ctl.addEventListener('change', function () { set(id, String(ctl.value)); renderCategory(cat); });
      } else {
        ctl.addEventListener('change', function () { set(id, ctl.value); renderCategory(cat); });
      }
    });
  }

  function labelFor(o) {
    var map = { system: 'System', light: 'Light', dark: 'Dark', auto: 'Auto', ltr: 'Left→Right', rtl: 'Right→Left (عربى)',
      classic: 'Mezze Classic', corporate: 'Corporate', coastal: 'Coastal', forest: 'Forest', coffeehouse: 'Coffee House',
      highcontrast: 'High Contrast', midnight: 'Midnight', lounge: 'Lounge', graphite: 'Graphite', forestnight: 'Forest Night',
      slate: 'Slate', terracotta: 'Terracotta', blue: 'Blue', teal: 'Teal', plum: 'Plum', olive: 'Olive',
      standard: 'Standard', compact: 'Compact', comfortable: 'Comfortable', detailed: 'Detailed',
      labels: 'Icons + labels', icons: 'Icons only', right: 'Right', left: 'Left', narrow: 'Narrow', wide: 'Wide',
      pos: 'Point of Sale', floor: 'Floor', kds: 'Kitchen', manager: 'Manager', reports: 'Reports',
      auto: 'Auto', '90': '90%', '100': '100%', '80': '80%', '110': '110%', '120': '120%', '140': '140%',
      lazy: 'Lazy', eager: 'Eager', off: 'Off', all: 'All items', category: 'Current category', favorites: 'Favorites',
      list: 'List', grid: 'Grid' };
    return map[o] || o;
  }

  // ---- Admin Console ----
  function buildAdminView() {
    var main = document.querySelector('.main'); if (!main) return;
    var v = el('section', 'view mz-view', '');
    v.id = 'view-admin';
    v.innerHTML = '<div class="mz-ws"><header class="mz-wshead"><h1>Admin Console</h1>'
      + '<div class="mz-wstabs" id="mz-admtabs">'
      + '<button class="mz-tab on" data-tab="templates">Templates</button>'
      + '<button class="mz-tab" data-tab="assignments">Assignments</button>'
      + '<button class="mz-tab" data-tab="locks">Locks &amp; Policy</button>'
      + '<button class="mz-tab" data-tab="permissions">Permissions</button>'
      + '<button class="mz-tab" data-tab="audit">Audit</button></div></header>'
      + '<div class="mz-admbody" id="mz-admbody"></div></div>';
    main.appendChild(v);
    v.querySelector('#mz-admtabs').addEventListener('click', function (ev) {
      var b = ev.target.closest('.mz-tab'); if (!b) return;
      Array.prototype.forEach.call(v.querySelectorAll('.mz-tab'), function (t) { t.classList.remove('on'); });
      b.classList.add('on'); renderAdminTab(b.getAttribute('data-tab'));
    });
  }

  function renderAdmin() {
    if (!state.isAdmin) {
      var body = document.getElementById('mz-admbody');
      if (body) body.innerHTML = '<div class="mz-empty">Admin Console requires an administrative role (organization administrator, store manager, role manager, or auditor).</div>';
      return;
    }
    renderAdminTab('templates');
  }

  function renderAdminTab(tab) {
    var body = document.getElementById('mz-admbody'); if (!body) return;
    body.innerHTML = '<div class="mz-empty">Loading…</div>';
    call('/admin/' + tab, {}).then(function (d) {
      if (!d || !d.ok) { body.innerHTML = '<div class="mz-empty">' + (d && d.error === 'permission_denied' ? 'Not permitted for your admin role.' : 'Unavailable.') + '</div>'; return; }
      if (tab === 'templates') renderTemplates(body, d.templates || []);
      else if (tab === 'assignments') renderAssignments(body, d.assignments || [], d.templates || []);
      else if (tab === 'locks') renderLocks(body, d.locks || []);
      else if (tab === 'permissions') renderPermissions(body, d.roles || []);
      else if (tab === 'audit') renderAudit(body, d.entries || []);
    });
  }

  function renderTemplates(body, rows) {
    body.innerHTML = '<div class="mz-adm-toolbar"><button class="mz-btn" data-adm="tpl-new">New template</button></div>'
      + '<table class="mz-table"><thead><tr><th>Name</th><th>Scope kind</th><th>State</th><th>Version</th><th>Settings</th><th></th></tr></thead><tbody>'
      + (rows.length ? rows.map(function (t) {
        return '<tr><td><b>' + esc(t.name) + '</b></td><td>' + esc(t.kind || '—') + '</td><td><span class="admin-badge ' + esc(t.state) + '">' + esc(t.state) + '</span></td>'
          + '<td>v' + esc(String(t.version || 1)) + '</td><td>' + esc(String(t.count || 0)) + '</td>'
          + '<td class="mz-actions">'
          + '<button class="mz-btn mz-btn--sm" data-adm="tpl-dup" data-id="' + t.id + '">Duplicate</button>'
          + (t.state === 'draft' ? '<button class="mz-btn mz-btn--sm" data-adm="tpl-pub" data-id="' + t.id + '">Publish</button>' : '<button class="mz-btn mz-btn--sm" data-adm="tpl-arch" data-id="' + t.id + '">Archive</button>')
          + '</td></tr>';
      }).join('') : '<tr><td colspan="6" class="mz-empty">No templates yet.</td></tr>')
      + '</tbody></table>';
    body.querySelectorAll('[data-adm]').forEach(function (b) {
      b.addEventListener('click', function () {
        var act = b.getAttribute('data-adm'), id = b.getAttribute('data-id');
        if (act === 'tpl-new') { var name = prompt('Template name:'); if (name) admCall('/admin/template/create', { name: name, kind: 'role' }, 'templates'); }
        else if (act === 'tpl-dup') admCall('/admin/template/duplicate', { template_id: +id }, 'templates');
        else if (act === 'tpl-pub') admCall('/admin/template/publish', { template_id: +id }, 'templates');
        else if (act === 'tpl-arch') admCall('/admin/template/archive', { template_id: +id }, 'templates');
      });
    });
  }
  function renderAssignments(body, rows, tpls) {
    body.innerHTML = '<table class="mz-table"><thead><tr><th>Scope</th><th>Target</th><th>Template</th><th>Effective</th></tr></thead><tbody>'
      + (rows.length ? rows.map(function (a) {
        return '<tr><td>' + esc(a.scope) + '</td><td>' + esc(a.target || '—') + '</td><td>' + esc(a.template || '—') + '</td><td>' + (a.effective ? '✓' : '') + '</td></tr>';
      }).join('') : '<tr><td colspan="4" class="mz-empty">No assignments. Assign a template to org/brand/branch/role/user/device via the API.</td></tr>')
      + '</tbody></table>';
  }
  function renderLocks(body, rows) {
    body.innerHTML = '<table class="mz-table"><thead><tr><th>Setting</th><th>Scope</th><th>Policy</th><th>Value</th><th>Affects</th></tr></thead><tbody>'
      + (rows.length ? rows.map(function (l) {
        return '<tr><td>' + esc(l.setting) + '</td><td>' + esc(l.scope) + '</td><td><span class="admin-badge ' + esc(l.policy) + '">' + esc(l.policy) + '</span></td><td>' + esc(String(l.value)) + '</td><td>' + esc(String(l.affects || '')) + '</td></tr>';
      }).join('') : '<tr><td colspan="5" class="mz-empty">No locks. Policies: free / bounded / locked.</td></tr>')
      + '</tbody></table>';
  }
  function renderPermissions(body, roles) {
    body.innerHTML = '<table class="mz-table"><thead><tr><th>Admin role</th><th>Capabilities</th></tr></thead><tbody>'
      + (roles.length ? roles.map(function (r) { return '<tr><td><b>' + esc(r.role) + '</b></td><td>' + esc((r.caps || []).join(', ')) + '</td></tr>'; }).join('')
        : '<tr><td colspan="2" class="mz-empty">Scoped admin roles: organization administrator, store manager, role manager, auditor.</td></tr>')
      + '</tbody></table>';
  }
  function renderAudit(body, rows) {
    body.innerHTML = '<table class="mz-table"><thead><tr><th>When</th><th>Actor</th><th>Event</th><th>Scope</th><th>Change</th></tr></thead><tbody>'
      + (rows.length ? rows.map(function (e) {
        return '<tr><td>' + esc(e.at || '') + '</td><td>' + esc(e.actor || '') + '</td><td>' + esc(e.event || '') + '</td><td>' + esc(e.scope || '') + '</td><td class="mz-mono">' + esc((e.old || '') + ' → ' + (e.new || '')) + '</td></tr>';
      }).join('') : '<tr><td colspan="5" class="mz-empty">No audit entries yet.</td></tr>')
      + '</tbody></table>';
  }
  function admCall(path, body, tab) { call(path, body).then(function () { renderAdminTab(tab); }); }

  // ---- misc UI helpers ----
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function downloadText(name, text) {
    var blob = new Blob([text], { type: 'application/json' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function pickImport() {
    var inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'application/json';
    inp.onchange = function () {
      var f = inp.files[0]; if (!f) return;
      var r = new FileReader(); r.onload = function () { var res = importPersonal(r.result); alert(res.ok ? ('Imported ' + res.applied + ' settings (' + res.rejected + ' rejected).') : ('Import failed: ' + res.error)); renderSettings(); }; r.readAsText(f);
    };
    inp.click();
  }

  function injectUiCss() {
    if (document.getElementById('mz-ui-css')) return;
    var s = el('style'); s.id = 'mz-ui-css';
    s.textContent = [
      '.mz-view{position:absolute;inset:0;display:none;background:var(--canvas,#FFFDFB);overflow:auto}',
      '.mz-view.active{display:block}',
      '.mz-ws{max-width:1100px;margin:0 auto;padding:24px 28px 60px}',
      '.mz-wshead{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px;flex-wrap:wrap}',
      '.mz-wshead h1{font-size:26px;font-weight:800;color:var(--ink);margin:0}',
      '.mz-wsactions{display:flex;gap:8px}.mz-wstabs{display:flex;gap:4px;flex-wrap:wrap}',
      /* DESIGN-P3A.1: .mz-btn styling removed — canonical single source is static/design/components.css */
      '.mz-tab{min-height:40px;padding:0 16px;border-radius:999px;border:1px solid transparent;background:transparent;color:var(--ink-2);font-weight:600;cursor:pointer}',
      '.mz-tab.on{background:var(--accent-soft);color:var(--accent-strong);border-color:var(--accent)}',
      '.mz-settings-body{display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:start}',
      '.mz-cats{display:flex;flex-direction:column;gap:2px;position:sticky;top:0}',
      '.mz-cat{text-align:start;min-height:40px;padding:0 14px;border-radius:10px;border:none;background:transparent;color:var(--ink-2);font-weight:600;cursor:pointer}',
      '.mz-cat.on{background:var(--surface);color:var(--ink);box-shadow:var(--shadow-sm)}',
      '.mz-panel{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:8px 20px 16px}',
      '.mz-cathead{display:flex;align-items:center;justify-content:space-between;padding:14px 0 6px;border-bottom:1px solid var(--line);margin-bottom:6px}',
      '.mz-cathead h2{font-size:17px;font-weight:700;color:var(--ink);margin:0}',
      '.mz-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}',
      '.mz-row:last-child{border-bottom:none}.mz-rowmain{min-width:0}',
      '.mz-rowmain label{display:block;font-weight:600;color:var(--ink);font-size:14px;margin-bottom:4px}',
      '.admin-badges{display:flex;gap:6px;flex-wrap:wrap}',
      '/* DESIGN-P3B.2: admin state/policy chips renamed off .mz-badge (canonical .mz-badge = 1 source),',
      '   now consuming the --mz- semantic tokens. .me maps to INFO (was brand accent) so brand is not a status. */',
      '.admin-badge{font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--mz-surface-2,var(--surface-2));color:var(--mz-text-mut,var(--ink-3))}',
      '.admin-badge.me,.admin-badge.inh{background:var(--mz-info-soft);color:var(--mz-info)}',                 /* provenance = info */
      '/* P3B.5 governance semantics: Locked is NOT an error (not danger); Bounded is NOT Warning; Disabled != Locked (dashed vs solid) */',
      '.admin-badge.pref{background:var(--mz-surface-2,var(--surface-2));color:var(--mz-text-mut,var(--ink-3));border:1px dashed var(--mz-border-strong)}',
      '.admin-badge.lock,.admin-badge.locked{background:var(--mz-surface-2,var(--surface-2));color:var(--mz-text-mut,var(--ink-3));border:1px solid var(--mz-border-strong)}',
      '.admin-badge.bounded{background:var(--mz-info-soft);color:var(--mz-info)}',
      '.admin-badge.published{background:var(--mz-ok-soft);color:var(--mz-ok)}',
      '.admin-badge.draft{background:var(--mz-info-soft);color:var(--mz-info)}',
      '.admin-badge.archived,.admin-badge.free{background:var(--mz-surface-2,var(--surface-2));color:var(--mz-text-mut,var(--ink-3))}',
      '.mz-prov{font:12px/1.4 var(--ff-mono-b,monospace);color:var(--ink-3);margin-top:4px}',
      '.mz-select{min-height:44px;min-width:180px;padding:0 12px;border-radius:10px;border:1px solid var(--border-strong);background:var(--surface);color:var(--ink);font-size:13px;font-weight:600}',
      '.mz-select:disabled{opacity:.6;cursor:not-allowed}',
      '.mz-toggle{width:52px;height:30px;border-radius:999px;border:none;background:var(--border-strong);position:relative;cursor:pointer;transition:background .16s}',
      '.mz-toggle.on{background:var(--accent)}.mz-toggle:disabled{opacity:.6;cursor:not-allowed}',
      '.mz-knob{position:absolute;top:3px;inset-inline-start:3px;width:24px;height:24px;border-radius:50%;background:#fff;transition:inset-inline-start .16s}',
      '.mz-toggle.on .mz-knob{inset-inline-start:25px}',
      '.mz-table{width:100%;border-collapse:collapse;font-size:13px}',
      '.mz-table th{text-align:start;color:var(--ink-3);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding:8px 10px;border-bottom:1px solid var(--border)}',
      '.mz-table td{padding:10px;border-bottom:1px solid var(--line);color:var(--ink)}',
      '.mz-actions{display:flex;gap:6px}.mz-adm-toolbar{margin-bottom:12px}',
      '.mz-empty{padding:28px;text-align:center;color:var(--ink-3)}',
      '.mz-mono{font-family:var(--ff-mono-b,monospace);font-size:12px}',
      '[dir="rtl"] .mz-ws{direction:rtl}'
    ].join('\n');
    document.head.appendChild(s);
  }

  // ---- public API ----
  window.MezzeDesign = {
    themes: { light: LIGHT_THEMES, dark: DARK_THEMES }, accents: ACCENTS, sections: sections,
    get: effectiveVal, set: set, isLocked: isLocked, resetSection: resetSection, resetAll: resetAll,
    apply: apply, on: on, exportPersonal: exportPersonal, importPersonal: importPersonal,
    state: function () { return state; }, validate: validate, openSettings: function () { openView('settings'); }, openAdmin: function () { openView('admin'); }
  };

  // early paint: set appearance/theme ASAP to avoid a flash, before full boot
  (function early() {
    try {
      var ov = jget(LS_KEY, {});
      var el0 = document.documentElement;
      el0.setAttribute('data-appearance', 'mezze');
      var m = ov.app_mode || ov.mode || 'system';                 // stable id, legacy fallback
      var mode = (m === 'system') ? ((window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light') : (m === 'dark' ? 'dark' : 'light');
      var hc = ov.ac_contrast || ov.highContrast;
      el0.setAttribute('data-theme', mode);
      el0.setAttribute('data-mz-mode', mode);
      el0.setAttribute('data-mz-theme', hc ? 'highcontrast' : (mode === 'dark' ? (ov.app_dark_theme || ov.darkTheme || 'lounge') : (ov.app_theme || ov.lightTheme || 'classic')));
      el0.setAttribute('data-mz-accent', ov.app_accent || ov.accent || 'terracotta');
      el0.setAttribute('data-mz-density', ov.app_density || ov.density || 'standard');
      el0.setAttribute('data-mz-scale', ov.app_scale || ov.uiScale || '100');
    } catch (e) {}
  })();

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
