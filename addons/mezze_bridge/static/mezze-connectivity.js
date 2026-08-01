/* Mezze Edge connectivity indicator (S1.1A).
 * Small long-lived service: polls /mezze/api/v1/edge/status, keeps last state,
 * derives LOCAL server from whether the RPC succeeds (server never claims it is
 * unavailable while answering), renders one compact Local/Internet/Services chip.
 * Shows only in deployment_mode === 'edge'. No overlapping polls; backs off on
 * failure; stops cleanly on pagehide. EN/AR, tokens only. */
(function () {
  'use strict';
  var NORMAL_MS = 20000, FAIL_MAX_MS = 60000;
  var timer = null, inFlight = false, failStreak = 0, mounted = false;

  function token() {
    var q = new URLSearchParams(location.search);
    var m = document.cookie.match(/(?:^|;\s*)mezze_pos_token=([^;]+)/);
    return q.get('token') || (m ? decodeURIComponent(m[1]) : '');
  }
  function apiBase() { var q = new URLSearchParams(location.search); return (q.get('base') || '') + '/mezze/api/v1'; }
  function isAr() { return (document.documentElement.getAttribute('dir') || '').toLowerCase() === 'rtl'; }

  var T = {
    en: { local: 'Local', internet: 'Internet', services: 'Services',
          online: 'Online', offline: 'Offline', unknown: 'Unknown', unavailable: 'Unavailable',
          degraded: 'Degraded', paused: 'Paused', na: 'N/A',
          wan_off: 'Internet unavailable. Local restaurant operations can continue. Internet-dependent services are temporarily paused.',
          local_off: 'Local Mezze server is unavailable. Reconnect to the restaurant network or contact support.',
          svc_deg: 'Some external services are delayed. Local restaurant operations are unaffected.' },
    ar: { local: 'المحلي', internet: 'الإنترنت', services: 'الخدمات',
          online: 'متصل', offline: 'غير متصل', unknown: 'غير معروف', unavailable: 'غير متاح',
          degraded: 'متدهور', paused: 'موقوف', na: 'غير منطبق',
          wan_off: 'الإنترنت غير متاح. يمكن متابعة عمليات المطعم المحلية. الخدمات المعتمدة على الإنترنت متوقفة مؤقتًا.',
          local_off: 'خادم Mezze المحلي غير متاح. أعد الاتصال بشبكة المطعم أو تواصل مع الدعم.',
          svc_deg: 'بعض الخدمات الخارجية متأخرة. عمليات المطعم المحلية غير متأثرة.' }
  };
  function t(k) { return (isAr() ? T.ar : T.en)[k] || k; }

  function ensureEl() {
    var el = document.getElementById('mezze-conn');
    if (el) return el;
    var bar = document.querySelector('.topbar');
    if (!bar) return null;
    el = document.createElement('div');
    el.id = 'mezze-conn';
    el.className = 'mezze-conn';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.hidden = true;
    // insert before the language toggle if present, else append
    var lang = bar.querySelector('.langtog');
    bar.insertBefore(el, lang || null);
    return el;
  }

  function dot(cls, label, valueText) {
    return '<span class="mc-item"><span class="mc-dot ' + cls + '"></span>' +
           '<span class="mc-k">' + label + '</span>' +
           '<span class="mc-v">' + valueText + '</span></span>';
  }
  function cls(state) {
    if (state === 'online') return 'ok';
    if (state === 'offline' || state === 'unavailable') return 'bad';
    if (state === 'degraded' || state === 'paused' || state === 'unknown') return 'warn';
    return 'neutral';
  }

  // exported for tests / manual drive: render from an explicit state object
  function render(state) {
    var el = ensureEl();
    if (!el) return;
    if (state.deployment_mode !== 'edge') { el.hidden = true; return; }
    el.hidden = false;
    var localState = state.local; // 'online' | 'unavailable'
    var wan = (state.wan && state.wan.state) || 'unknown';
    var svc = (state.external_services && state.external_services.state) || 'n/a';
    var msg = '';
    if (localState === 'unavailable') msg = t('local_off');
    else if (wan === 'offline') msg = t('wan_off');
    else if (svc === 'degraded') msg = t('svc_deg');
    el.className = 'mezze-conn' + (localState === 'unavailable' ? ' mc-critical' : (wan === 'offline' ? ' mc-warn' : ''));
    el.title = msg;
    el.innerHTML =
      dot(cls(localState), t('local'), t(localState === 'online' ? 'online' : 'unavailable')) +
      dot(cls(wan), t('internet'), t(wan === 'n/a' ? 'na' : wan)) +
      dot(svc === 'n/a' ? 'neutral' : cls(svc), t('services'), t(svc === 'n/a' ? 'na' : svc)) +
      (msg ? '<span class="mc-msg">' + msg + '</span>' : '');
  }

  function schedule(ms) {
    if (timer) { clearTimeout(timer); timer = null; }
    timer = setTimeout(poll, ms);
  }

  function poll() {
    if (inFlight) return;               // no overlapping polls
    inFlight = true;
    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctrl) ctrl.abort(); }, 8000);
    fetch(apiBase() + '/edge/status', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token() }),
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) { return r.json(); })
      .then(function (d) {                // RPC succeeded -> local server ONLINE
        failStreak = 0;
        render({ deployment_mode: d.deployment_mode, local: 'online', wan: d.wan, external_services: d.external_services });
        schedule(NORMAL_MS);
      })
      .catch(function () {                // RPC failed -> local server UNAVAILABLE
        failStreak++;
        render({ deployment_mode: 'edge', local: 'unavailable', wan: { state: 'unknown' }, external_services: { state: 'unknown' } });
        schedule(Math.min(NORMAL_MS * Math.max(1, failStreak), FAIL_MAX_MS));
      })
      .finally(function () { clearTimeout(to); inFlight = false; });
  }

  function start() {
    if (mounted) return; mounted = true;
    poll();
    window.addEventListener('pagehide', stop, { once: true });
  }
  function stop() { if (timer) { clearTimeout(timer); timer = null; } mounted = false; }

  // expose a tiny API for tests / manual verification
  window.MezzeConnectivity = { start: start, stop: stop, render: render, _poll: poll };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
