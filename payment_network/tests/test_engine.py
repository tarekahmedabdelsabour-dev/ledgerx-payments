"""Integration tests: run on a Sandbox site with  bench --site <site> run-tests --app payment_network
They call seed.run() once (demo users, float, services) and then exercise the engine for real: ledger, limits,
reversal, commissions, permission isolation, idempotency, PIN lock, webhook signature and two concurrent
operations on one wallet.  NOT executed by the author (no bench available) - run them before using the module.
"""
import json
import threading
import uuid

import frappe

try:
	from frappe.tests import IntegrationTestCase as Base
except ImportError:  # older Frappe
	from frappe.tests.utils import FrappeTestCase as Base

from payment_network import permissions, seed
from payment_network.engine import ledger, logic, service

MGR = "pn.manager@example.com"
SUP1, SUP2 = "pn.supervisor1@example.com", "pn.supervisor2@example.com"
A1, A2, A3 = "pn.agent1@example.com", "pn.agent2@example.com", "pn.agent3@example.com"
PIN = "1234"


def as_user(email):
	frappe.set_user(email)
	frappe.local.__dict__.pop("pn_profiles", None)


def wallet(email):
	p = frappe.db.get_value("Payment Agent Profile", {"user": email}, "name")
	return frappe.db.get_value("Agent Wallet", {"profile": p}, ["name", "balance", "commission_balance", "custody_balance"], as_dict=True)


def pay(email, amount, service_name="Mobile Top-up", key=None, ref="01000000000"):
	as_user(email)
	return service.execute(service_name, amount, ref, PIN, key or uuid.uuid4().hex)


class TestPaymentNetwork(Base):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed.run()
		frappe.db.set_value("Payment Settings", None, {"approval_threshold": 2500, "pending_review_minutes": 5})
		frappe.clear_cache(doctype="Payment Settings")

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------ ledger
	def test_ledger_is_consistent_and_append_only(self):
		w = wallet(A1)
		self.assertEqual(ledger.verify(w.name), {})
		entry = frappe.get_all("Wallet Ledger Entry", filters={"wallet": w.name}, limit=1, pluck="name")[0]
		doc = frappe.get_doc("Wallet Ledger Entry", entry)
		doc.remarks = "tamper"
		self.assertRaises(frappe.ValidationError, doc.save)
		self.assertRaises(frappe.ValidationError, frappe.delete_doc, "Wallet Ledger Entry", entry)
		self.assertRaises(frappe.ValidationError, ledger.post, w.name, "Available", "Debit", 10**9)  # never below zero

	# ------------------------------------------------------------ success path, commissions, accounting
	def test_success_moves_money_and_books_balanced_entries(self):
		before = wallet(A1)
		r = pay(A1, 100)
		self.assertEqual(r.status, "Success")
		after = wallet(A1)
		self.assertEqual(logic.r2(before.balance - after.balance), 100)          # float spent
		self.assertEqual(logic.r2(after.custody_balance - before.custody_balance), 101)  # amount + 1% fee in cash
		t = frappe.get_doc("Payment Transaction", r.name)
		self.assertAlmostEqual(t.agent_commission + t.supervisor_commission + t.company_commission, logic.calc_commission("Percent", 100, 1), 2)
		self.assertTrue(t.journal_entry)
		je = frappe.get_doc("Journal Entry", t.journal_entry)
		self.assertAlmostEqual(je.total_debit, je.total_credit, 2)
		self.assertEqual(ledger.verify(after.name), {})

	def test_failed_operation_releases_the_hold(self):
		before = wallet(A1)
		r = pay(A1, 50.13)  # the sandbox provider declines .13
		self.assertEqual(r.status, "Failed")
		self.assertEqual(wallet(A1).balance, before.balance)

	def test_pending_is_finished_by_the_review_job(self):
		before = wallet(A1)
		r = pay(A1, 60.77)  # .77 stays pending, then succeeds
		self.assertEqual(r.status, "Processing")
		self.assertEqual(logic.r2(before.balance - wallet(A1).balance), 60.77)  # held meanwhile
		frappe.db.set_value("Payment Transaction", r.name, "started_at", frappe.utils.add_to_date(None, minutes=-30))
		service.review_pending()
		self.assertEqual(frappe.db.get_value("Payment Transaction", r.name, "status"), "Success")

	# ------------------------------------------------------------ limits
	def test_limits(self):
		as_user(A1)
		with self.assertRaises(frappe.ValidationError):
			service.execute("Mobile Top-up", 3001, "010", PIN, uuid.uuid4().hex)  # above the per-transaction limit
		with self.assertRaises(frappe.ValidationError):
			service.execute("Mobile Top-up", 1, "010", "9999", uuid.uuid4().hex)  # wrong PIN
		frappe.set_user("Administrator")
		p = frappe.db.get_value("Payment Agent Profile", {"user": A2}, "name")
		frappe.db.set_value("Payment Agent Profile", p, "cash_custody_limit", wallet(A2).custody_balance + 50)
		with self.assertRaises(frappe.ValidationError):
			pay(A2, 100)  # cash held would pass the custody limit
		frappe.db.set_value("Payment Agent Profile", p, "cash_custody_limit", 10**6)

	# ------------------------------------------------------------ idempotency
	def test_same_key_never_charges_twice(self):
		key = uuid.uuid4().hex
		before = wallet(A1)
		a, b = pay(A1, 20, key=key), pay(A1, 20, key=key)
		self.assertEqual(a.name, b.name)
		self.assertEqual(logic.r2(before.balance - wallet(A1).balance), 20)

	# ------------------------------------------------------------ reversal and approvals
	def test_reversal_needs_the_supervisor_and_restores_everything(self):
		before = wallet(A1)
		r = pay(A1, 200)
		req = service.request_reversal(r.name, "customer cancelled")
		as_user(A1)
		self.assertRaises(frappe.PermissionError, service.decide, req, True)          # an agent cannot approve
		as_user(SUP2)
		self.assertRaises(frappe.PermissionError, service.decide, req, True)          # nor another supervisor
		as_user(SUP1)
		service.decide(req, True, "ok")
		t = frappe.get_doc("Payment Transaction", r.name)
		self.assertEqual(t.status, "Reversed")
		self.assertTrue(t.reversal_journal_entry)
		after = wallet(A1)
		self.assertEqual((after.balance, after.custody_balance, after.commission_balance),
			(before.balance, before.custody_balance, before.commission_balance))
		self.assertEqual(ledger.verify(after.name), {})

	def test_large_amount_waits_for_approval(self):
		r = pay(A1, 2600, service_name="Gift Voucher")
		self.assertEqual(r.status, "Pending")
		self.assertTrue(r.approval_request)
		as_user(SUP1)
		service.decide(r.approval_request, True)
		self.assertEqual(frappe.db.get_value("Payment Transaction", r.name, "status"), "Success")

	# ------------------------------------------------------------ permission isolation
	def test_isolation(self):
		pay(A1, 10)
		pay(A3, 10)
		names = lambda: set(frappe.get_list("Payment Transaction", fields=["agent"], pluck="agent", limit_page_length=0))
		as_user(A1)
		own = frappe.db.get_value("Payment Agent Profile", {"user": A1}, "name")
		self.assertEqual(names(), {own})
		as_user(SUP1)
		mine = set(frappe.get_all("Payment Agent Profile", filters={"supervisor": permissions.profile_of(SUP1).name}, pluck="name"))
		self.assertTrue(names() <= mine)
		self.assertEqual(frappe.get_list("Agent Wallet", filters={"profile": frappe.db.get_value("Payment Agent Profile", {"user": A3}, "name")}), [])
		as_user(MGR)
		self.assertGreaterEqual(len(names()), 2)
		as_user(A1)
		other = frappe.get_doc("Payment Transaction", frappe.get_all("Payment Transaction", filters={"agent": frappe.db.get_value("Payment Agent Profile", {"user": A3}, "name")}, pluck="name", ignore_permissions=True)[0])
		self.assertFalse(frappe.has_permission("Payment Transaction", "read", doc=other, user=A1))

	# ------------------------------------------------------------ settlement
	def test_cash_settlement_moves_custody_up_the_chain(self):
		pay(A2, 100)
		a_before, s_before = wallet(A2), wallet(SUP1)
		as_user(A2)
		prof = permissions.profile_of(A2)
		doc = frappe.get_doc({"doctype": "Cash Settlement", "stage": "Agent to Supervisor", "from_profile": prof.name,
			"to_profile": frappe.db.get_value("Payment Agent Profile", prof.name, "supervisor"),
			"amount_due": a_before.custody_balance, "commission_offset": 0, "amount_handed": a_before.custody_balance})
		doc.insert()
		self.assertRaises(frappe.PermissionError, doc.submit)  # the sender cannot confirm his own handover
		as_user(SUP1)
		doc.reload()
		doc.submit()
		self.assertEqual(wallet(A2).custody_balance, 0)
		self.assertEqual(logic.r2(wallet(SUP1).custody_balance - s_before.custody_balance), a_before.custody_balance)

	# ------------------------------------------------------------ PIN lock
	def test_wrong_pin_locks_the_agent(self):
		frappe.set_user("Administrator")
		prof = frappe.db.get_value("Payment Agent Profile", {"user": A3}, "name")
		for _ in range(5):
			as_user(A3)
			with self.assertRaises(frappe.ValidationError):
				service.execute("Mobile Top-up", 1, "010", "0000", uuid.uuid4().hex)
		self.assertTrue(frappe.db.get_value("Payment Agent Profile", prof, "locked_until"))
		with self.assertRaises(frappe.ValidationError):
			pay(A3, 1)  # even the right PIN is refused while locked
		frappe.db.set_value("Payment Agent Profile", prof, {"locked_until": None, "failed_pin_attempts": 0})

	# ------------------------------------------------------------ webhook
	def test_webhook_signature(self):
		frappe.set_user("Administrator")
		r = pay(A1, 70.77)
		self.assertEqual(r.status, "Processing")
		secret = "test-secret"
		frappe.db.set_value("Payment Settings", None, "webhook_secret", secret)  # Password field: stored plain here, test only
		from frappe.utils.password import set_encrypted_password
		set_encrypted_password("Payment Settings", "Payment Settings", secret, "webhook_secret")
		frappe.clear_cache(doctype="Payment Settings")
		body = json.dumps({"reference": r.name, "status": "Success", "provider_ref": "X1"}).encode()
		self.assertFalse(service.handle_webhook(body, {"X-Signature": "bad"}))
		self.assertEqual(frappe.db.get_value("Payment Transaction", r.name, "status"), "Processing")
		self.assertTrue(service.handle_webhook(body, {"X-Signature": logic.sign(secret, body)}))
		self.assertEqual(frappe.db.get_value("Payment Transaction", r.name, "status"), "Success")
		self.assertTrue(service.handle_webhook(body, {"X-Signature": logic.sign(secret, body)}))  # replay changes nothing
		self.assertEqual(frappe.db.get_value("Payment Transaction", r.name, "status"), "Success")

	# ------------------------------------------------------------ concurrency
	def test_two_concurrent_operations_cannot_spend_the_same_money(self):
		"""Balance 1000, two simultaneous 800 operations: exactly one may pass."""
		frappe.set_user("Administrator")
		w = wallet(A2)
		ledger.lock([w.name])
		spare = logic.r2(w.balance - 1000)
		if spare > 0:
			ledger.post(w.name, "Available", "Debit", spare, remarks="test setup")
		elif spare < 0:
			ledger.post(w.name, "Available", "Credit", -spare, remarks="test setup")
		frappe.db.commit()
		site, results = frappe.local.site, []

		def worker():
			frappe.init(site=site)
			frappe.connect()
			try:
				frappe.set_user(A2)
				results.append(service.execute("Mobile Top-up", 800, "010", PIN, uuid.uuid4().hex).status)
			except frappe.ValidationError:
				results.append("Refused")
			finally:
				frappe.db.commit()
				frappe.destroy()

		threads = [threading.Thread(target=worker) for _ in range(2)]
		[t.start() for t in threads]
		[t.join() for t in threads]
		frappe.init(site=site)
		frappe.connect()
		self.assertEqual(sorted(results), ["Refused", "Success"])
		self.assertGreaterEqual(wallet(A2).balance, 0)
