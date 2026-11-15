import frappe
from frappe import _
from frappe.model.document import Document


class PaymentApprovalRequest(Document):
	def before_insert(self):
		if not self.flags.pn_engine:
			frappe.throw(_("Approval requests are created by the system"))

	def validate(self):
		if not self.is_new() and not self.flags.pn_engine:
			before = self.get_doc_before_save()
			if before and before.status != self.status:
				frappe.throw(_("Use the Approve or Reject button"))

	def on_trash(self):
		frappe.throw(_("An approval request cannot be deleted"))

	@frappe.whitelist()
	def approve(self, note=None):
		from payment_network.engine import service

		service.decide(self.name, True, note)

	@frappe.whitelist()
	def reject(self, note=None):
		from payment_network.engine import service

		service.decide(self.name, False, note)
