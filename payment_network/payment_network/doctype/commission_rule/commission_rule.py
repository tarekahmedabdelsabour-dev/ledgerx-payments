import frappe
from frappe import _
from frappe.model.document import Document

from payment_network.engine import logic


class CommissionRule(Document):
	def validate(self):
		if not logic.shares_valid(self.agent_share, self.supervisor_share, self.company_share):
			frappe.throw(_("The agent, supervisor and company shares must total 100%"))
		if self.basis == "Percent" and not (0 <= (self.percent or 0) <= 100):
			frappe.throw(_("Commission % must be between 0 and 100"))
		if self.basis == "Tiered":
			if not self.tiers:
				frappe.throw(_("Add at least one tier"))
			rows = sorted(self.tiers, key=lambda r: r.from_amount or 0)
			prev_to = None
			for r in rows:
				if r.to_amount and r.to_amount < r.from_amount:
					frappe.throw(_("Row {0}: To Amount is below From Amount").format(r.idx))
				if prev_to is not None and (r.from_amount or 0) <= prev_to:
					frappe.throw(_("Row {0}: tiers overlap").format(r.idx))
				prev_to = r.to_amount if r.to_amount else float("inf")
