"""Backend of the agent's mobile page (/agent-pay). The agent is always the profile of the logged-in user,
never something taken from the request. Money moves only through engine.service."""
import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from payment_network.engine import logic, service

PT = "Payment Transaction"


def _agent():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in"), frappe.AuthenticationError)
	return service.agent_profile()


@frappe.whitelist()
def me():
	p = _agent()
	s = service.settings()
	w = frappe.db.get_value("Agent Wallet", {"profile": p.name}, ["balance", "commission_balance", "custody_balance"], as_dict=True) or {}
	company_currency = frappe.get_cached_value("Company", p.company or s.company, "default_currency") if (p.company or s.company) else None
	return {
		"profile": p.name, "name": p.full_name, "role_type": p.role_type,
		"supervisor": frappe.db.get_value("Payment Agent Profile", p.supervisor, "full_name") if p.supervisor else None,
		"balance": flt(w.get("balance")), "commission": flt(w.get("commission_balance")), "custody": flt(w.get("custody_balance")),
		"custody_limit": flt(p.cash_custody_limit), "txn_limit": flt(p.txn_limit) or flt(s.global_txn_limit),
		"daily_limit": flt(p.daily_limit) or flt(s.global_daily_limit), "daily_used": service.daily_total(p.name),
		"pin_set": bool(p.pin_set), "locked_until": str(p.locked_until) if p.locked_until else None,
		"device_registered": bool(p.device_id), "mode": s.mode, "currency": company_currency or frappe.db.get_default("currency"),
		"approval_threshold": flt(s.approval_threshold),
		"open_settlement": frappe.db.exists("Cash Settlement", {"from_profile": p.name, "docstatus": 0}),
	}


@frappe.whitelist()
def services():
	_agent()
	return frappe.get_all("Payment Service", filters={"enabled": 1}, order_by="category, service_name",
		fields=["name", "service_name", "category", "min_amount", "max_amount", "fee_fixed", "fee_percent",
			"requires_reference", "reference_label"])


@frappe.whitelist()
def quote(service_name, amount):
	_agent()
	svc = frappe.get_doc("Payment Service", service_name)
	amount = logic.r2(amount)
	fee = logic.calc_fee(amount, svc.fee_fixed, svc.fee_percent)
	return {"amount": amount, "fee": fee, "total": logic.r2(amount + fee)}


@frappe.whitelist(methods=["POST"])
def execute(service_name, amount, customer_reference=None, pin=None, idempotency_key=None, customer=None, device_id=None):
	_agent()
	return service.execute(service_name, flt(amount), customer_reference, pin, idempotency_key, customer, device_id)


@frappe.whitelist(methods=["POST"])
def pay_invoice(amount, pin=None, idempotency_key=None, sales_invoice=None, pos_invoice=None, device_id=None):
	_agent()
	return service.pay_invoice(flt(amount), pin, idempotency_key, sales_invoice or None, pos_invoice or None, device_id)


@frappe.whitelist()
def transaction(name):
	p = _agent()
	if frappe.db.get_value(PT, name, "agent") != p.name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return service.result(name)


@frappe.whitelist()
def history(limit=30):
	p = _agent()
	return frappe.get_all(PT, filters={"agent": p.name}, order_by="creation desc", limit=min(cint(limit) or 30, 100),
		fields=["name", "kind", "status", "service", "customer_reference", "amount", "fee", "total_collected",
			"failure_reason", "creation"])


@frappe.whitelist(methods=["POST"])
def change_pin(new_pin, old_pin=None):
	p = _agent()
	service.set_pin(p.name, new_pin, old_pin)
	return True


@frappe.whitelist(methods=["POST"])
def request_reversal(name, reason):
	_agent()
	return service.request_reversal(name, reason)


@frappe.whitelist(methods=["POST"])
def handover(amount, commission_offset=0, amount_handed=None, notes=None):
	"""Draft a settlement to the supervisor; he confirms it (submits) from the desk."""
	p = _agent()
	if not p.supervisor:
		frappe.throw(_("You have no supervisor to hand the cash to"))
	amount = flt(amount)
	doc = frappe.get_doc({
		"doctype": "Cash Settlement", "stage": "Agent to Supervisor", "settlement_date": nowdate(), "from_profile": p.name,
		"to_profile": p.supervisor, "amount_due": amount, "commission_offset": flt(commission_offset),
		"amount_handed": flt(amount_handed) if amount_handed not in (None, "") else amount - flt(commission_offset),
		"notes": notes, "company": p.company})
	doc.insert()
	return {"name": doc.name, "difference": doc.difference}


@frappe.whitelist()
def my_settlements():
	p = _agent()
	return frappe.get_all("Cash Settlement", filters={"from_profile": p.name}, order_by="creation desc", limit=15,
		fields=["name", "settlement_date", "amount_due", "commission_offset", "amount_handed", "difference", "docstatus"])
