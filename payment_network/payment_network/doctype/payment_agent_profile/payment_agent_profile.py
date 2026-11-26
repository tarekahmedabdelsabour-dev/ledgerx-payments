import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

ROLE_OF = {"Agent": "Payment Agent", "Supervisor": "Payment Supervisor", "Manager": "Payment Manager"}


class PaymentAgentProfile(Document):
	def validate(self):
		for f in ("txn_limit", "daily_limit", "cash_custody_limit"):
			if flt(self.get(f)) < 0:
				frappe.throw(_("{0} cannot be negative").format(_(self.meta.get_label(f))))
		if self.role_type != "Agent":
			self.supervisor = None
		elif self.supervisor:
			sup = frappe.db.get_value("Payment Agent Profile", self.supervisor, ["role_type", "name"], as_dict=True)
			if not sup or sup.role_type != "Supervisor" or sup.name == self.name:
				frappe.throw(_("The supervisor must be a profile with the Supervisor role type"))
		if not self.company:
			self.company = frappe.db.get_single_value("Payment Settings", "company")
		if not self.is_new():
			before = self.get_doc_before_save()
			if before and before.role_type != self.role_type and frappe.db.exists("Payment Transaction", {"agent": self.name}):
				frappe.throw(_("The role type cannot change after the profile has transactions"))
			if before and before.status != self.status:
				from payment_network.engine import audit

				audit.log(f"Profile {self.status}", self.doctype, self.name)

	def after_insert(self):
		from payment_network.engine import ledger

		ledger.wallet_of(self.name)
		self.ensure_role()

	def on_update(self):
		self.ensure_role()

	def ensure_role(self):
		role = ROLE_OF[self.role_type]
		if self.user and not frappe.db.exists("Has Role", {"parent": self.user, "role": role, "parenttype": "User"}):
			user = frappe.get_doc("User", self.user)
			user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		# a changed role type must not leave the previous payment role behind (unless another profile of the user needs it)
		if self.user:
			stale = [r for k, r in ROLE_OF.items() if r != role and not frappe.db.exists(
				"Payment Agent Profile", {"user": self.user, "role_type": k, "name": ["!=", self.name]})]
			for r in stale:
				frappe.db.delete("Has Role", {"parent": self.user, "parenttype": "User", "role": r})

	def on_trash(self):
		if frappe.db.exists("Wallet Ledger Entry", {"agent": self.name}) or frappe.db.exists("Payment Transaction", {"agent": self.name}):
			frappe.throw(_("A profile with activity cannot be deleted. Suspend it instead."))

	@frappe.whitelist()
	def set_pin(self, pin):
		from payment_network.engine import service

		service.set_pin(self.name, pin)

	@frappe.whitelist(methods=["POST"])
	def reset_device(self):
		from payment_network import permissions
		from payment_network.engine import audit

		if not permissions.is_manager():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		frappe.db.set_value(self.doctype, self.name, {"device_id": None, "pending_device_id": None})
		audit.log("Device reset", self.doctype, self.name)

	@frappe.whitelist(methods=["POST"])
	def approve_device(self):
		from payment_network import permissions
		from payment_network.engine import audit

		if not permissions.is_manager():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		pending = frappe.db.get_value(self.doctype, self.name, "pending_device_id")
		if not pending:
			frappe.throw(_("No device is waiting for approval"))
		frappe.db.set_value(self.doctype, self.name, {"device_id": pending, "pending_device_id": None})
		audit.log("Device approved", self.doctype, self.name, {"device_id": pending})

	@frappe.whitelist()
	def unlock(self):
		from payment_network import permissions
		from payment_network.engine import audit

		if not permissions.is_manager():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		frappe.db.set_value(self.doctype, self.name, {"locked_until": None, "failed_pin_attempts": 0})
		audit.log("PIN unlocked", self.doctype, self.name)
