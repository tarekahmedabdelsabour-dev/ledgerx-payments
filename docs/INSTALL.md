# Installation

```bash
cd ~/frappe-bench-v16
bench get-app https://github.com/<you>/payment-network.git   # or copy the folder into apps/ and add it to sites/apps.txt
./env/bin/pip install -e apps/payment_network                # only if you copied the folder
bench --site mysite.localhost install-app payment_network
bench --site mysite.localhost migrate
bench --site mysite.localhost clear-cache
```
Restart the server afterwards.

## First setup (Desk)

1. **Payment Settings**: choose the company, then press *Setup > Create Accounts* (read `docs/ACCOUNTING.md` first), set *Company Cash Account*, the limits and the amount that needs approval. Keep the mode on *Sandbox*.
2. **Users and profiles**: for each person make a *Payment Agent Profile* (role type Manager / Supervisor / Agent, the supervisor of each agent, limits), then *Security > Set PIN*. The profile gives the user the matching role automatically.
3. **Services and commission rules**.
4. **Fund the float**: a *Wallet Charge* of type *Company Funding* to the manager, then *Transfer* charges down the chain.
5. Agents open **/agent-pay** on their phone.

## Demo data (Sandbox only)

```bash
bench --site mysite.localhost execute payment_network.seed.run
```
Creates a manager, two supervisors, four agents (password and PIN are printed), five services, two commission rules and a funded float.

## Tests

```bash
bench --site mysite.localhost run-tests --app payment_network
```
Run them on a **test site**, not on your live data: they call the seed and make real transactions. Without bench the pure rules can be tested alone: `python3 -m pytest payment_network/tests/test_logic.py`.

## Roles

| Role | Sees | Can do |
|---|---|---|
| Payment Agent | own wallet, own transactions | sell services, ask for a reversal, hand cash to his supervisor (agent screen) |
| Payment Supervisor | himself and his agents | charge his agents from his wallet, confirm their cash handovers, approve large amounts and reversals |
| Payment Manager | everything | fund the float, set up services/rules/profiles, reverse directly, pay suppliers |
| Payment Auditor | everything, read only | reports and the audit log |

Isolation is enforced in the backend (`permissions.py`: `permission_query_conditions` and `has_permission`), not only in the screens.
