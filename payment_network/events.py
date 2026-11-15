"""doc_events on the standard documents (declared in hooks.py)."""
import frappe
from frappe import _


def block_cancel(doc, method=None):
	"""A Journal/Payment Entry made by a payment transaction is undone by reversing the transaction, not by cancelling it."""
	if doc.flags.get("pn_engine"):
		return
	txn = doc.get("pn_transaction")
	if txn and frappe.db.get_value("Payment Transaction", txn, "status") in ("Success", "Processing"):
		frappe.throw(_("This entry belongs to payment transaction {0}. Reverse the transaction instead of cancelling the entry.").format(txn))
	if doc.get("pn_source") and not txn:
		frappe.throw(_("This entry was made by the payment network ({0}) and cannot be cancelled by hand.").format(doc.pn_source))


def user_updated(doc, method=None):
	"""Disabling a user suspends his payment profile."""
	if not doc.enabled and frappe.db.exists("Payment Agent Profile", {"user": doc.name, "status": "Active"}):
		frappe.db.set_value("Payment Agent Profile", {"user": doc.name}, "status", "Suspended")
