"""Desk-side actions for managers."""
import frappe
from frappe.utils import flt

from payment_network.engine import service


@frappe.whitelist(methods=["POST"])
def pay_supplier(purchase_invoice, amount, idempotency_key, supplier_reference=None):
	"""Pay a supplier through the provider (needs "Allow Paying Suppliers Electronically" in Payment Settings)."""
	return service.pay_supplier(purchase_invoice, flt(amount), idempotency_key, supplier_reference)
