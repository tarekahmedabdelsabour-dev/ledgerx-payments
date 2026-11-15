import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conditions = {}
	if filters.get("role_type"):
		conditions["role_type"] = filters.role_type
	if filters.get("company"):
		conditions["company"] = filters.company

	rows = frappe.get_list(
		"Agent Wallet",
		filters=conditions,
		fields=[
			"name", "agent_name", "role_type", "balance", "commission_balance",
			"custody_balance", "last_entry_at",
		],
		order_by="agent_name asc",
		limit_page_length=0,
	)

	data = [
		{
			"wallet": r.name,
			"agent_name": r.agent_name,
			"role_type": r.role_type,
			"balance": r.balance,
			"commission_balance": r.commission_balance,
			"custody_balance": r.custody_balance,
			"last_entry_at": r.last_entry_at,
		}
		for r in rows
	]
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Wallet"), "fieldname": "wallet", "fieldtype": "Link", "options": "Agent Wallet", "width": 130},
		{"label": _("Name"), "fieldname": "agent_name", "fieldtype": "Data", "width": 170},
		{"label": _("Role Type"), "fieldname": "role_type", "fieldtype": "Data", "width": 100},
		{"label": _("Available Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 140},
		{"label": _("Commission Balance"), "fieldname": "commission_balance", "fieldtype": "Currency", "width": 150},
		{"label": _("Cash Held"), "fieldname": "custody_balance", "fieldtype": "Currency", "width": 130},
		{"label": _("Last Entry"), "fieldname": "last_entry_at", "fieldtype": "Datetime", "width": 160},
	]
