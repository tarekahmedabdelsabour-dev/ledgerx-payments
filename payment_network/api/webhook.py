"""Provider callbacks. Guest access is allowed only because the signature is verified (HMAC) before anything happens."""
import frappe
from frappe.rate_limiter import rate_limit

from payment_network.engine import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=300, seconds=60)
def provider_callback():
	raw = frappe.request.get_data() or b""
	headers = {k: v for k, v in (frappe.request.headers or {}).items()}
	try:
		ok = service.handle_webhook(raw, headers)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Payment Network: webhook failed")
		frappe.local.response["http_status_code"] = 500
		return {"ok": False}
	if not ok:
		frappe.local.response["http_status_code"] = 400
		return {"ok": False}
	return {"ok": True}
