import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, now_datetime, time_diff_in_seconds, today

STATUSES = ["Failed", "Processing", "Pending"]
NON_FINAL = ("Processing", "Pending")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.get("from_date") or get_first_day(today()))
	to_date = getdate(filters.get("to_date") or today())

	status = filters.get("status")
	statuses = [status] if status in STATUSES else STATUSES

	rows = frappe.get_list(
		"Payment Transaction",
		filters=[
			["status", "in", statuses],
			["creation", ">=", from_date],
			["creation", "<", add_days(to_date, 1)],
		],
		fields=[
			"name", "creation", "agent", "agent_name", "service", "customer_reference",
			"amount", "status", "provider_status", "failure_reason", "started_at",
			"approval_request",
		],
		order_by="creation desc",
		limit_page_length=0,
	)

	now = now_datetime()
	data = []
	for r in rows:
		age = None
		if r.status in NON_FINAL:
			since = r.started_at or r.creation
			if since:
				age = round(flt(time_diff_in_seconds(now, since)) / 60, 1)
		data.append({
			"transaction": r.name,
			"creation": r.creation,
			"agent": r.agent,
			"agent_name": r.agent_name,
			"service": r.service,
			"customer_reference": r.customer_reference,
			"amount": r.amount,
			"status": r.status,
			"provider_status": r.provider_status,
			"failure_reason": r.failure_reason,
			"age_minutes": age,
			"approval_request": r.approval_request,
		})
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Transaction"), "fieldname": "transaction", "fieldtype": "Link", "options": "Payment Transaction", "width": 130},
		{"label": _("Created"), "fieldname": "creation", "fieldtype": "Datetime", "width": 160},
		{"label": _("Agent"), "fieldname": "agent", "fieldtype": "Link", "options": "Payment Agent Profile", "hidden": 1, "width": 100},
		{"label": _("Agent Name"), "fieldname": "agent_name", "fieldtype": "Data", "width": 150},
		{"label": _("Service"), "fieldname": "service", "fieldtype": "Link", "options": "Payment Service", "width": 140},
		{"label": _("Customer Reference"), "fieldname": "customer_reference", "fieldtype": "Data", "width": 150},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Provider Status"), "fieldname": "provider_status", "fieldtype": "Data", "width": 130},
		{"label": _("Failure Reason"), "fieldname": "failure_reason", "fieldtype": "Data", "width": 220},
		{"label": _("Age (Minutes)"), "fieldname": "age_minutes", "fieldtype": "Float", "precision": 1, "width": 110},
		{"label": _("Approval Request"), "fieldname": "approval_request", "fieldtype": "Link", "options": "Payment Approval Request", "width": 140},
	]
