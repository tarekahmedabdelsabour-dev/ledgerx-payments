"""Payment operations: execute, finalize, reverse, approve, review pending, webhook.

Flow of one service transaction (the database transaction is committed between the steps that matter,
so a crash can never leave money taken without a record):
  1. validate: user, device, PIN, service, limits, idempotency          (rolls back on any error)
  2. hold: debit the agent's available balance, status Processing        (committed)
  3. provider call (no locks held)
  4. Success -> cash held credited, commissions distributed, Journal Entry, status Success
     Failed  -> the hold is credited back, status Failed
     Pending -> stays Processing; the scheduled job and the webhook finish it
"""
import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, nowdate, now_datetime

from payment_network import permissions
from payment_network.engine import accounting, audit, ledger, logic
from payment_network.providers.base import ProviderResult
from payment_network.providers.registry import get_provider

PT = "Payment Transaction"


def settings():
	return frappe.get_cached_doc("Payment Settings")


# ------------------------------------------------------------------ who is calling
def agent_profile(user=None):
	user = user or frappe.session.user
	p = frappe.db.get_value("Payment Agent Profile", {"user": user}, "*", as_dict=True)
	if not p:
		frappe.throw(_("Your user is not registered as a payment agent"), frappe.PermissionError)
	if p.role_type != "Agent":
		frappe.throw(_("Your profile is registered as {0}. The agent screen is for agents only: create a separate user and profile with role type Agent for field work, and use the desk to supervise.").format(_(p.role_type)), frappe.PermissionError)
	if p.status != "Active":
		frappe.throw(_("Your account is suspended. Contact your supervisor."), frappe.PermissionError)
	return p


def check_device(profile, device_id):
	if profile.device_id:
		if not device_id or device_id != profile.device_id:
			audit.log("Device mismatch", "Payment Agent Profile", profile.name, {"sent": device_id})
			frappe.db.commit()
			frappe.throw(_("This device is not registered for your account"), frappe.PermissionError)
	elif device_id:
		frappe.db.set_value("Payment Agent Profile", profile.name, "device_id", device_id, update_modified=False)
		audit.log("Device registered", "Payment Agent Profile", profile.name, {"device_id": device_id})


def check_pin(profile, pin):
	s = settings()
	now = now_datetime()
	if profile.locked_until and get_datetime(profile.locked_until) > now:
		frappe.throw(_("The PIN is locked until {0}").format(frappe.utils.format_datetime(profile.locked_until)))
	if not profile.pin_set:
		frappe.throw(_("Set your PIN first"))
	if logic.verify_pin(pin, profile.pin_hash):
		if profile.failed_pin_attempts:
			frappe.db.set_value("Payment Agent Profile", profile.name, "failed_pin_attempts", 0, update_modified=False)
		return
	attempts = cint(profile.failed_pin_attempts) + 1
	vals = {"failed_pin_attempts": attempts}
	if attempts >= (cint(s.max_pin_attempts) or 5):
		vals = {"failed_pin_attempts": 0, "locked_until": add_to_date(now, minutes=cint(s.lock_minutes) or 15)}
	frappe.db.set_value("Payment Agent Profile", profile.name, vals, update_modified=False)
	audit.log("Wrong PIN", "Payment Agent Profile", profile.name, {"attempts": attempts})
	frappe.db.commit()  # the counter must survive the error below
	frappe.throw(_("Wrong PIN"))


def set_pin(profile_name, new_pin, old_pin=None):
	if not logic.valid_pin(new_pin):
		frappe.throw(_("The PIN must be 4 to 6 digits"))
	p = frappe.db.get_value("Payment Agent Profile", profile_name, "*", as_dict=True)
	own = p.user == frappe.session.user
	if not own and not permissions.is_manager():
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if own and p.pin_set and not permissions.is_manager():
		check_pin(frappe._dict(p), old_pin)
	frappe.db.set_value("Payment Agent Profile", profile_name,
		{"pin_hash": logic.hash_pin(new_pin), "pin_set": 1, "failed_pin_attempts": 0, "locked_until": None}, update_modified=False)
	audit.log("PIN changed", "Payment Agent Profile", profile_name)


# ------------------------------------------------------------------ limits
def daily_total(profile):
	return flt(frappe.db.sql(
		f"SELECT COALESCE(SUM(amount),0) FROM `tab{PT}` WHERE agent=%s AND kind IN ('Service','Invoice Payment') "
		"AND status IN ('Processing','Success') AND DATE(started_at)=%s", (profile, nowdate()))[0][0])


def limit_context(profile, amount, collect, needs_float=True):
	s = settings()
	w = frappe.db.get_value("Agent Wallet", {"profile": profile.name}, ["balance", "custody_balance"], as_dict=True) or {}
	return {
		"status": profile.status, "amount": amount, "collect": collect, "needs_float": needs_float,
		"txn_limit": profile.txn_limit, "global_txn_limit": s.global_txn_limit, "daily_limit": profile.daily_limit,
		"global_daily_limit": s.global_daily_limit, "daily_total": daily_total(profile.name),
		"float_balance": flt(w.get("balance")), "custody": flt(w.get("custody_balance")),
		"custody_limit": profile.cash_custody_limit,
	}


def limit_message(err):
	code, p = err
	return {
		"SUSPENDED": _("Your account is suspended. Contact your supervisor."),
		"TXN_LIMIT": _("The amount is above your transaction limit ({0})").format(p.get("limit")),
		"DAILY_LIMIT": _("This would pass your daily limit ({0}). Used today: {1}").format(p.get("limit"), p.get("used")),
		"INSUFFICIENT": _("Your balance ({0}) is not enough").format(p.get("balance")),
		"CUSTODY_LIMIT": _("You hold {0} in cash, the limit is {1}. Hand over cash to your supervisor first.").format(p.get("held"), p.get("limit")),
	}[code]


# ------------------------------------------------------------------ create
def _existing(key):
	return frappe.db.get_value(PT, {"idempotency_key": key}, "name")


def result(name):
	t = frappe.db.get_value(PT, name, ["name", "kind", "status", "amount", "fee", "total_collected", "provider_ref",
		"failure_reason", "approval_request", "customer_reference", "service", "agent"], as_dict=True)
	return t


def _insert(values):
	doc = frappe.get_doc({"doctype": PT, **values})
	doc.flags.pn_engine = True
	doc.insert(ignore_permissions=True)
	return doc


def _base_values(profile, kind, key, amount, device_id):
	ip, _dev = audit.request_info()
	wallet = ledger.wallet_of(profile.name)
	return {
		"kind": kind, "status": "Pending", "agent": profile.name, "supervisor": profile.supervisor, "wallet": wallet,
		"company": settings().company, "sandbox": 1 if (settings().mode or "Sandbox") == "Sandbox" else 0, "amount": amount,
		"idempotency_key": key, "provider": settings().provider, "device_id": device_id, "ip_address": ip,
	}


def _guard(profile, pin, key, device_id):
	if not key:
		frappe.throw(_("An idempotency key is required"))
	if (name := _existing(key)):
		if frappe.db.get_value(PT, name, "agent") != profile.name:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return name
	get_provider()  # fails early on a bad provider/mode
	check_device(profile, device_id)
	check_pin(profile, pin)
	return None


def execute(service, amount, customer_reference=None, pin=None, idempotency_key=None, customer=None, device_id=None):
	"""An agent sells a service to a walk-in customer who pays cash."""
	profile = agent_profile()
	if (name := _guard(profile, pin, idempotency_key, device_id)):
		return result(name)
	accounting.require("service")
	svc = frappe.get_doc("Payment Service", service)
	amount = logic.r2(amount)
	if not svc.enabled:
		frappe.throw(_("The service {0} is not available").format(svc.name))
	if amount <= 0 or amount < flt(svc.min_amount) or (flt(svc.max_amount) and amount > flt(svc.max_amount)):
		frappe.throw(_("The amount must be between {0} and {1}").format(flt(svc.min_amount), flt(svc.max_amount) or _("no maximum")))
	if cint(svc.requires_reference) and not (customer_reference or "").strip():
		frappe.throw(_("{0} is required").format(_(svc.reference_label or "Customer Reference")))
	fee = logic.calc_fee(amount, svc.fee_fixed, svc.fee_percent)
	total = logic.r2(amount + fee)
	ledger.lock([ledger.wallet_of(profile.name)])
	if (err := logic.check_limits(limit_context(profile, amount, total))):
		audit.log("Operation refused", PT, None, {"code": err[0], "amount": amount, "service": service})
		frappe.db.commit()
		frappe.throw(limit_message(err))
	values = _base_values(profile, "Service", idempotency_key, amount, device_id)
	values.update({"service": service, "customer": customer, "customer_reference": customer_reference, "fee": fee, "total_collected": total})
	try:
		txn = _insert(values)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		frappe.db.rollback()
		return result(_existing(idempotency_key))
	audit.log("Transaction created", PT, txn.name, {"amount": amount, "service": service})
	return _route(txn, "Large Transaction")


def pay_invoice(amount, pin=None, idempotency_key=None, sales_invoice=None, pos_invoice=None, device_id=None):
	"""An agent collects a customer's invoice payment through the provider."""
	profile = agent_profile()
	if (name := _guard(profile, pin, idempotency_key, device_id)):
		return result(name)
	accounting.require("invoice")
	if bool(sales_invoice) == bool(pos_invoice):
		frappe.throw(_("Choose either a Sales Invoice or a POS Invoice"))
	dt, inv = ("Sales Invoice", sales_invoice) if sales_invoice else ("POS Invoice", pos_invoice)
	d = frappe.db.get_value(dt, inv, ["docstatus", "customer", "outstanding_amount", "company"], as_dict=True, for_update=True) \
		if frappe.db.exists(dt, inv) else None
	if not d or d.docstatus != 1:
		frappe.throw(_("The invoice must exist and be submitted"))
	amount = logic.r2(amount)
	# money already on its way (Pending/Processing) counts against the outstanding, for Sales and POS invoices alike
	in_flight = flt(frappe.db.sql(
		f"SELECT COALESCE(SUM(amount),0) FROM `tab{PT}` WHERE kind='Invoice Payment' AND status IN ('Pending','Processing') "
		"AND (sales_invoice=%s OR pos_invoice=%s)", (inv, inv))[0][0])
	room = flt(d.outstanding_amount) - in_flight
	if amount <= 0 or amount > room + 0.005:
		frappe.throw(_("The amount must not be more than the invoice outstanding ({0})").format(max(room, 0)))
	ledger.lock([ledger.wallet_of(profile.name)])
	if (err := logic.check_limits(limit_context(profile, amount, 0, needs_float=False))):
		frappe.throw(limit_message(err))
	values = _base_values(profile, "Invoice Payment", idempotency_key, amount, device_id)
	values.update({"customer": d.customer, "customer_reference": inv, "total_collected": amount,
		"sales_invoice": sales_invoice, "pos_invoice": pos_invoice})
	try:
		txn = _insert(values)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		frappe.db.rollback()
		return result(_existing(idempotency_key))
	audit.log("Transaction created", PT, txn.name, {"amount": amount, "invoice": inv})
	return _route(txn, "Large Transaction")


def pay_supplier(purchase_invoice, amount, idempotency_key, supplier_reference=None):
	"""Manager pays a supplier through the provider (switched on in Payment Settings)."""
	if not permissions.is_manager():
		frappe.throw(_("Only a payment manager can pay suppliers"), frappe.PermissionError)
	s = settings()
	if not cint(s.enable_supplier_payments):
		frappe.throw(_("Paying suppliers electronically is switched off in Payment Settings"))
	if (name := _existing(idempotency_key)):
		return result(name)
	profile = frappe.db.get_value("Payment Agent Profile", {"user": frappe.session.user, "status": "Active"}, "*", as_dict=True)
	if not profile:
		frappe.throw(_("Your user has no active payment profile"))
	accounting.require("supplier")
	d = frappe.db.get_value("Purchase Invoice", purchase_invoice, ["docstatus", "supplier", "outstanding_amount"], as_dict=True)
	amount = logic.r2(amount)
	if not d or d.docstatus != 1 or amount <= 0 or amount > flt(d.outstanding_amount) + 0.005:
		frappe.throw(_("The invoice must be submitted and the amount not more than its outstanding"))
	if flt(s.global_txn_limit) and amount > flt(s.global_txn_limit):
		frappe.throw(_("The amount is above the transaction limit ({0})").format(s.global_txn_limit))
	values = _base_values(profile, "Supplier Payment", idempotency_key, amount, None)
	values.update({"supplier": d.supplier, "purchase_invoice": purchase_invoice, "customer_reference": supplier_reference or purchase_invoice,
		"total_collected": amount})
	try:
		txn = _insert(values)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		frappe.db.rollback()
		return result(_existing(idempotency_key))
	audit.log("Supplier payment created", PT, txn.name, {"amount": amount, "invoice": purchase_invoice})
	return _route(txn, "Large Transaction")


def _route(txn, request_type):
	"""Large amounts wait for approval; everything else goes straight to the provider."""
	thr = flt(settings().approval_threshold)
	if thr and txn.kind != "Supplier Payment" and txn.amount >= thr:
		req = frappe.get_doc({
			"doctype": "Payment Approval Request", "request_type": request_type, "transaction": txn.name, "agent": txn.agent,
			"amount": txn.amount, "requested_by": frappe.session.user, "status": "Pending",
			"reason": _("Amount at or above {0}").format(thr),
		})
		req.flags.pn_engine = True
		req.insert(ignore_permissions=True)
		frappe.db.set_value(PT, txn.name, "approval_request", req.name)
		audit.log("Approval requested", "Payment Approval Request", req.name, {"transaction": txn.name})
		frappe.db.commit()
		return result(txn.name)
	return start(txn.name)


# ------------------------------------------------------------------ provider round trip
def start(name):
	"""Hold the money, commit, call the provider, apply its answer."""
	# lock the row first: two callers (approval click + retry) must not both start the same transaction
	if frappe.db.get_value(PT, name, "status", for_update=True) != "Pending":
		return result(name)
	txn = frappe.get_doc(PT, name)
	if txn.kind == "Service":
		ledger.lock([txn.wallet])
		profile = frappe.db.get_value("Payment Agent Profile", txn.agent, "*", as_dict=True)
		if (err := logic.check_limits(limit_context(profile, txn.amount, txn.total_collected))):
			finalize_failure(name, limit_message(err))
			frappe.db.commit()
			return result(name)
		try:
			ledger.post(txn.wallet, "Available", "Debit", txn.amount, PT, name, group=name, remarks=_("Held for {0}").format(name))
		except ledger.InsufficientBalance:
			finalize_failure(name, _("Insufficient balance"))
			frappe.db.commit()
			return result(name)
	frappe.db.set_value(PT, name, {"status": "Processing", "started_at": now_datetime()})
	frappe.db.commit()
	try:
		provider = get_provider()
		code = frappe.db.get_value("Payment Service", txn.service, "provider_code") if txn.service else txn.kind
		res = provider.charge(name, txn.amount, code or txn.service, txn.customer_reference,
			{"kind": txn.kind, "fee": txn.fee})
	except Exception:
		frappe.log_error(title=f"Payment provider error for {name}")
		frappe.db.set_value(PT, name, "provider_status", "Unknown: waiting for review")
		frappe.db.commit()
		return result(name)
	apply_result(name, res)
	frappe.db.commit()
	return result(name)


def apply_result(name, res):
	status = frappe.db.get_value(PT, name, "status", for_update=True)
	if status != "Processing":
		return status
	if res.provider_ref:
		frappe.db.set_value(PT, name, "provider_ref", res.provider_ref)
	frappe.db.set_value(PT, name, "provider_status", res.status)
	if res.status == "Success":
		finalize_success(name)
	elif res.status == "Failed":
		finalize_failure(name, res.message or _("Declined by the provider"))
	return frappe.db.get_value(PT, name, "status")


def finalize_success(name):
	txn = frappe.get_doc(PT, name)
	if not logic.can_transition(txn.status, "Success"):
		return
	vals = {"status": "Success", "completed_at": now_datetime(), "failure_reason": None}
	if txn.kind == "Service":
		a = accounting.accounts_map("service")
		svc = frappe.get_doc("Payment Service", txn.service)
		agent_c = sup_c = company_c = 0.0
		if svc.commission_rule and frappe.db.get_value("Commission Rule", svc.commission_rule, "enabled"):
			rule = frappe.get_doc("Commission Rule", svc.commission_rule)
			pool = logic.calc_commission(rule.basis, txn.amount, rule.percent, [t.as_dict() for t in rule.tiers])
			sup_active = bool(txn.supervisor) and frappe.db.get_value("Payment Agent Profile", txn.supervisor, "status") == "Active"
			sh = logic.split_pool(pool, rule.agent_share, rule.supervisor_share, rule.company_share, sup_active)
			agent_c, sup_c, company_c = sh["agent"], sh["supervisor"], sh["company"]
		sup_wallet = ledger.wallet_of(txn.supervisor) if sup_c else None
		ledger.lock([txn.wallet, sup_wallet])
		ledger.post(txn.wallet, "Cash Held", "Credit", txn.total_collected, PT, name, group=name, remarks=_("Cash collected"))
		if agent_c:
			ledger.post(txn.wallet, "Commission", "Credit", agent_c, PT, name, group=name)
		if sup_c:
			ledger.post(sup_wallet, "Commission", "Credit", sup_c, PT, name, group=name)
		je = accounting.make_je(accounting.service_lines(txn.amount, txn.fee, agent_c, sup_c, a),
			_("Payment {0}: {1}").format(name, txn.service), f"{PT} {name}", name)
		vals.update({"agent_commission": agent_c, "supervisor_commission": sup_c, "company_commission": company_c, "journal_entry": je})
	elif txn.kind == "Invoice Payment":
		if txn.sales_invoice:
			vals["payment_entry"] = accounting.payment_entry(txn, "Customer", "Sales Invoice", txn.sales_invoice, txn.amount)
			frappe.db.set_value("Sales Invoice", txn.sales_invoice, "pn_transaction", name, update_modified=False)
		else:
			si = frappe.db.get_value("POS Invoice", txn.pos_invoice, "consolidated_invoice")
			if si:
				vals["payment_entry"] = accounting.payment_entry(txn, "Customer", "Sales Invoice", si, txn.amount)
			else:  # not consolidated yet: an unallocated receipt the accountant allocates later
				vals["payment_entry"] = accounting.advance_payment_entry(txn, txn.customer, txn.amount,
					_("Electronic payment of POS Invoice {0}").format(txn.pos_invoice))
			frappe.db.set_value("POS Invoice", txn.pos_invoice, "pn_transaction", name, update_modified=False)
	elif txn.kind == "Supplier Payment":
		vals["payment_entry"] = accounting.payment_entry(txn, "Supplier", "Purchase Invoice", txn.purchase_invoice, txn.amount)
		frappe.db.set_value("Purchase Invoice", txn.purchase_invoice, "pn_transaction", name, update_modified=False)
	frappe.db.set_value(PT, name, vals)
	audit.log("Transaction succeeded", PT, name, {"amount": txn.amount})


def finalize_failure(name, reason):
	status = frappe.db.get_value(PT, name, "status", for_update=True)
	if not logic.can_transition(status, "Failed"):
		return
	txn = frappe.get_doc(PT, name)
	if txn.kind == "Service" and frappe.db.exists("Wallet Ledger Entry", {"reference_doctype": PT, "reference_name": name,
			"bucket": "Available", "direction": "Debit"}):
		ledger.lock([txn.wallet])
		ledger.post(txn.wallet, "Available", "Credit", txn.amount, PT, name, group=name, remarks=_("Released: {0}").format(name))
	frappe.db.set_value(PT, name, {"status": "Failed", "failure_reason": reason, "completed_at": now_datetime()})
	audit.log("Transaction failed", PT, name, {"reason": reason})


# ------------------------------------------------------------------ reversal
def reverse(name):
	status = frappe.db.get_value(PT, name, "status", for_update=True)
	if status != "Success":
		frappe.throw(_("Only a successful transaction can be reversed"))
	txn = frappe.get_doc(PT, name)
	res = get_provider().refund(name, txn.provider_ref, txn.amount)
	if res.status != "Success":
		frappe.throw(_("The provider did not confirm the refund: {0}").format(res.message))
	vals = {"status": "Reversed", "reversed_at": now_datetime()}
	if txn.kind == "Service":
		a = accounting.accounts_map("service")
		sup_wallet = ledger.wallet_of(txn.supervisor) if flt(txn.supervisor_commission) else None
		ledger.lock([txn.wallet, sup_wallet])
		ledger.post(txn.wallet, "Available", "Credit", txn.amount, PT, name, group=name + "-R", remarks=_("Reversal of {0}").format(name))
		ledger.post(txn.wallet, "Cash Held", "Debit", txn.total_collected, PT, name, group=name + "-R", allow_negative=True)
		if flt(txn.agent_commission):
			ledger.post(txn.wallet, "Commission", "Debit", txn.agent_commission, PT, name, group=name + "-R", allow_negative=True)
		if flt(txn.supervisor_commission):
			ledger.post(sup_wallet, "Commission", "Debit", txn.supervisor_commission, PT, name, group=name + "-R", allow_negative=True)
		lines = accounting.invert(accounting.service_lines(txn.amount, txn.fee, flt(txn.agent_commission), flt(txn.supervisor_commission), a))
		vals["reversal_journal_entry"] = accounting.make_je(lines, _("Reversal of payment {0}").format(name), f"{PT} {name}", name)
	else:
		accounting.cancel_doc("Payment Entry", txn.payment_entry)
	frappe.db.set_value(PT, name, vals)
	audit.log("Transaction reversed", PT, name)


def request_reversal(name, reason):
	t = frappe.db.get_value(PT, name, ["agent", "status", "amount", "kind"], as_dict=True)
	profile = agent_profile()
	if not t or t.agent != profile.name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if t.status != "Success":
		frappe.throw(_("Only a successful transaction can be reversed"))
	if not (reason or "").strip():
		frappe.throw(_("Give the reason for the reversal"))
	if frappe.db.exists("Payment Approval Request", {"transaction": name, "request_type": "Reversal", "status": "Pending"}):
		frappe.throw(_("A reversal request is already waiting"))
	req = frappe.get_doc({"doctype": "Payment Approval Request", "request_type": "Reversal", "transaction": name,
		"agent": t.agent, "amount": t.amount, "requested_by": frappe.session.user, "status": "Pending", "reason": reason})
	req.flags.pn_engine = True
	req.insert(ignore_permissions=True)
	audit.log("Reversal requested", "Payment Approval Request", req.name, {"transaction": name})
	return req.name


def decide(request, approve, note=None):
	if frappe.db.get_value("Payment Approval Request", request, "status", for_update=True) != "Pending":
		frappe.throw(_("This request was already decided"))
	req = frappe.get_doc("Payment Approval Request", request)
	permissions.require_can_decide(req.agent, req.requested_by)
	frappe.db.set_value("Payment Approval Request", request, {
		"status": "Approved" if approve else "Rejected", "decided_by": frappe.session.user,
		"decided_on": now_datetime(), "decision_note": note})
	audit.log("Request approved" if approve else "Request rejected", "Payment Approval Request", request, {"note": note})
	if req.request_type == "Large Transaction":
		if approve:
			start(req.transaction)
		else:
			finalize_failure(req.transaction, _("Rejected: {0}").format(note or ""))
	elif approve:
		reverse(req.transaction)


# ------------------------------------------------------------------ pending review and webhook
def review_pending():
	s = settings()
	cutoff = add_to_date(now_datetime(), minutes=-(cint(s.pending_review_minutes) or 5))
	names = frappe.get_all(PT, filters={"status": "Processing", "started_at": ["<", cutoff]}, pluck="name", limit=200)
	if not names:
		return 0
	provider = get_provider(s)
	done = 0
	for n in names:
		try:
			res = provider.status(n, frappe.db.get_value(PT, n, "provider_ref"))
			apply_result(n, res)
			frappe.db.commit()
			done += 1
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Payment review failed for {n}")
	return done


def handle_webhook(raw_body, headers):
	data = get_provider().verify_webhook(raw_body, headers)
	if not data or not frappe.db.exists(PT, data["reference"]):
		return False
	apply_result(data["reference"], ProviderResult(data["status"], data.get("provider_ref", ""), data.get("message", "")))
	audit.log("Webhook applied", PT, data["reference"], {"status": data["status"]}, user="Guest")
	frappe.db.commit()
	return True
