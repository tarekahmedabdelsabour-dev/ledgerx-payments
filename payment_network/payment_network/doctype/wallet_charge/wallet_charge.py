import frappe
from frappe import _
from frappe.model.document import Document


from payment_network import permissions
from payment_network.engine import accounting, audit, ledger, logic

PROFILE = "Payment Agent Profile"


class WalletCharge(Document):
	"""Charging a wallet: two opposite ledger entries (sender debited, receiver credited), or company funding of a manager."""

	def validate(self):
		self.amount = logic.r2(self.amount)
		if self.amount <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		self.company = self.company or frappe.db.get_single_value("Payment Settings", "company")
		to = frappe.db.get_value(PROFILE, self.to_profile, ["name", "role_type", "status", "supervisor"], as_dict=True)
		if not to or to.status != "Active":
			frappe.throw(_("The receiving profile must be active"))
		if self.charge_type == "Company Funding":
			if not permissions.is_manager():
				frappe.throw(_("Only a payment manager can fund the company wallet"), frappe.PermissionError)
			if to.role_type != "Manager":
				frappe.throw(_("Company funding goes to a manager's wallet"))
			if not self.funding_account:
				frappe.throw(_("Choose the bank or cash account the money comes from"))
			acc = frappe.db.get_value("Account", self.funding_account, ["account_type", "is_group", "company"], as_dict=True)
			if not acc or acc.is_group or acc.account_type not in ("Bank", "Cash") or (self.company and acc.company != self.company):
				frappe.throw(_("The funding account must be a bank or cash account of the company"))
			self.from_profile = None
			return
		self.funding_account = None
		frm = frappe.db.get_value(PROFILE, self.from_profile, ["name", "role_type", "status", "supervisor", "user"], as_dict=True)
		if not frm or frm.status != "Active":
			frappe.throw(_("The sending profile must be active"))
		if frm.name == to.name:
			frappe.throw(_("Sender and receiver must be different"))
		linked = (to.supervisor == frm.name) or (frm.supervisor == to.name)
		if not logic.transfer_allowed(frm.role_type, to.role_type, linked):
			frappe.throw(_("A transfer goes along the chain manager, supervisor, agent (an agent only under his own supervisor)"))
		if not permissions.is_manager():
			mine = permissions.profile_of()
			if not mine or mine.name != frm.name:
				frappe.throw(_("You can only transfer from your own wallet"), frappe.PermissionError)

	def before_submit(self):
		if self.charge_type == "Company Funding":
			accounting.require("funding")

	def on_submit(self):
		to_w = ledger.wallet_of(self.to_profile)
		try:
			if self.charge_type == "Company Funding":
				ledger.lock([to_w])
				ledger.post(to_w, "Available", "Credit", self.amount, self.doctype, self.name, remarks=self.remarks)
				a = accounting.accounts_map("funding")
				je = accounting.make_je([(a["provider"], self.amount, 0), (self.funding_account, 0, self.amount)],
					_("Funding of the payment float {0}").format(self.name), f"{self.doctype} {self.name}", posting_date=self.posting_date)
				self.db_set("journal_entry", je)
			else:
				ledger.transfer(ledger.wallet_of(self.from_profile), to_w, self.amount, "Available", self.doctype, self.name, self.remarks)
		except ledger.InsufficientBalance:
			frappe.throw(_("The sender's balance is not enough for this transfer"))
		audit.log("Wallet charged", self.doctype, self.name, {"amount": self.amount, "from": self.from_profile, "to": self.to_profile})

	def on_cancel(self):
		frappe.throw(_("A posted charge cannot be cancelled. Post a return transfer instead."))
