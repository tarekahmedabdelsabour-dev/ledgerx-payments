"""Provider registry. `get_provider()` returns the one selected in Payment Settings.

A real provider: write a PaymentProvider subclass in your own app and put its dotted path in
site_config.json as "payment_network_provider_class", then set the provider to Custom in Payment Settings.
"""
from payment_network.providers.mock import MockProvider


def _secret(site_key, settings, field):
	import frappe

	val = frappe.conf.get(site_key)
	if val:
		return val
	try:
		return settings.get_password(field, raise_exception=False)
	except Exception:
		return None


def get_provider(settings=None):
	import frappe
	from frappe import _

	settings = settings or frappe.get_single("Payment Settings")
	api_key = _secret("payment_network_api_key", settings, "provider_api_key")
	secret = _secret("payment_network_webhook_secret", settings, "webhook_secret")
	if settings.provider == "Custom":
		path = frappe.conf.get("payment_network_provider_class")
		if not path:
			frappe.throw(_("Set payment_network_provider_class in the site configuration"))
		cls = frappe.get_attr(path)
		return cls(settings=settings, api_key=api_key, secret=secret)
	return MockProvider(settings=settings, api_key=api_key, secret=secret)
