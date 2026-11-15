"""Sandbox provider that works without any network.

Behaviour is decided by the cents of the amount, so every path can be tried by hand:
  .13 -> fails      .77 -> stays pending, succeeds on the first status check      .99 -> pending forever, then fails
anything else succeeds immediately. Its state lives in the site cache.
"""
import json

import frappe

from payment_network.engine import logic
from payment_network.providers.base import PaymentProvider, ProviderResult


def _cents(amount):
	return int(round(float(amount) * 100)) % 100


class MockProvider(PaymentProvider):
	name = "Mock"

	def _key(self, reference):
		return f"pn_mock::{reference}"

	def _store(self, reference, data):
		frappe.cache.set_value(self._key(reference), json.dumps(data), expires_in_sec=7 * 86400)

	def _load(self, reference):
		raw = frappe.cache.get_value(self._key(reference))
		return json.loads(raw) if raw else None

	def charge(self, reference, amount, service_code, customer_reference, meta=None):
		existing = self._load(reference)
		if existing:  # same reference twice must never charge twice
			return ProviderResult(existing["status"], existing["ref"], existing.get("message", ""))
		c = _cents(amount)
		ref = "MOCK-" + frappe.generate_hash(length=10).upper()
		if c == 13:
			data = {"status": "Failed", "ref": ref, "message": "Declined by the sandbox provider", "amount": amount}
		elif c in (77, 99):
			data = {"status": "Pending", "ref": ref, "message": "Waiting for the provider", "amount": amount, "mode": c}
		else:
			data = {"status": "Success", "ref": ref, "message": "OK", "amount": amount}
		self._store(reference, data)
		return ProviderResult(data["status"], data["ref"], data["message"])

	def status(self, reference, provider_ref=None):
		data = self._load(reference)
		if not data:
			return ProviderResult("Failed", provider_ref or "", "Unknown reference")
		if data["status"] == "Pending":
			data["status"] = "Success" if data.get("mode") == 77 else "Failed"
			data["message"] = "OK" if data["status"] == "Success" else "Timed out at the provider"
			self._store(reference, data)
		return ProviderResult(data["status"], data["ref"], data.get("message", ""))

	def refund(self, reference, provider_ref, amount):
		data = self._load(reference) or {}
		if data.get("status") != "Success":
			return ProviderResult("Failed", provider_ref or "", "Only a successful operation can be refunded")
		data["refunded"] = True
		self._store(reference, data)
		return ProviderResult("Success", provider_ref or data.get("ref", ""), "Refunded")

	def verify_webhook(self, raw_body, headers):
		secret = self.secret("webhook_secret")
		sig = (headers or {}).get("X-Signature") or (headers or {}).get("x-signature")
		if not logic.verify_signature(secret, raw_body, sig):
			return None
		try:
			p = json.loads(raw_body.decode("utf-8"))
		except Exception:
			return None
		if p.get("status") not in ("Success", "Failed") or not p.get("reference"):
			return None
		return {"reference": p["reference"], "status": p["status"], "provider_ref": p.get("provider_ref", ""), "message": p.get("message", "")}
