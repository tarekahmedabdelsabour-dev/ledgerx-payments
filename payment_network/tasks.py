"""Scheduled jobs (declared in hooks.py)."""
import frappe


def review_pending():
	"""Every few minutes: ask the provider about transactions that are still processing."""
	try:
		from payment_network.engine import service

		service.review_pending()
	except Exception:
		frappe.log_error(title="Payment Network: review of pending transactions failed")
