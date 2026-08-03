-- S5 — Mezze staging neutralization. Run automatically by `odoo-bin neutralize`
-- (Odoo discovers each installed module's data/neutralize.sql). Makes a restored
-- production copy safe to run as staging: outbound side effects are disabled and a
-- neutralized marker is set so the app treats aggregator callbacks / online charging
-- / notifications / real terminals as inert. Odoo core + payment modules already
-- neutralize mail servers and payment.provider (-> disabled/test); this file adds
-- the Mezze-specific outbound surfaces.

-- 1) Mark the database neutralized (honored by mezze.productization.is_neutralized).
INSERT INTO ir_config_parameter (key, value)
VALUES ('mezze_bridge.neutralized', 'True')
ON CONFLICT (key) DO UPDATE SET value = 'True';

-- 2) Disable aggregator channels and blank their outbound notify URL + secret so no
--    callback can reach a live aggregator from staging. (Secrets are re-set by an
--    operator if a channel is deliberately re-enabled for a staging test.)
UPDATE mezze_aggregator
   SET active = FALSE,
       notify_url = NULL,
       secret_enc = NULL;

-- 3) Drain any queued outbound integration/webhook events so a restore does not
--    re-deliver production webhooks from staging.
UPDATE mezze_outbox_event
   SET status = 'dead'
 WHERE status IN ('pending', 'inflight', 'failed')
   AND event_type LIKE 'integration.%';
