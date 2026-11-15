"""Install and migrate steps. Each step is idempotent and one failing step never aborts a migrate."""
import json
import os

import frappe

MODULE = "Payment Network"
ROLES = ["Payment Agent", "Payment Supervisor", "Payment Manager", "Payment Auditor"]
MODE_OF_PAYMENT = "Electronic Payment"

# Custom Fields on the standard documents. They travel as fixtures (fixtures/custom_field.json, built by
# tools/gen_fixtures.py from this table) and are also re-applied on migrate, so nothing is edited through the UI.
CUSTOM_FIELDS = {
	"Journal Entry": [
		{"fieldname": "pn_source", "label": "Payment Network Source", "fieldtype": "Data", "insert_after": "user_remark"},
		{"fieldname": "pn_transaction", "label": "Payment Transaction", "fieldtype": "Link", "options": "Payment Transaction", "insert_after": "pn_source"},
	],
	"Payment Entry": [
		{"fieldname": "pn_transaction", "label": "Payment Transaction", "fieldtype": "Link", "options": "Payment Transaction", "insert_after": "reference_no"},
	],
	"Sales Invoice": [
		{"fieldname": "pn_transaction", "label": "Last Electronic Payment", "fieldtype": "Link", "options": "Payment Transaction", "insert_after": "po_no"},
	],
	"POS Invoice": [
		{"fieldname": "pn_transaction", "label": "Last Electronic Payment", "fieldtype": "Link", "options": "Payment Transaction", "insert_after": "po_no"},
	],
	"Purchase Invoice": [
		{"fieldname": "pn_transaction", "label": "Last Electronic Payment", "fieldtype": "Link", "options": "Payment Transaction", "insert_after": "bill_no"},
	],
}


def custom_field_docs():
	out = []
	for dt, fields in CUSTOM_FIELDS.items():
		for f in fields:
			out.append({"doctype": "Custom Field", "name": f"{dt}-{f['fieldname']}", "dt": dt, "module": MODULE,
				"read_only": 1, "no_copy": 1, "print_hide": 1, "allow_on_submit": 1, **f})
	return out


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & set(ROLES + ["System Manager"]))


def after_install():
	for fn in (ensure_modules, ensure_roles, ensure_custom_fields, ensure_mode_of_payment):
		_run(fn)
	frappe.clear_cache()


def after_migrate():
	for fn in (ensure_modules, ensure_roles, ensure_custom_fields, ensure_mode_of_payment):
		_run(fn)
	frappe.clear_cache()


def _run(fn):
	try:
		fn()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"payment_network install step failed: {fn.__name__}")


def ensure_modules():
	if not frappe.db.exists("Module Def", MODULE):
		frappe.get_doc({"doctype": "Module Def", "module_name": MODULE, "app_name": "payment_network"}).insert(ignore_permissions=True)


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def ensure_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({dt: [{**f, "read_only": 1, "no_copy": 1, "print_hide": 1, "allow_on_submit": 1} for f in fields]
		for dt, fields in CUSTOM_FIELDS.items()}, update=True)


def ensure_mode_of_payment():
	if not frappe.db.exists("Mode of Payment", MODE_OF_PAYMENT):
		frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": MODE_OF_PAYMENT, "type": "Bank"}).insert(ignore_permissions=True)


def write_fixtures(path):
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(custom_field_docs(), fh, indent=1, ensure_ascii=False)
		fh.write("\n")


if __name__ == "__main__":
	write_fixtures(os.path.join(os.path.dirname(__file__), "fixtures", "custom_field.json"))
