import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

ACCOUNT_FIELDS = ("agent_custody_account", "provider_clearing_account", "wallet_liability_account",
	"commission_income_account", "commission_expense_account", "cash_account", "difference_account")


class PaymentSettings(Document):
	def validate(self):
		from payment_network.providers.registry import PROVIDERS

		if self.mode == "Live" and (self.provider or "Mock") == "Mock":
			frappe.throw(_("Live mode needs a real payment provider. Choose one first."))
		if (self.provider or "Mock") not in PROVIDERS:
			frappe.throw(_("Payment provider {0} is not installed").format(self.provider))
		for f in ("global_txn_limit", "global_daily_limit", "approval_threshold"):
			if flt(self.get(f)) < 0:
				frappe.throw(_("{0} cannot be negative").format(_(self.meta.get_label(f))))
		if self.company:
			for f in ACCOUNT_FIELDS:
				acc = self.get(f)
				if acc and frappe.db.get_value("Account", acc, "company") != self.company:
					frappe.throw(_("{0} must belong to {1}").format(_(self.meta.get_label(f)), self.company))
				if acc and frappe.db.get_value("Account", acc, "is_group"):
					frappe.throw(_("{0} must not be a group account").format(_(self.meta.get_label(f))))


@frappe.whitelist()
def create_accounts():
	"""Create the missing accounts under the standard groups (preview them first in docs/ACCOUNTING.md)."""
	from payment_network import permissions
	from payment_network.engine import accounting, audit

	if not permissions.is_manager():
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	made = accounting.ensure_accounts()
	audit.log("Accounts created", "Payment Settings", "Payment Settings", {"accounts": made})
	frappe.clear_cache()
	return made


@frappe.whitelist()
def webhook_url():
	return frappe.utils.get_url("/api/method/payment_network.api.webhook.provider_callback")
