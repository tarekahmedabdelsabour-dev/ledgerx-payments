import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.get("from_date") or get_first_day(today()))
	to_date = getdate(filters.get("to_date") or today())
	group_field = "supervisor" if filters.get("group_by") == "Supervisor" else "agent"

	base = [
		["creation", ">=", from_date],
		["creation", "<", add_days(to_date, 1)],
	]

	def aggregate(extra_conditions, fields):
		rows = frappe.get_list(
			"Payment Transaction",
			filters=base + extra_conditions,
			fields=[group_field] + fields,
			group_by=group_field,
			order_by=group_field,
			limit_page_length=0,
		)
		return {r.get(group_field): r for r in rows}

	totals = aggregate([], [{"COUNT": "name", "as": "cnt"}])
	success = aggregate(
		[["status", "=", "Success"]],
		[
			{"COUNT": "name", "as": "cnt"},
			{"SUM": "amount", "as": "amount"},
			{"SUM": "fee", "as": "fee"},
			{"SUM": "agent_commission", "as": "agent_commission"},
			{"SUM": "supervisor_commission", "as": "supervisor_commission"},
			{"SUM": "company_commission", "as": "company_commission"},
		],
	)
	failed = aggregate([["status", "=", "Failed"]], [{"COUNT": "name", "as": "cnt"}])

	names = {}
	keys = [k for k in totals if k]
	if keys:
		names = {
			p.name: p.full_name
			for p in frappe.get_list(
				"Payment Agent Profile",
				filters={"name": ["in", keys]},
				fields=["name", "full_name"],
				limit_page_length=0,
			)
		}

	data = []
	for key, t in totals.items():
		s = success.get(key) or {}
		count = t.cnt or 0
		ok = s.get("cnt") or 0
		data.append({
			"group": key,
			"group_name": names.get(key) or key,
			"total_count": count,
			"success_count": ok,
			"failed_count": (failed.get(key) or {}).get("cnt") or 0,
			"success_rate": (ok / count * 100) if count else 0,
			"success_amount": flt(s.get("amount")),
			"fees": flt(s.get("fee")),
			"agent_commission": flt(s.get("agent_commission")),
			"supervisor_commission": flt(s.get("supervisor_commission")),
			"company_commission": flt(s.get("company_commission")),
		})
	data.sort(key=lambda d: d["success_amount"], reverse=True)

	chart = None
	if data:
		chart = {
			"data": {
				"labels": [d["group_name"] or _("Unassigned") for d in data],
				"datasets": [{"name": _("Successful Amount"), "values": [d["success_amount"] for d in data]}],
			},
			"type": "bar",
		}

	return get_columns(filters.get("group_by") or "Agent"), data, None, chart


def get_columns(group_by):
	return [
		{"label": _(group_by), "fieldname": "group", "fieldtype": "Link", "options": "Payment Agent Profile", "width": 120},
		{"label": _("Name"), "fieldname": "group_name", "fieldtype": "Data", "width": 170},
		{"label": _("Transactions"), "fieldname": "total_count", "fieldtype": "Int", "width": 110},
		{"label": _("Successful"), "fieldname": "success_count", "fieldtype": "Int", "width": 100},
		{"label": _("Failed"), "fieldname": "failed_count", "fieldtype": "Int", "width": 90},
		{"label": _("Success Rate %"), "fieldname": "success_rate", "fieldtype": "Percent", "width": 120},
		{"label": _("Successful Amount"), "fieldname": "success_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Fees on Successful"), "fieldname": "fees", "fieldtype": "Currency", "width": 140},
		{"label": _("Agent Commission"), "fieldname": "agent_commission", "fieldtype": "Currency", "width": 140},
		{"label": _("Supervisor Commission"), "fieldname": "supervisor_commission", "fieldtype": "Currency", "width": 150},
		{"label": _("Company Commission"), "fieldname": "company_commission", "fieldtype": "Currency", "width": 150},
	]
