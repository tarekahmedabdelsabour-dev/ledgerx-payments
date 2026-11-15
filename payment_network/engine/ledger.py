"""The wallet ledger: the only code that changes a wallet balance.

Every change is an append-only Wallet Ledger Entry plus the matching update of the wallet's balance,
both made while the wallet row is locked (SELECT ... FOR UPDATE), so two operations on the same wallet
can never both spend the same money.
"""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from payment_network.engine import logic


class InsufficientBalance(frappe.ValidationError):
	pass


def wallet_of(profile, create=True):
	name = frappe.db.get_value("Agent Wallet", {"profile": profile}, "name")
	if name or not create:
		return name
	company = frappe.db.get_value("Payment Agent Profile", profile, "company")
	doc = frappe.get_doc({"doctype": "Agent Wallet", "profile": profile, "company": company})
	doc.flags.pn_ledger = True
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Payment Agent Profile", profile, "wallet", doc.name, update_modified=False)
	return doc.name


def lock(wallets):
	"""Lock wallet rows in a fixed order (no deadlocks between two transfers going opposite ways)."""
	names = sorted({w for w in wallets if w})
	if names:
		frappe.db.sql("SELECT name FROM `tabAgent Wallet` WHERE name IN %(n)s ORDER BY name FOR UPDATE", {"n": tuple(names)})


def post(wallet, bucket, direction, amount, ref_doctype=None, ref_name=None, group=None, remarks=None, allow_negative=False):
	amount = logic.r2(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero"))
	field = logic.BUCKET_FIELD[bucket]
	row = frappe.db.get_value("Agent Wallet", wallet, [field, "profile", "company"], as_dict=True, for_update=True)
	if not row:
		frappe.throw(_("Wallet {0} not found").format(wallet))
	new = logic.apply_entry(flt(row[field]), direction, amount)
	if new < 0 and not allow_negative:
		raise InsufficientBalance(_("Insufficient balance in {0}").format(_(bucket)))
	now = now_datetime()
	entry = frappe.get_doc({
		"doctype": "Wallet Ledger Entry", "wallet": wallet, "agent": row.profile, "bucket": bucket,
		"direction": direction, "amount": amount, "balance_after": new, "posting_datetime": now,
		"reference_doctype": ref_doctype, "reference_name": ref_name, "group_id": group, "remarks": remarks,
	})
	entry.flags.pn_ledger = True
	entry.insert(ignore_permissions=True)
	frappe.db.set_value("Agent Wallet", wallet, {field: new, "last_entry_at": now}, update_modified=False)
	return entry.name


def transfer(from_wallet, to_wallet, amount, bucket="Available", ref_doctype=None, ref_name=None, remarks=None):
	"""Two opposite entries in one go: debit the sender, credit the receiver."""
	lock([from_wallet, to_wallet])
	group = frappe.generate_hash(length=12)
	post(from_wallet, bucket, "Debit", amount, ref_doctype, ref_name, group, remarks)
	post(to_wallet, bucket, "Credit", amount, ref_doctype, ref_name, group, remarks)
	return group


def verify(wallet):
	"""Balances recomputed from the entries; returns {field: (stored, calculated)} for every mismatch."""
	rows = frappe.db.sql(
		"SELECT bucket, SUM(IF(direction='Credit', amount, -amount)) FROM `tabWallet Ledger Entry` WHERE wallet=%s GROUP BY bucket",
		wallet)
	calc = {logic.BUCKET_FIELD[b]: logic.r2(v) for b, v in rows}
	stored = frappe.db.get_value("Agent Wallet", wallet, list(logic.BUCKET_FIELD.values()), as_dict=True)
	out = {}
	for field in logic.BUCKET_FIELD.values():
		if logic.r2(stored[field]) != calc.get(field, 0.0):
			out[field] = (logic.r2(stored[field]), calc.get(field, 0.0))
	return out
