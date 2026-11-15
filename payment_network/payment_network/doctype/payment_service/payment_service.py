import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PaymentService(Document):
	def validate(self):
		if flt(self.max_amount) and flt(self.max_amount) < flt(self.min_amount):
			frappe.throw(_("The maximum amount is below the minimum"))
		if flt(self.fee_fixed) < 0 or not (0 <= flt(self.fee_percent) <= 100):
			frappe.throw(_("Check the fee: it cannot be negative and the percent is 0 to 100"))
