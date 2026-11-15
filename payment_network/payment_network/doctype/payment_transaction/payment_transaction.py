import frappe
from frappe import _
from frappe.model.document import Document


class PaymentTransaction(Document):
	"""Created and updated only by the payment engine (payment_network.engine.service)."""

	def before_insert(self):
		if not self.flags.pn_engine:
			frappe.throw(_("Transactions are created from the agent screen only"))

	def validate(self):
		if not self.is_new() and not self.flags.pn_engine:
			frappe.throw(_("A transaction cannot be edited"))

	def on_trash(self):
		frappe.throw(_("A transaction cannot be deleted"))

	@frappe.whitelist()
	def reverse(self, reason=None):
		"""Manager: reverse a successful transaction (refund at the provider and undo every entry)."""
		from payment_network import permissions
		from payment_network.engine import audit, service

		if not permissions.is_manager():
			frappe.throw(_("Only a payment manager can reverse a transaction directly"), frappe.PermissionError)
		audit.log("Manager reversal", self.doctype, self.name, {"reason": reason})
		service.reverse(self.name)
