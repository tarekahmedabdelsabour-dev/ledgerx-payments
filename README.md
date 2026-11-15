# Payment Network

Electronic payments and a network of field agents on top of the accounting, sales, POS, purchasing and stock modules: wallets, cash custody, commissions, settlements, approvals and a full audit trail. The screens are Arabic-first (`translations/ar.csv`); the agent works from a phone page at `/agent-pay`.

## How money moves

```
company bank --funding--> Manager wallet --transfer--> Supervisor wallet --transfer--> Agent wallet
                                                                                          |
   customer pays cash <-- agent sells a service (float spent, provider charged) ----------+
   cash held by the agent --handover--> supervisor --handover--> manager --> company cash
```

Every wallet has three balances, all calculated from an append-only ledger (never edited, never deleted):
**Available** (float to spend), **Commission** (earned, not settled) and **Cash Held** (collected from customers, not handed in).

## What is inside

| Part | Where |
|---|---|
| 12 DocTypes (profile, wallet, ledger entry, service, commission rule/tier, transaction, wallet charge, cash settlement, approval request, settings, audit log) | `payment_network/payment_network/doctype` |
| Pure rules (fees, commission split, limits, PIN, signatures), unit-tested | `engine/logic.py` |
| Ledger with row locking | `engine/ledger.py` |
| Operations: hold, provider call, success, failure, reversal, approvals, pending review, webhook | `engine/service.py` |
| Journal and Payment Entries | `engine/accounting.py`, [docs/ACCOUNTING.md](docs/ACCOUNTING.md) |
| Provider layer (`PaymentProvider` + sandbox `Mock`) | `providers/`, [docs/PROVIDERS.md](docs/PROVIDERS.md) |
| Backend isolation by role | `permissions.py` |
| Agent API, webhook (HMAC), manager actions | `api/` |
| 7 reports, workspace, dashboard charts, number cards | `report/`, `workspace/`, ... |
| Custom Fields on invoices/entries (fixtures) and `doc_events` | `fixtures/`, `hooks.py`, `events.py` |

## Safety rules built in

- Balance changes happen only in `ledger.post`, inside `SELECT ... FOR UPDATE`; two operations can never spend the same money.
- A transaction holds the float and commits **before** the provider is called; a crash leaves a visible *Processing* record that the 5-minute job resolves.
- `idempotency_key` is unique: repeating a request returns the same transaction.
- Wrong PIN attempts are counted even though the request errors; the account locks after the configured number.
- Webhooks are accepted only with a valid HMAC signature; the provider answer is applied once.
- Reversal is only an opposite operation (refund at the provider, opposite ledger entries and Journal Entry); it needs a supervisor/manager who is not the requester.
- Journal/Payment Entries made by the module cannot be cancelled by hand; reverse the transaction instead.

## Install and test

See [docs/INSTALL.md](docs/INSTALL.md).

## Status

Written without access to a running site. The pure rules have passing unit tests; everything that needs the database (the engine, controllers, reports, the page, the integration tests in `tests/test_engine.py`) has been statically checked only. Run the integration tests on a test site before any real use, and keep the mode on Sandbox until they pass.
