# Accounting: proposed accounts and entries

Review this with your accountant **before** pressing *Create Accounts* in Payment Settings. Nothing is posted until you do and until the first charge.

## Accounts (one set per company)

| Setting | Suggested name | Type | Holds |
|---|---|---|---|
| Payment Provider Clearing Account | Payment Provider Clearing | Asset | Money held with the payment provider (the float) |
| Agents Cash Custody Account | Payment Agents Cash Custody | Asset | Cash agents and supervisors collected from customers and not handed in yet |
| Wallet Balances Liability Account | Payment Wallet Balances | Liability | Commission owed to agents and supervisors |
| Commission Income Account | Payment Commission Income | Income | Fees charged to customers |
| Agents Commission Expense Account | Payment Agents Commission | Expense | Commission paid to agents and supervisors |
| Cash Difference Account | Payment Cash Differences | Expense | Cash shortage (debit) or excess (credit) found at settlement |
| Company Cash Account | (your existing cash/bank account) | Asset | Where settlements arrive |

The wallet itself is not an account: it is the ledger of three balances per person (Available, Commission, Cash Held). The Available balance is float the company already holds at the provider, handed out inside the company, so moving it between wallets needs no entry.

## Entries

| Event | Debit | Credit |
|---|---|---|
| **Company funding** of the manager's wallet | Provider Clearing | Bank/Cash chosen on the charge |
| **Transfer** manager > supervisor > agent (and back) | no entry (ledger only) | |
| **Service sold** (amount 100, fee 1, commission pool 1 split 60/20/20 with agent 0.60, supervisor 0.20, company 0.20) | Cash Custody 101; Commission Expense 0.80 | Provider Clearing 100; Commission Income 1; Wallet Balances 0.80 |
| **Reversal** of a service | the opposite of the entry above | |
| **Invoice paid electronically** | Provider Clearing (Payment Entry, mode "Electronic Payment") | Accounts Receivable |
| **Supplier paid electronically** | Accounts Payable | Provider Clearing (Payment Entry) |
| **Settlement agent > supervisor** (due D, commission deducted O, handed H, shortage S = D - O - H) | Wallet Balances O; Cash Difference S | Cash Custody O + S |
| **Settlement supervisor > manager** | Cash H; Wallet Balances O; Cash Difference S | Cash Custody D |

Excess cash (S below zero) is booked the other way round. The commission an agent keeps from the cash he hands in (O) clears his liability.

## Points that need an accountant's decision

1. **Who bears a cash shortage.** Here it is expensed to Cash Difference and the settlement records it; recovering it from the agent (for example from payroll) is a separate manual step.
2. **Commission is paid from the customer fee.** If the commission pool is larger than the fee, the company subsidises the difference (the expense is still booked in full).
3. **POS invoices** that are not consolidated yet get an unallocated Payment Entry (an advance) that you allocate after consolidation.
4. **Multi-currency:** one company currency is assumed for all the accounts above.
