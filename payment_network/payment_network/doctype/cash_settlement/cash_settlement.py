import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from payment_network import permissions
from payment_network.engine import accounting, audit, ledger, logic

PROFILE = "Payment Agent Profile"


class CashSettlement(Document):
	"""Cash handed up the chain. The receiver confirms by submitting; a submitted settlement is locked."""

	def validate(self):
		self.company = self.company or frappe.db.get_single_value("Payment Settings", "company")
		frm = frappe.db.get_value(PROFILE, self.from_profile, ["name", "role_type", "supervisor", "user", "status"], as_dict=True)
		to = frappe.db.get_value(PROFILE, self.to_profile, ["name", "role_type", "user", "status"], as_dict=True)
		if not frm or not to:
			frappe.throw(_("Choose who hands over and who receives"))
		if not logic.settlement_stage_ok(self.stage, frm.role_type, to.role_type, frm.supervisor == to.name):
			frappe.throw(_("The stage does not match the people: an agent hands to his own supervisor, a supervisor hands to a manager"))
		if not (permissions.is_manager() or frappe.session.user in (frm.user, to.user)):
			frappe.throw(_("Only the sender, the receiver or a manager can work on this settlement"), frappe.PermissionError)
		w = frappe.db.get_value("Agent Wallet", {"profile": frm.name}, ["custody_balance", "commission_balance"], as_dict=True) or {}
		self.custody_before = flt(w.get("custody_balance"))
		self.amount_due = logic.r2(self.amount_due)
		self.commission_offset = logic.r2(self.commission_offset)
		self.amount_handed = logic.r2(self.amount_handed)
		if self.amount_due <= 0:
			frappe.throw(_("Cash Being Settled must be greater than zero"))
		if self.amount_due > flt(w.get("custody_balance")) + 0.005:
			frappe.throw(_("The sender holds only {0} in cash").format(flt(w.get("custody_balance"))))
		if self.commission_offset < 0 or self.commission_offset > flt(w.get("commission_balance")) + 0.005 or self.commission_offset > self.amount_due:
			frappe.throw(_("The deducted commission cannot be more than the earned commission ({0}) or the cash settled").format(flt(w.get("commission_balance"))))
		if self.amount_handed < 0:
			frappe.throw(_("Cash Actually Handed cannot be negative"))
		self.difference = logic.settlement_difference(self.amount_due, self.commission_offset, self.amount_handed)

	def before_submit(self):
		to_user = frappe.db.get_value(PROFILE, self.to_profile, "user")
		if not (permissions.is_manager() or frappe.session.user == to_user):
			frappe.throw(_("Only the receiver confirms a settlement"), frappe.PermissionError)
		accounting.require("settlement")

	def on_submit(self):
		a = accounting.accounts_map("settlement")
		fw, tw = ledger.wallet_of(self.from_profile), ledger.wallet_of(self.to_profile)
		ledger.lock([fw, tw])
		try:
			ledger.post(fw, "Cash Held", "Debit", self.amount_due, self.doctype, self.name, remarks=_("Cash settled"))
			if self.commission_offset:
				ledger.post(fw, "Commission", "Debit", self.commission_offset, self.doctype, self.name, remarks=_("Commission deducted"))
		except ledger.InsufficientBalance:
			frappe.throw(_("The sender's cash or commission balance changed and is not enough now. Reload and correct the amounts."))
		if self.stage == "Agent to Supervisor" and self.amount_handed > 0:
			ledger.post(tw, "Cash Held", "Credit", self.amount_handed, self.doctype, self.name, remarks=_("Cash received"))
		je = accounting.make_je(accounting.settlement_lines(self.stage, self.amount_due, self.commission_offset, self.amount_handed, a),
			_("Cash settlement {0}").format(self.name), f"{self.doctype} {self.name}", posting_date=self.settlement_date)
		self.db_set({"confirmed_by": frappe.session.user, "journal_entry": je})
		audit.log("Settlement confirmed", self.doctype, self.name, {"due": self.amount_due, "handed": self.amount_handed, "difference": self.difference})

	def on_cancel(self):
		frappe.throw(_("A confirmed settlement cannot be cancelled"))
