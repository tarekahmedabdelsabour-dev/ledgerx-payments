"""Demo data for the Sandbox: 1 manager, 2 supervisors, 4 agents, services, commission rules and a funded float.

    bench --site mysite.localhost execute payment_network.seed.run

Refuses to run in Live mode. Idempotent (running again adds nothing that exists). Demo users share one password,
printed at the end; change or disable them before real use.
"""
import frappe
from frappe.utils import nowdate

PASSWORD = "PnDemo#2026"
USERS = [
	("pn.manager@example.com", "Payment Manager Demo", "Manager", None),
	("pn.supervisor1@example.com", "Supervisor One", "Supervisor", None),
	("pn.supervisor2@example.com", "Supervisor Two", "Supervisor", None),
	("pn.agent1@example.com", "Agent One", "Agent", "pn.supervisor1@example.com"),
	("pn.agent2@example.com", "Agent Two", "Agent", "pn.supervisor1@example.com"),
	("pn.agent3@example.com", "Agent Three", "Agent", "pn.supervisor2@example.com"),
	("pn.agent4@example.com", "Agent Four", "Agent", "pn.supervisor2@example.com"),
]


def run():
	from payment_network.engine import accounting

	s = frappe.get_doc("Payment Settings")
	if s.mode == "Live":
		frappe.throw("The demo data is for Sandbox only")
	company = s.company or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw("Set a default company first")
	s.company = company
	s.save(ignore_permissions=True)
	accounting.ensure_accounts()
	s.reload()
	bank = frappe.db.get_value("Account", {"company": company, "account_type": ["in", ["Cash", "Bank"]], "is_group": 0}, "name")
	if not bank:
		frappe.throw("No cash or bank account found for the company")
	for f in ("cash_account",):
		if not s.get(f):
			s.set(f, bank)
	s.approval_threshold = s.approval_threshold or 5000
	s.save(ignore_permissions=True)

	profiles = {}
	for email, name, role, sup in USERS:
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": name, "send_welcome_email": 0, "new_password": PASSWORD,
				"user_type": "System User"}).insert(ignore_permissions=True)
		profile = frappe.db.get_value("Payment Agent Profile", {"user": email}, "name")
		if not profile:
			doc = frappe.get_doc({"doctype": "Payment Agent Profile", "user": email, "role_type": role,
				"supervisor": profiles.get(sup), "company": company, "txn_limit": 3000, "daily_limit": 20000,
				"cash_custody_limit": 10000, "status": "Active"}).insert(ignore_permissions=True)
			profile = doc.name

			frappe.db.set_value("Payment Agent Profile", profile, "pin_set", 0)
			_pin(profile, "1234")
		profiles[email] = profile

	rule = _rule("Standard 1%", "Percent", percent=1)
	tiered = _rule("Bills Tiered", "Tiered", tiers=[
		{"from_amount": 0, "to_amount": 100, "commission_amount": 1, "commission_percent": 0},
		{"from_amount": 100.01, "to_amount": 1000, "commission_amount": 0, "commission_percent": 1.5},
		{"from_amount": 1000.01, "to_amount": 0, "commission_amount": 15, "commission_percent": 0.5}])
	for name, cat, fee_fixed, fee_pct, r in [("Electricity Bill", "Bill Payment", 2, 0, tiered), ("Water Bill", "Bill Payment", 2, 0, tiered),
			("Mobile Top-up", "Mobile Top-up", 0, 1, rule), ("Internet Bill", "Bill Payment", 3, 0, rule), ("Gift Voucher", "Voucher", 0, 2, rule)]:
		if not frappe.db.exists("Payment Service", name):
			frappe.get_doc({"doctype": "Payment Service", "service_name": name, "category": cat, "fee_fixed": fee_fixed,
				"fee_percent": fee_pct, "commission_rule": r, "min_amount": 5, "max_amount": 3000, "provider_code": name.upper().replace(" ", "_")}).insert(ignore_permissions=True)

	# a funded float: company -> manager -> supervisors -> agents (only when the manager wallet is empty)
	mgr = profiles["pn.manager@example.com"]
	if not frappe.db.get_value("Agent Wallet", mgr, "balance"):
		_charge("Company Funding", None, mgr, 200000, funding=bank, company=company)
		for sup in ("pn.supervisor1@example.com", "pn.supervisor2@example.com"):
			_charge("Transfer", mgr, profiles[sup], 50000)
		for email, _n, role, sup in USERS:
			if role == "Agent":
				_charge("Transfer", profiles[sup], profiles[email], 10000)
	frappe.db.commit()
	return {"password": PASSWORD, "pin": "1234", "users": [u[0] for u in USERS]}


def _pin(profile, pin):
	from payment_network.engine import logic

	frappe.db.set_value("Payment Agent Profile", profile, {"pin_hash": logic.hash_pin(pin), "pin_set": 1})


def _rule(name, basis, percent=0, tiers=None):
	if not frappe.db.exists("Commission Rule", name):
		frappe.get_doc({"doctype": "Commission Rule", "rule_name": name, "basis": basis, "percent": percent, "tiers": tiers or [],
			"agent_share": 60, "supervisor_share": 20, "company_share": 20}).insert(ignore_permissions=True)
	return name


def _charge(kind, frm, to, amount, funding=None, company=None):
	doc = frappe.get_doc({"doctype": "Wallet Charge", "charge_type": kind, "from_profile": frm, "to_profile": to, "amount": amount,
		"funding_account": funding, "company": company, "posting_date": nowdate(), "remarks": "Demo float"})
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
