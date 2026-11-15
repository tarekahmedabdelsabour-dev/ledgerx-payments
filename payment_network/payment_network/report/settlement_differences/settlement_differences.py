import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.get("from_date") or get_first_day(today()))
	to_date = getdate(filters.get("to_date") or today())

	conditions = {
		"docstatus": 1,
		"difference": ["!=", 0],
		"settlement_date": ["between", [from_date, to_date]],
	}
	if filters.get("stage"):
		conditions["stage"] = filters.stage
	if filters.get("from_profile"):
		conditions["from_profile"] = filters.from_profile

	rows = frappe.get_list(
		"Cash Settlement",
		filters=conditions,
		fields=[
			"name", "settlement_date", "stage", "from_profile", "to_profile", "amount_due",
			"commission_offset", "amount_handed", "difference", "confirmed_by",
		],
		order_by="settlement_date desc, creation desc",
		limit_page_length=0,
	)

	data = [
		{
			"settlement": r.name,
			"settlement_date": r.settlement_date,
			"stage": r.stage,
			"from_profile": r.from_profile,
			"to_profile": r.to_profile,
			"amount_due": r.amount_due,
			"commission_offset": r.commission_offset,
			"amount_handed": r.amount_handed,
			"difference": r.difference,
			"confirmed_by": r.confirmed_by,
		}
		for r in rows
	]
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Settlement"), "fieldname": "settlement", "fieldtype": "Link", "options": "Cash Settlement", "width": 130},
		{"label": _("Date"), "fieldname": "settlement_date", "fieldtype": "Date", "width": 100},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 170},
		{"label": _("Handed By"), "fieldname": "from_profile", "fieldtype": "Link", "options": "Payment Agent Profile", "width": 130},
		{"label": _("Received By"), "fieldname": "to_profile", "fieldtype": "Link", "options": "Payment Agent Profile", "width": 130},
		{"label": _("Cash Settled"), "fieldname": "amount_due", "fieldtype": "Currency", "width": 120},
		{"label": _("Commission Deducted"), "fieldname": "commission_offset", "fieldtype": "Currency", "width": 150},
		{"label": _("Cash Handed"), "fieldname": "amount_handed", "fieldtype": "Currency", "width": 120},
		{"label": _("Difference (Shortage +, Excess -)"), "fieldname": "difference", "fieldtype": "Currency", "width": 190},
		{"label": _("Confirmed By"), "fieldname": "confirmed_by", "fieldtype": "Link", "options": "User", "width": 160},
	]
