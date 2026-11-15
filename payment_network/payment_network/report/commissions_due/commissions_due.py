import frappe
from frappe import _
from frappe.utils import add_days, getdate, get_first_day, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.get("from_date") or get_first_day(today()))
	to_date = getdate(filters.get("to_date") or today())

	conditions = [["commission_balance", ">", 0]]
	if filters.get("role_type"):
		conditions.append(["role_type", "=", filters.role_type])

	wallets = frappe.get_list(
		"Agent Wallet",
		filters=conditions,
		fields=["name", "agent_name", "role_type", "commission_balance"],
		order_by="commission_balance desc",
		limit_page_length=0,
	)
	if not wallets:
		return get_columns(), []

	earned = {
		e.wallet: e.total
		for e in frappe.get_list(
			"Wallet Ledger Entry",
			filters=[
				["wallet", "in", [w.name for w in wallets]],
				["bucket", "=", "Commission"],
				["direction", "=", "Credit"],
				["posting_datetime", ">=", from_date],
				["posting_datetime", "<", add_days(to_date, 1)],
			],
			fields=["wallet", "sum(amount) as total"],
			group_by="wallet",
			order_by="wallet",
			limit_page_length=0,
		)
	}

	data = [
		{
			"wallet": w.name,
			"agent_name": w.agent_name,
			"role_type": w.role_type,
			"commission_balance": w.commission_balance,
			"earned_in_period": earned.get(w.name) or 0,
		}
		for w in wallets
	]
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Wallet"), "fieldname": "wallet", "fieldtype": "Link", "options": "Agent Wallet", "width": 130},
		{"label": _("Name"), "fieldname": "agent_name", "fieldtype": "Data", "width": 170},
		{"label": _("Role Type"), "fieldname": "role_type", "fieldtype": "Data", "width": 100},
		{"label": _("Commission Balance (Unsettled)"), "fieldname": "commission_balance", "fieldtype": "Currency", "width": 200},
		{"label": _("Commission Earned in Period"), "fieldname": "earned_in_period", "fieldtype": "Currency", "width": 200},
	]
