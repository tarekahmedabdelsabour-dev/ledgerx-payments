import frappe
from frappe import _
from frappe.utils import date_diff, flt, today


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conditions = [["custody_balance", ">", 0]]
	if filters.get("supervisor"):
		profiles = frappe.get_list(
			"Payment Agent Profile",
			filters={"supervisor": filters.supervisor},
			pluck="name",
			limit_page_length=0,
		)
		if not profiles:
			return get_columns(), []
		conditions.append(["profile", "in", profiles])

	wallets = frappe.get_list(
		"Agent Wallet",
		filters=conditions,
		fields=["name", "profile", "agent_name", "custody_balance"],
		order_by="custody_balance desc",
		limit_page_length=0,
	)
	if not wallets:
		return get_columns(), []

	profile_names = [w.profile for w in wallets]
	profile_info = {
		p.name: p
		for p in frappe.get_list(
			"Payment Agent Profile",
			filters={"name": ["in", profile_names]},
			fields=["name", "supervisor", "cash_custody_limit"],
			limit_page_length=0,
		)
	}

	last_handover = {
		s.from_profile: s.last_date
		for s in frappe.get_list(
			"Cash Settlement",
			filters={"docstatus": 1, "from_profile": ["in", profile_names]},
			fields=["from_profile", "max(settlement_date) as last_date"],
			group_by="from_profile",
			order_by="from_profile",
			limit_page_length=0,
		)
	}

	data = []
	for w in wallets:
		info = profile_info.get(w.profile) or frappe._dict()
		limit = flt(info.get("cash_custody_limit"))
		last_date = last_handover.get(w.profile)
		data.append({
			"agent": w.profile,
			"agent_name": w.agent_name,
			"supervisor": info.get("supervisor"),
			"custody_balance": w.custody_balance,
			"cash_custody_limit": limit,
			"percent_used": (flt(w.custody_balance) / limit * 100) if limit > 0 else 0,
			"last_handover": last_date,
			"days_since": date_diff(today(), last_date) if last_date else None,
		})
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Agent"), "fieldname": "agent", "fieldtype": "Link", "options": "Payment Agent Profile", "width": 120},
		{"label": _("Agent Name"), "fieldname": "agent_name", "fieldtype": "Data", "width": 160},
		{"label": _("Supervisor"), "fieldname": "supervisor", "fieldtype": "Link", "options": "Payment Agent Profile", "width": 120},
		{"label": _("Cash Held"), "fieldname": "custody_balance", "fieldtype": "Currency", "width": 130},
		{"label": _("Custody Limit"), "fieldname": "cash_custody_limit", "fieldtype": "Currency", "width": 130},
		{"label": _("% of Limit Used"), "fieldname": "percent_used", "fieldtype": "Percent", "width": 120},
		{"label": _("Last Confirmed Handover"), "fieldname": "last_handover", "fieldtype": "Date", "width": 160},
		{"label": _("Days Since Handover"), "fieldname": "days_since", "fieldtype": "Int", "width": 130},
	]
