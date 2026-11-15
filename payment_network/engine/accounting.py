"""Journal Entries and Payment Entries for every money movement. See docs/ACCOUNTING.md for the full table.

Accounts (all set in Payment Settings; "Create Accounts" there makes them under the standard groups):
  custody   asset      cash agents hold from customers          provider  asset      money held at the payment provider
  liability liability  commission the company owes holders      income    income     fees earned
  expense   expense    commission paid to agents/supervisors    diff      expense    cash shortages / excess
"""
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from payment_network.engine import logic

FIELDS = {
	"custody": "agent_custody_account", "provider": "provider_clearing_account", "liability": "wallet_liability_account",
	"income": "commission_income_account", "expense": "commission_expense_account", "cash": "cash_account",
	"diff": "difference_account",
}
LABELS = {
	"agent_custody_account": "Agents Cash Custody Account", "provider_clearing_account": "Payment Provider Clearing Account",
	"wallet_liability_account": "Wallet Balances Liability Account", "commission_income_account": "Commission Income Account",
	"commission_expense_account": "Agents Commission Expense Account", "cash_account": "Company Cash Account (receives settlements)",
	"difference_account": "Cash Difference Account",
}
# which settings each flow needs
NEEDS = {
	"service": ("custody", "provider", "income", "liability", "expense"),
	"funding": ("provider",),
	"settlement": ("custody", "liability", "cash", "diff"),
	"invoice": ("provider",),
	"supplier": ("provider",),
}


def settings():
	return frappe.get_cached_doc("Payment Settings")


def acct(key):
	return settings().get(FIELDS[key])


def require(flow):
	"""Fail early (before any money moves) when an account the flow needs is not set."""
	s = settings()
	missing = [_(LABELS[FIELDS[k]]) for k in NEEDS[flow] if not s.get(FIELDS[k])]
	if missing:
		frappe.throw(_("Set these accounts in Payment Settings first: {0}").format(", ".join(missing)))
	if not s.company:
		frappe.throw(_("Set the company in Payment Settings first"))


def _cost_center(account, company):
	if frappe.db.get_value("Account", account, "report_type") == "Profit and Loss":
		return settings().cost_center or frappe.get_cached_value("Company", company, "cost_center")
	return None


def merge(lines):
	"""Net each account (debit minus credit) so a Journal Entry never carries the same account twice."""
	net = {}
	for account, dr, cr in lines:
		net[account] = net.get(account, 0.0) + flt(dr) - flt(cr)
	out = []
	for account, v in net.items():
		v = logic.r2(v)
		if v > 0:
			out.append((account, v, 0.0))
		elif v < 0:
			out.append((account, 0.0, -v))
	return out


def make_je(lines, remark, source, transaction=None, posting_date=None):
	lines = merge(lines)
	if not lines:
		return None
	company = settings().company
	doc = frappe.get_doc({
		"doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": company,
		"posting_date": getdate(posting_date or nowdate()), "user_remark": remark, "pn_source": source,
		"pn_transaction": transaction,
		"accounts": [{"account": a, "debit_in_account_currency": dr, "credit_in_account_currency": cr,
			"cost_center": _cost_center(a, company)} for a, dr, cr in lines],
	})
	doc.flags.pn_engine = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


# ------------------------------------------------------------------ line builders (pure given the amounts)
def service_lines(amount, fee, agent_comm, sup_comm, a):
	"""Customer paid cash amount+fee to the agent; the provider was paid `amount` out of the float."""
	lines = [(a["custody"], amount + fee, 0), (a["provider"], 0, amount)]
	if fee:
		lines.append((a["income"], 0, fee))
	comm = logic.r2(agent_comm + sup_comm)
	if comm:
		lines += [(a["expense"], comm, 0), (a["liability"], 0, comm)]
	return lines


def invert(lines):
	return [(acc, cr, dr) for acc, dr, cr in lines]


def settlement_lines(stage, due, offset, handed, a):
	"""Custody account moves by what really left the sender's hands; see docs/ACCOUNTING.md."""
	diff = logic.settlement_difference(due, offset, handed)
	lines = []
	if offset:
		lines += [(a["liability"], offset, 0), (a["custody"], 0, offset)]
	if diff > 0:  # shortage
		lines += [(a["diff"], diff, 0), (a["custody"], 0, diff)]
	elif diff < 0:  # excess cash
		lines += [(a["custody"], -diff, 0), (a["diff"], 0, -diff)]
	if stage == "Supervisor to Manager":
		# cash leaves the agents' custody and reaches the company cash account
		lines += [(a["cash"], handed, 0), (a["custody"], 0, handed)]
	return lines


def accounts_map(flow):
	require(flow)
	s = settings()
	return {k: s.get(f) for k, f in FIELDS.items()}


# ------------------------------------------------------------------ documents
def payment_entry(txn, party_type, invoice_doctype, invoice_name, amount):
	"""Payment Entry from the provider clearing account against an invoice (receive for sales, pay for purchases)."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	s = settings()
	pe = get_payment_entry(invoice_doctype, invoice_name, party_amount=amount)
	if party_type == "Customer":
		pe.paid_to = s.provider_clearing_account
		pe.paid_to_account_currency = frappe.db.get_value("Account", s.provider_clearing_account, "account_currency")
	else:
		pe.paid_from = s.provider_clearing_account
		pe.paid_from_account_currency = frappe.db.get_value("Account", s.provider_clearing_account, "account_currency")
	pe.mode_of_payment = s.mode_of_payment
	pe.reference_no = txn.provider_ref or txn.name
	pe.reference_date = nowdate()
	pe.pn_transaction = txn.name
	pe.flags.pn_engine = True
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def advance_payment_entry(txn, customer, amount, note):
	"""Unallocated receipt from a customer (e.g. a POS invoice that is not consolidated yet)."""
	s = settings()
	from erpnext.accounts.party import get_party_account

	pe = frappe.get_doc({
		"doctype": "Payment Entry", "payment_type": "Receive", "party_type": "Customer", "party": customer,
		"company": s.company, "posting_date": nowdate(), "mode_of_payment": s.mode_of_payment,
		"paid_from": get_party_account("Customer", customer, s.company), "paid_to": s.provider_clearing_account,
		"paid_amount": amount, "received_amount": amount, "reference_no": txn.provider_ref or txn.name,
		"reference_date": nowdate(), "remarks": note, "pn_transaction": txn.name,
	})
	pe.flags.pn_engine = True
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def cancel_doc(doctype, name):
	if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
		doc = frappe.get_doc(doctype, name)
		doc.flags.pn_engine = True
		doc.cancel()


# ------------------------------------------------------------------ account setup
def ensure_accounts():
	"""Create the seven accounts under the standard groups of the company (skips the ones already set)."""
	s = frappe.get_doc("Payment Settings")
	if not s.company:
		frappe.throw(_("Set the company in Payment Settings first"))
	company = s.company
	spec = [
		("agent_custody_account", "Payment Agents Cash Custody", "Asset", "Current Assets"),
		("provider_clearing_account", "Payment Provider Clearing", "Asset", "Current Assets"),
		("wallet_liability_account", "Payment Wallet Balances", "Liability", "Current Liabilities"),
		("commission_income_account", "Payment Commission Income", "Income", "Indirect Income"),
		("commission_expense_account", "Payment Agents Commission", "Expense", "Indirect Expenses"),
		("difference_account", "Payment Cash Differences", "Expense", "Indirect Expenses"),
	]
	made = []
	for field, name, root, group in spec:
		if s.get(field):
			continue
		parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": root,
			"account_name": ["like", f"{group}%"]}, "name") or frappe.db.get_value(
			"Account", {"company": company, "is_group": 1, "root_type": root}, "name", order_by="lft")
		if not parent:
			frappe.throw(_("No {0} group account found for {1}").format(_(root), company))
		existing = frappe.db.get_value("Account", {"company": company, "account_name": name}, "name")
		acc = existing or frappe.get_doc({"doctype": "Account", "account_name": name, "company": company,
			"parent_account": parent, "is_group": 0, "root_type": root}).insert(ignore_permissions=True).name
		s.set(field, acc)
		made.append(acc)
	s.save(ignore_permissions=True)
	_link_mode_of_payment(company, s.provider_clearing_account)
	return made


def _link_mode_of_payment(company, account):
	name = settings().mode_of_payment or "Electronic Payment"
	if not frappe.db.exists("Mode of Payment", name):
		frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": name, "type": "Bank"}).insert(ignore_permissions=True)
	mop = frappe.get_doc("Mode of Payment", name)
	if account and not any(r.company == company for r in mop.accounts):
		mop.append("accounts", {"company": company, "default_account": account})
		mop.save(ignore_permissions=True)
