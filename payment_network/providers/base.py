"""Contract every payment provider adapter implements.

Adding a real provider (Fawry, Paymob, ...): subclass PaymentProvider, implement the four methods,
register it in providers/registry.py and pick it in Payment Settings. Nothing else changes.
Secrets come from Payment Settings (Password fields) or site_config.json, never from code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ProviderResult:
	status: str  # "Success" | "Failed" | "Pending"
	provider_ref: str = ""
	message: str = ""
	raw: dict = field(default_factory=dict)


class PaymentProvider(ABC):
	name = "base"

	def __init__(self, settings):
		self.settings = settings

	def secret(self, fieldname):
		"""A secret from Payment Settings, falling back to site_config.json (key: payment_network_<fieldname>)."""
		import frappe

		value = self.settings.get_password(fieldname, raise_exception=False)
		return value or frappe.conf.get(f"payment_network_{fieldname}")

	@abstractmethod
	def charge(self, reference, amount, service_code, customer_reference, meta=None) -> ProviderResult:
		"""Start the operation. `reference` is our transaction id: send it so retries never double charge."""

	@abstractmethod
	def status(self, reference, provider_ref=None) -> ProviderResult:
		"""Ask the provider what happened to an operation (used for pending ones)."""

	@abstractmethod
	def refund(self, reference, provider_ref, amount) -> ProviderResult:
		"""Reverse a successful operation."""

	@abstractmethod
	def verify_webhook(self, raw_body: bytes, headers: dict):
		"""Return {"reference", "status", "provider_ref", "message"} for a genuine callback, or None."""
