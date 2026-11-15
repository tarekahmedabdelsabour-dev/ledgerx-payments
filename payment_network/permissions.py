"""Who sees which payment data, enforced in the backend (not by hiding things in the screen).

  Payment Manager / Auditor / System Manager : everything
  Payment Supervisor                         : his own records and his agents'
  Payment Agent                              : his own records only

Two hooks do it: permission_query_conditions filters every list/report query, has_permission denies a
single document. Both read the same `visible_profiles`. DocPerm rows still decide *which actions* a role has.
"""
import frappe
from frappe import _

MANAGER, SUPERVISOR, AGENT, AUDITOR = "Payment Manager", "Payment Supervisor", "Payment Agent", "Payment Auditor"
# doctype -> fields that hold a payment profile (a document is visible when ANY of them is visible)
SCOPED = {
	"Payment Agent Profile": ["name"],
	"Agent Wallet": ["profile"],
	"Wallet Ledger Entry": ["agent"],
	"Payment Transaction": ["agent"],
	"Cash Settlement": ["from_profile", "to_profile"],
	"Wallet Charge": ["from_profile", "to_profile"],
	"Payment Approval Request": ["agent"],
}
ADMIN_ONLY = ("Payment Audit Log",)


def _roles(user):
	return set(frappe.get_roles(user))


def sees_all(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(_roles(user) & {MANAGER, AUDITOR, "System Manager"})


def is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(_roles(user) & {MANAGER, "System Manager"})


def profile_of(user=None):
	user = user or frappe.session.user
	cache = frappe.local.__dict__.setdefault("pn_profiles", {})
	if user not in cache:
		cache[user] = frappe.db.get_value("Payment Agent Profile", {"user": user}, ["name", "role_type"], as_dict=True)
	return cache[user]


def visible_profiles(user=None):
	"""None = unrestricted, otherwise the list of profile names the user may see (possibly empty)."""
	user = user or frappe.session.user
	if sees_all(user):
		return None
	p = profile_of(user)
	if not p:
		return []
	names = [p.name]
	if p.role_type == "Supervisor":
		names += frappe.get_all("Payment Agent Profile", filters={"supervisor": p.name}, pluck="name")
	return names


def query_conditions(doctype, user=None):
	user = user or frappe.session.user
	if doctype in ADMIN_ONLY:
		return "" if sees_all(user) else "1=0"
	names = visible_profiles(user)
	if names is None:
		return ""
	if not names:
		return "1=0"
	inlist = ", ".join(frappe.db.escape(n) for n in names)
	parts = [f"`tab{doctype}`.`{f}` in ({inlist})" for f in SCOPED[doctype]]
	return "(" + " or ".join(parts) + ")"


def _make_query(doctype):
	def fn(user=None, doctype=doctype, **_kw):
		return query_conditions(doctype, user)
	return fn


def has_permission(doc, ptype=None, user=None, **_kw):
	"""Deny a document outside the user's scope. (Can only deny; DocPerm grants the action itself.)"""
	user = user or frappe.session.user
	if ptype == "create" or doc.get("__islocal") or doc.is_new():
		return True
	if doc.doctype in ADMIN_ONLY:
		return sees_all(user)
	names = visible_profiles(user)
	if names is None:
		return True
	for f in SCOPED.get(doc.doctype, []):
		v = doc.name if f == "name" else doc.get(f)
		if v and v in names:
			return True
	return False


def require_can_decide(agent_profile, requested_by=None):
	"""Approving a request: a manager, or the supervisor of the agent; never the person who asked."""
	user = frappe.session.user
	if is_manager(user):
		ok = True
	else:
		names = visible_profiles(user) or []
		p = profile_of(user)
		ok = bool(p and p.role_type == "Supervisor" and agent_profile in names and agent_profile != p.name)
	if not ok:
		frappe.throw(_("You cannot decide on this request"), frappe.PermissionError)
	if requested_by and requested_by == user and user != "Administrator":
		frappe.throw(_("You cannot approve your own request"), frappe.PermissionError)


# hooks.py points at these
pqc_profile = _make_query("Payment Agent Profile")
pqc_wallet = _make_query("Agent Wallet")
pqc_ledger = _make_query("Wallet Ledger Entry")
pqc_transaction = _make_query("Payment Transaction")
pqc_settlement = _make_query("Cash Settlement")
pqc_charge = _make_query("Wallet Charge")
pqc_approval = _make_query("Payment Approval Request")
pqc_audit = _make_query("Payment Audit Log")
