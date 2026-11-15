import frappe
from frappe import _
from frappe.model.document import Document


class PaymentAuditLog(Document):
	"""Append-only: created by the system, never edited, deleted or cancelled."""

	def before_insert(self):
		if not self.flags.pn_ledger:
			frappe.throw(_("This record is created by the system only"))

	def validate(self):
		if not self.is_new():
			frappe.throw(_("This record cannot be changed"))

	def on_trash(self):
		frappe.throw(_("This record cannot be deleted"))
