"""Capture harness for the pixel-parity loop. Not an assertion suite.

Renders the REAL Odoo/Owl Register at the canonical 1920x1080 canvas and writes
the PNG to disk so it can be diffed against the frozen prototype rendered at the
same size. It is a harness, not a test: it asserts nothing about the design, and
it exists because a screenshot taken any other way is not the screen a cashier
sees — a detached HTML approximation would prove nothing.

Auth goes through `HttpCase.authenticate`, which is the same call every
`browser_js(login=...)` in this suite already makes.

Tagged `mezze_capture` and excluded from the default run, so it never slows the
suite or fails a build on a rendering hiccup.
"""
import base64
import binascii
import os

from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser

OUT = os.environ.get('MEZZE_SHOT_DIR', '/home/mageed/.mezze_shots')
URL = os.environ.get('MEZZE_SHOT_URL', '/mezze/pos')
NAME = os.environ.get('MEZZE_SHOT_NAME', 'actual.png')
READY = os.environ.get('MEZZE_SHOT_READY', '.mz-tile')


@tagged('post_install', '-at_install', '-standard', 'mezze_capture')
class TestVisualCapture(HttpCase):
    browser_size = '1920,1080'          # the canonical canvas, deviceScaleFactor 1

    def test_capture(self):
        # Runs against WHATEVER database it is pointed at, and uses that database's
        # own branch — no fixture. Pixel comparison needs representative data: the
        # 5-item test fixture produced 3 columns where the reference has 5, so the
        # diff measured the menu rather than the layout. Point this at the demo DB
        # and it renders the real catalogue.
        cfg = self.env['pos.config'].sudo().search(
            [('id', '=', int(os.environ['MEZZE_SHOT_CONFIG']))] if os.environ.get('MEZZE_SHOT_CONFIG')
            else [], limit=1)
        self.assertTrue(cfg, 'no pos.config in this database to render')
        if not self.env['pos.session'].sudo().search_count(
                [('config_id', '=', cfg.id), ('state', '!=', 'closed')]):
            sess = self.env['pos.session'].sudo().create({'config_id': cfg.id})
            sess.action_pos_session_open()
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cfg.id))
        self.env.flush_all()
        # PHASE 2 — state parity. The reference panel shows a populated check, so an
        # empty one compares a layout against a placeholder. These are the reference's
        # own six lines, quantities, seats and kitchen states, so the two panels
        # describe the same order.
        table_id = None
        if os.environ.get('MEZZE_SHOT_SEED'):
            table_id = self._seed_reference_check(cfg)

        # A bare /mezze/pos lands on the register PICKER when the till does not know
        # which branch it is — the screenshot would be of a chooser, not the
        # Register. Name the branch explicitly.
        url = URL + ('&' if '?' in URL else '?') + 'config_id=%s' % cfg.id
        if table_id:
            url += '&table_id=%s' % table_id
        browser = ChromeBrowser(self, headless=True)
        try:
            # The framework fences HTTP during tests: without this context the
            # server answers every navigation with "Request ignored during test as
            # it does not contain the required cookie", so the page renders an
            # error body and no amount of waiting produces a tile. browser_js wraps
            # its navigation in exactly this; a hand-rolled harness must too.
            stack = self.allow_requests(browser=browser)
            stack.__enter__()
            self.addCleanup(lambda: stack.__exit__(None, None, None))
            self.authenticate('admin', 'admin', browser=browser)
            self.cr.flush()
            self.cr.clear()
            # PHASE 2 — lock the rendering conditions to the reference's.
            # Headless Chrome reports prefers-color-scheme: dark, and this product
            # honours it (we ship light + dark + High-Contrast). The frozen design is
            # light-only, so an unforced capture differs from the reference in every
            # background pixel — ~99.85% — and any geometry read off that diff is
            # noise. Emulate light BEFORE navigating so first paint is already light.
            browser._websocket_request(
                'Emulation.setEmulatedMedia',
                params={'features': [{'name': 'prefers-color-scheme', 'value': 'light'},
                                     {'name': 'prefers-reduced-motion', 'value': 'reduce'}]},
                timeout=10)
            browser.navigate_to(self.base_url() + url, wait_stop=True)
            # Wait for the app to actually paint, not merely for the document to
            # stop loading — an Owl screen reports "complete" long before it has
            # rendered anything.
            # Poll explicitly rather than via _wait_ready: that helper folds our
            # expression into its own readiness contract, and when it times out it
            # says nothing about WHICH half failed. Here a timeout reports the last
            # value the page actually returned.
            import time as _time
            deadline, seen = _time.time() + 120, None
            while _time.time() < deadline:
                r = browser._websocket_request(
                    'Runtime.evaluate',
                    params={'expression':
                            "JSON.stringify({tiles:document.querySelectorAll('.mz-tile').length,"
                            "phase:(document.querySelector('.mz-app')||{}).dataset"
                            "&&document.querySelector('.mz-app').dataset.phase||null,"
                            "body:document.body.innerText.slice(0,80)})",
                            'returnByValue': True}, timeout=20)
                # `_websocket_request` already unwraps the CDP envelope and returns
                # the `result` object, so Runtime.evaluate lands as
                # {'result': {'type':'string','value': ...}} — one level, not two.
                seen = ((r or {}).get('result') or {}).get('value')
                if seen and '"tiles":0' not in seen:
                    break
                _time.sleep(1.0)
            self.assertTrue(seen and '"tiles":0' not in seen,
                            'the Register never painted a tile; last state: %s' % seen)
            browser._websocket_request(
                'Runtime.evaluate',
                params={'expression': 'new Promise(r => setTimeout(r, 1500))',
                        'awaitPromise': True}, timeout=20)
            res = browser._websocket_request(
                'Page.captureScreenshot',
                params={'format': 'png', 'captureBeyondViewport': False}, timeout=30)
            data = (res.get('result') or {}).get('data') or res.get('data')
            self.assertTrue(data, 'chrome returned no image data')
            os.makedirs(OUT, exist_ok=True)
            path = os.path.join(OUT, NAME)
            with open(path, 'wb') as fh:
                fh.write(binascii.a2b_base64(data))
            self._logger.info('MEZZE_SHOT %s bytes=%s', path, os.path.getsize(path))
            # PHASE 1 — measure, don't eyeball. Region geometry is the signal that
            # survives a data difference; a pixel ratio between two different menus
            # measures the menu, not the layout.
            g = browser._websocket_request(
                'Runtime.evaluate',
                params={'expression': '''JSON.stringify((()=>{
                  const R=s=>{const e=document.querySelector(s);
                    if(!e) return null; const r=e.getBoundingClientRect();
                    return {x:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height)};};
                  const cs=s=>{const e=document.querySelector(s);return e?getComputedStyle(e):null;};
                  const grid=document.querySelector('.mz-grid');
                  const tile=document.querySelector('.mz-tile');
                  return {
                    theme:document.documentElement.getAttribute('data-theme'),
                    scheme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',
                    topbar:R('.mz-topbar'), rail:R('.mz-rail'), cats:R('.mz-catside'),
                    catalog:R('.mz-catalog'), panel:R('.mz-cart'), grid:R('.mz-grid'),
                    tile:R('.mz-tile'),
                    tileRadius:tile?getComputedStyle(tile).borderRadius:null,
                    gridGap:grid?getComputedStyle(grid).gap:null,
                    cols:grid?getComputedStyle(grid).gridTemplateColumns.split(/\\s+/).filter(Boolean).length:0,
                    charge:R('[data-testid=mz-charge]'),
                    bodyBg:getComputedStyle(document.body).backgroundColor,
                    tiles:document.querySelectorAll('.mz-tile').length};})())''',
                        'returnByValue': True}, timeout=20)
            self._logger.info('MEZZE_GEOM %s',
                              ((g or {}).get('result') or {}).get('value'))
        finally:
            browser.stop()

    # ------------------------------------------------------------------
    def _seed_reference_check(self, cfg):
        """Build the reference's check on this branch. Returns the table id.

        Quantities, seats and kitchen states are the ones the frozen panel shows —
        19 items over six lines — so the comparison is of two panels describing the
        same order rather than of a populated panel against an empty one.
        """
        env = self.env
        Product = env['product.product'].sudo()
        table = env['restaurant.table'].sudo().search(
            [('floor_id.pos_config_ids', 'in', cfg.ids), ('active', '=', True)],
            order='table_number', limit=1)
        session = env['pos.session'].sudo().search(
            [('config_id', '=', cfg.id), ('state', '!=', 'closed')], limit=1)

        WANT = [
            # name,               qty, seat, kitchen state
            ('The Family Feast',   2, None, 'fired'),
            ('Shish Tawook',       3, 2,    'fired'),
            ('Kofta',              4, None, 'preparing'),
            ('Mint Lemonade',      5, None, 'served'),
            ('Fries',              3, None, None),      # NEW
            ('Hummus',             2, 1,    None),      # NEW
        ]
        vals = {'session_id': session.id, 'company_id': cfg.company_id.id,
                'amount_tax': 0, 'amount_total': 0, 'amount_paid': 0, 'amount_return': 0}
        if table:
            vals['table_id'] = table.id
        if 'customer_count' in env['pos.order']._fields:
            vals['customer_count'] = 2
        order = env['pos.order'].sudo().create(vals)

        by_state = {}
        for name, qty, seat, state in WANT:
            prod = Product.search([('name', '=', name)], limit=1)
            if not prod:
                continue
            lv = {'order_id': order.id, 'product_id': prod.id, 'qty': qty,
                  'price_unit': prod.list_price,
                  'price_subtotal': prod.list_price * qty,
                  'price_subtotal_incl': prod.list_price * qty}
            if seat and 'mezze_seat' in env['pos.order.line']._fields:
                lv['mezze_seat'] = seat
            env['pos.order.line'].sudo().create(lv)
            if state:
                by_state.setdefault(state, []).append(prod)

        # Kitchen badges are derived from KDS tickets, not stored on the line, so a
        # state only shows if a ticket actually carries that product.
        Ticket = env['mezze.kds.ticket'].sudo()
        for state, prods in by_state.items():
            try:
                tk = Ticket.create({'pos_order_id': order.id, 'station': 'Grill',
                                    'state': state})
                if 'line_ids' in Ticket._fields:
                    for prod in prods:
                        env['mezze.kds.ticket.line'].sudo().create(
                            {'ticket_id': tk.id, 'product_id': prod.id, 'qty': 1})
            except Exception:  # noqa: BLE001 — a badge must never block the capture
                self._logger.exception('could not seed kitchen state %r', state)
        env.flush_all()
        self._logger.info('MEZZE_SEED order=%s lines=%s table=%s',
                          order.id, len(order.lines), table.id if table else None)
        return table.id if table else None
