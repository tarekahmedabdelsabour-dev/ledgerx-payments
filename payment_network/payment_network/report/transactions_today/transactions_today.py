import frappe
from frappe import _
from frappe.utils import add_days, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	day = getdate(filters.get("date") or today())

	conditions = [
		["creation", ">=", day],
		["creation", "<", add_days(day, 1)],
	]
	for key in ("agent", "service", "status"):
		if filters.get(key):
			conditions.append([key, "=", filters.get(key)])

	rows = frappe.get_list(
		"Payment Transaction",
		filters=conditions,
		fields=[
			"name", "creation", "agent", "agent_name", "service", "customer_reference",
			"amount", "fee", "total_collected", "status", "provider_ref",
		],
		order_by="creation desc",
		limit_page_length=0,
	)

	data = []
	by_status = {}
	for r in rows:
		data.append({
			"transaction": r.name,
			"time": r.creation.strftime("%H:%M:%S") if r.creation else "",
			"agent": r.agent,
			"agent_name": r.agent_name,
			"service": r.service,
			"customer_reference": r.customer_reference,
			"amount": r.amount,
			"fee": r.fee,
			"total_collected": r.total_collected,
			"status": r.status,
			"provider_ref": r.provider_ref,
		})
		by_status[r.status] = by_status.get(r.status, 0) + 1

	chart = None
	if by_status:
		chart = {
			"data": {"labels": [_(s) for s in by_status], "datasets": [{"name": _("Transactions"), "values": list(by_status.values())}]},
			"type": "bar",
		}

	return get_columns(), data, None, chart


def get_columns():
	return [
		{"label": _("Transaction"), "fieldname": "transaction", "fieldtype": "Link", "options": "Payment Transaction", "width": 130},
		{"label": _("Time"), "fieldname": "time", "fieldtype": "Data", "width": 80},
		{"label": _("Agent"), "fieldname": "agent", "fieldtype": "Link", "options": "Payment Agent Profile", "hidden": 1, "width": 100},
		{"label": _("Agent Name"), "fieldname": "agent_name", "fieldtype": "Data", "width": 150},
		{"label": _("Service"), "fieldname": "service", "fieldtype": "Link", "options": "Payment Service", "width": 140},
		{"label": _("Customer Reference"), "fieldname": "customer_reference", "fieldtype": "Data", "width": 150},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Fee"), "fieldname": "fee", "fieldtype": "Currency", "width": 90},
		{"label": _("Total Collected"), "fieldname": "total_collected", "fieldtype": "Currency", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Provider Reference"), "fieldname": "provider_ref", "fieldtype": "Data", "width": 150},
	]
