# Mezze — optional demo restaurant (EXPLICIT-only)

These seed scripts create an optional demo restaurant (pizzas + a half-&-half
base, promotions, product images) so a salesperson or a new evaluator can see a
populated menu immediately.

## They are NEVER auto-loaded

`mezze_bridge` declares **no** Odoo `demo` manifest key. None of these files are
in the manifest `data`/`demo` lists, so:

- installing or upgrading the module loads **zero** demo records;
- a production install (`-i mezze_bridge --without-demo=all`) is factory-empty;
- a production go-live failure is a **real** failure — no demo data papers over it.

## Loading the demo deliberately (non-production only)

```bash
./odoo-bin shell -c <conf> -d <demo_db> --no-http < addons/mezze_bridge/demo/seed_pizza.py
./odoo-bin shell -c <conf> -d <demo_db> --no-http < addons/mezze_bridge/demo/seed_promos.py
./odoo-bin shell -c <conf> -d <demo_db> --no-http < addons/mezze_bridge/demo/seed_images.py
```

Each script is idempotent (re-running updates the same records) and portable
(reuses the demo DB's own taxes). `seed_pizza.py` sets
`ir.config_parameter mezze_bridge.demo_loaded = True`.

## Guardrail

The Go-Live validator has a `demo_data_absent` check: if `mezze_bridge.demo_loaded`
is set while `mezze_bridge.env_profile = production`, the check **FAILS** — you
cannot certify a production go-live with the demo dataset still loaded.
