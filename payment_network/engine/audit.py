"""Audit trail of sensitive operations: who, what, when, from which address and device."""
import json

import frappe
from frappe.utils import now_datetime


def request_info():
	ip = getattr(frappe.local, "request_ip", None)
	try:
		device = frappe.get_request_header("X-Device-Id") or (frappe.form_dict or {}).get("device_id")
	except Exception:
		device = None
	return ip, device


def log(action, ref_doctype=None, ref_name=None, details=None, user=None):
	ip, device = request_info()
	doc = frappe.get_doc({
		"doctype": "Payment Audit Log", "timestamp": now_datetime(), "user": user or frappe.session.user,
		"action": action, "reference_doctype": ref_doctype, "reference_name": ref_name, "ip_address": ip,
		"device_id": device, "details": json.dumps(details, default=str, ensure_ascii=False) if details is not None else None,
	})
	doc.flags.pn_ledger = True
	doc.insert(ignore_permissions=True)
	return doc.name
