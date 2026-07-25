/* mezze-customer.js — minimal appearance bootstrap for CUSTOMER-FACING surfaces.
 *
 * Applies the approved Mezze appearance + theme/mode/accent/direction and nothing
 * else: NO staff navigation shell, NO settings UI, NO admin controls. Theme source,
 * in priority order: URL params (?mztheme=&mzmode=&mzaccent=&dir= — so a branch can
 * pin its CFD/QR screen), then any persisted staff prefs on this origin, else the
 * approved defaults (Mezze Classic / Terracotta / system light-dark). Re-applies on
 * system light/dark change with no reload.
 */
(function () {
  'use strict';
  var LIGHT = ['classic', 'corporate', 'coastal', 'forest', 'coffeehouse', 'highcontrast'];
  var DARK = ['midnight', 'lounge', 'graphite', 'forestnight', 'slate', 'highcontrast'];
  var ACCENTS = ['terracotta', 'blue', 'teal', 'plum', 'olive'];

  function q() { try { return new URLSearchParams(location.search); } catch (e) { return { get: function () { return null; } }; }
  }
  function prefs() { try { return JSON.parse(localStorage.getItem('mzSettings.v1') || '{}') || {}; } catch (e) { return {}; } }
  function pick(list, v, def) { return list.indexOf(v) >= 0 ? v : def; }

  function apply() {
    var p = q(), o = prefs(), h = document.documentElement;
    var modePref = p.get('mzmode') || o.app_mode || o.mode || 'system';
    var mode = (modePref === 'system')
      ? ((window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light')
      : (modePref === 'dark' ? 'dark' : 'light');
    var hc = (p.get('mztheme') === 'highcontrast') || (o.ac_contrast||o.highContrast);
    var theme = hc ? 'highcontrast'
      : (mode === 'dark' ? pick(DARK, p.get('mztheme') || (o.app_dark_theme||o.darkTheme), 'lounge')
                         : pick(LIGHT, p.get('mztheme') || (o.app_theme||o.lightTheme), 'classic'));
    var accent = pick(ACCENTS, p.get('mzaccent') || (o.app_accent||o.accent), 'terracotta');
    h.setAttribute('data-appearance', 'mezze');
    h.setAttribute('data-theme', mode);
    h.setAttribute('data-mz-mode', mode);
    h.setAttribute('data-mz-theme', theme);
    h.setAttribute('data-mz-accent', accent);
    var dirPref = p.get('dir') || (o.ac_dir||o.direction);
    var dir = (dirPref === 'rtl' || dirPref === 'ltr') ? dirPref
      : ((h.getAttribute('lang') || '').toLowerCase().indexOf('ar') === 0 ? 'rtl' : 'ltr');
    h.setAttribute('dir', dir);
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      h.setAttribute('data-mz-motion', 'reduced');
    }
  }

  apply();
  if (window.matchMedia) {
    try { window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', apply); } catch (e) { /* older engines */ }
  }
  window.MezzeCustomerTheme = { apply: apply };
})();
