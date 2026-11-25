"""Pure rules of the payment network: no database, no Frappe, so they are unit-tested on their own.

Ledger sign convention (every balance type): Credit adds to the holder's balance, Debit subtracts.
"""
import hashlib
import hmac
import os
import re
from decimal import ROUND_HALF_UP, Decimal

BUCKET_FIELD = {"Available": "balance", "Commission": "commission_balance", "Cash Held": "custody_balance"}
STATUSES = ("Pending", "Processing", "Success", "Failed", "Reversed")
_TRANSITIONS = {
	"Pending": {"Processing", "Failed"},
	"Processing": {"Success", "Failed"},
	"Success": {"Reversed"},
	"Failed": set(),
	"Reversed": set(),
}


def r2(x):
	return float(Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def apply_entry(balance, direction, amount):
	if direction not in ("Debit", "Credit"):
		raise ValueError("direction")
	return r2(balance + amount if direction == "Credit" else balance - amount)


def can_transition(old, new):
	return new in _TRANSITIONS.get(old, set())


# ------------------------------------------------------------------ fees and commission
def calc_fee(amount, fixed=0, percent=0):
	return r2(float(fixed or 0) + float(amount or 0) * float(percent or 0) / 100.0)


def calc_commission(basis, amount, percent=0, tiers=()):
	amount = float(amount or 0)
	if basis == "Tiered":
		best = None
		for t in tiers:
			lo, hi = float(t.get("from_amount") or 0), float(t.get("to_amount") or 0)
			if amount >= lo and (not hi or amount <= hi) and (best is None or lo >= float(best.get("from_amount") or 0)):
				best = t
		if not best:
			return 0.0
		return r2(float(best.get("commission_amount") or 0) + amount * float(best.get("commission_percent") or 0) / 100.0)
	return r2(amount * float(percent or 0) / 100.0)


def shares_valid(agent, supervisor, company):
	return abs(float(agent or 0) + float(supervisor or 0) + float(company or 0) - 100.0) < 0.005


def split_pool(pool, agent_pct, supervisor_pct, company_pct, has_supervisor=True):
	"""Distribute a commission pool. A missing supervisor's share goes to the company; rounding remainder too."""
	pool = r2(pool)
	agent = r2(pool * float(agent_pct or 0) / 100.0)
	sup = r2(pool * float(supervisor_pct or 0) / 100.0) if has_supervisor else 0.0
	return {"agent": agent, "supervisor": sup, "company": r2(pool - agent - sup)}


# ------------------------------------------------------------------ limits
def check_limits(c):
	"""First rule an operation breaks, as (code, params), or None. `c` is a plain dict (see service._context)."""
	amount = float(c["amount"])
	collect = amount if c.get("collect") is None else float(c["collect"])
	if c.get("status") != "Active":
		return ("SUSPENDED", {})
	for key in ("txn_limit", "global_txn_limit"):
		lim = float(c.get(key) or 0)
		if lim and amount > lim:
			return ("TXN_LIMIT", {"limit": lim})
	for key in ("daily_limit", "global_daily_limit"):
		lim = float(c.get(key) or 0)
		if lim and float(c.get("daily_total") or 0) + amount > lim:
			return ("DAILY_LIMIT", {"limit": lim, "used": float(c.get("daily_total") or 0)})
	if c.get("needs_float", True) and float(c.get("float_balance") or 0) + 1e-9 < amount:
		return ("INSUFFICIENT", {"balance": float(c.get("float_balance") or 0)})
	lim = float(c.get("custody_limit") or 0)
	if lim and float(c.get("custody") or 0) + collect > lim:
		return ("CUSTODY_LIMIT", {"limit": lim, "held": float(c.get("custody") or 0)})
	return None


# ------------------------------------------------------------------ hierarchy
_ALWAYS = {("Manager", "Supervisor"), ("Manager", "Agent"), ("Supervisor", "Manager"), ("Agent", "Manager")}
_LINKED = {("Supervisor", "Agent"), ("Agent", "Supervisor")}


def transfer_allowed(from_role, to_role, linked):
	"""Balance moves along the chain manager > supervisor > agent (or back up). supervisor<->agent needs the reporting link."""
	pair = (from_role, to_role)
	return pair in _ALWAYS or (pair in _LINKED and bool(linked))


def settlement_stage_ok(stage, from_role, to_role, linked):
	if stage == "Agent to Supervisor":
		return from_role == "Agent" and to_role == "Supervisor" and bool(linked)
	if stage == "Supervisor to Manager":
		return from_role == "Supervisor" and to_role == "Manager"
	return False


def settlement_difference(due, offset, handed):
	"""Shortage is positive, excess negative."""
	return r2(float(due or 0) - float(offset or 0) - float(handed or 0))


# ------------------------------------------------------------------ PIN
PIN_RE = re.compile(r"^\d{4,6}$")
_ITER = 200_000


def valid_pin(pin):
	return bool(pin) and bool(PIN_RE.match(str(pin)))


def hash_pin(pin, salt=None, iterations=_ITER):
	salt = salt or os.urandom(16).hex()
	dk = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), iterations).hex()
	return f"pbkdf2_sha256${iterations}${salt}${dk}"


def verify_pin(pin, stored):
	try:
		algo, it, salt, dk = (stored or "").split("$")
		if algo != "pbkdf2_sha256":
			return False
		calc = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), int(it)).hex()
		return hmac.compare_digest(calc, dk)
	except Exception:
		return False


# ------------------------------------------------------------------ webhook signature
def sign(secret, body):
	body = body if isinstance(body, bytes) else str(body).encode()
	return hmac.new(str(secret).encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret, body, signature):
	if not secret or not signature:
		return False
	sig = str(signature).strip()
	if sig.lower().startswith("sha256="):
		sig = sig[7:]
	return hmac.compare_digest(sign(secret, body), sig.lower())
