"""Provider name (as chosen in Payment Settings) -> adapter class."""
import frappe
from frappe import _

from payment_network.providers.mock import MockProvider

PROVIDERS = {"Mock": MockProvider}


def get_provider(settings=None):
	settings = settings or frappe.get_cached_doc("Payment Settings")
	cls = PROVIDERS.get(settings.provider or "Mock")
	if not cls:
		frappe.throw(_("Payment provider {0} is not installed").format(settings.provider))
	if (settings.mode or "Sandbox") == "Live" and cls is MockProvider:
		frappe.throw(_("Live mode needs a real payment provider. Choose one in Payment Settings."))
	return cls(settings)
