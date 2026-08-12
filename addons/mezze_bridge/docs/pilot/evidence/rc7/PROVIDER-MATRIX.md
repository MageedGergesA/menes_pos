# RC7 — Provider matrix

Read from the RC7 pilot database.

## POS payment methods (attached to the pilot config)

| Method | Mezze mode | Meaning |
|---|---|---|
| Cash | `cash` | native cash tender |
| Card | `manual` | manual / external capture — the amount is keyed, no terminal is driven |

## Payment providers

| Provider | State |
|---|---|
| `demo` | **test** |
| `paymob` | disabled |
| all others (19 rows) | disabled / unset |

## Verdict

**Real payment: NOT READY.** Only the demo provider is enabled and it is in `test`
state; Paymob is disabled and carries no live credentials. No live credentials were
configured and no charge was executed — both are explicitly out of scope for this task.
