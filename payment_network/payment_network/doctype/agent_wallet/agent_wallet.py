import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

GUARDED = ("balance", "commission_balance", "custody_balance", "profile")


class AgentWallet(Document):
	"""Balances are calculated by the ledger; nobody edits them (not even through the form)."""

	def before_insert(self):
		if not self.flags.pn_ledger:
			frappe.throw(_("Wallets are created automatically with the agent profile"))

	def validate(self):
		before = self.get_doc_before_save()
		if before and not self.flags.pn_ledger:
			for f in GUARDED:
				if flt(before.get(f)) != flt(self.get(f)) if f != "profile" else before.get(f) != self.get(f):
					frappe.throw(_("Wallet balances are calculated from the ledger and cannot be edited"))

	def on_trash(self):
		frappe.throw(_("A wallet cannot be deleted"))

	@frappe.whitelist()
	def verify_balances(self):
		"""Compare the stored balances with the sum of the ledger entries."""
		from payment_network.engine import ledger

		bad = ledger.verify(self.name)
		return {"ok": not bad, "mismatch": bad}
