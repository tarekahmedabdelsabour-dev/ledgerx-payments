"""Pure-logic tests (no Frappe): python3 -m pytest payment_network/tests/test_logic.py"""
import pytest

from payment_network.engine import logic as L


def test_rounding_and_ledger_sign():
	assert L.r2(1.005) == 1.01 and L.r2(2.675) == 2.68
	assert L.apply_entry(100, "Credit", 25.5) == 125.5
	assert L.apply_entry(100, "Debit", 25.5) == 74.5
	with pytest.raises(ValueError):
		L.apply_entry(1, "X", 1)


def test_status_transitions():
	assert L.can_transition("Pending", "Processing") and L.can_transition("Processing", "Success")
	assert L.can_transition("Success", "Reversed")
	assert not L.can_transition("Failed", "Success") and not L.can_transition("Reversed", "Success")
	assert not L.can_transition("Success", "Failed")


def test_fee_and_commission():
	assert L.calc_fee(200, 2, 1.5) == 5.0
	assert L.calc_commission("Percent", 200, 1.5) == 3.0
	tiers = [{"from_amount": 0, "to_amount": 100, "commission_amount": 1, "commission_percent": 0},
		{"from_amount": 100.01, "to_amount": 500, "commission_amount": 0, "commission_percent": 2},
		{"from_amount": 500.01, "to_amount": 0, "commission_amount": 5, "commission_percent": 0.5}]
	assert L.calc_commission("Tiered", 50, tiers=tiers) == 1.0
	assert L.calc_commission("Tiered", 300, tiers=tiers) == 6.0
	assert L.calc_commission("Tiered", 1000, tiers=tiers) == 10.0
	assert L.calc_commission("Tiered", 1000, tiers=[]) == 0.0


def test_split_pool_sums_exactly():
	for pool in (0.01, 0.07, 1.0, 3.33, 10.01, 99.99):
		s = L.split_pool(pool, 60, 20, 20)
		assert L.r2(s["agent"] + s["supervisor"] + s["company"]) == L.r2(pool)
	s = L.split_pool(10, 60, 20, 20, has_supervisor=False)
	assert s == {"agent": 6.0, "supervisor": 0.0, "company": 4.0}
	assert L.shares_valid(60, 20, 20) and not L.shares_valid(60, 20, 10)


def base(**o):
	c = dict(status="Active", amount=100, collect=105, txn_limit=500, global_txn_limit=0, daily_limit=1000,
		global_daily_limit=0, daily_total=0, float_balance=1000, custody=0, custody_limit=2000)
	c.update(o)
	return c


def test_limits():
	assert L.check_limits(base()) is None
	assert L.check_limits(base(status="Suspended"))[0] == "SUSPENDED"
	assert L.check_limits(base(amount=600))[0] == "TXN_LIMIT"
	assert L.check_limits(base(global_txn_limit=50))[0] == "TXN_LIMIT"
	assert L.check_limits(base(daily_total=950))[0] == "DAILY_LIMIT"
	assert L.check_limits(base(float_balance=99.99))[0] == "INSUFFICIENT"
	assert L.check_limits(base(float_balance=100)) is None
	assert L.check_limits(base(custody=1900))[0] == "CUSTODY_LIMIT"
	assert L.check_limits(base(custody=1895)) is None
	assert L.check_limits(base(txn_limit=0, daily_limit=0, custody_limit=0, custody=10**6)) is None


def test_hierarchy():
	assert L.transfer_allowed("Manager", "Supervisor", False)
	assert L.transfer_allowed("Manager", "Agent", False)
	assert L.transfer_allowed("Supervisor", "Agent", True)
	assert not L.transfer_allowed("Supervisor", "Agent", False)
	assert not L.transfer_allowed("Agent", "Agent", True)
	assert not L.transfer_allowed("Supervisor", "Supervisor", True)
	assert L.settlement_stage_ok("Agent to Supervisor", "Agent", "Supervisor", True)
	assert not L.settlement_stage_ok("Agent to Supervisor", "Agent", "Supervisor", False)
	assert L.settlement_stage_ok("Supervisor to Manager", "Supervisor", "Manager", False)
	assert not L.settlement_stage_ok("Supervisor to Manager", "Agent", "Manager", True)
	assert L.settlement_difference(1000, 50, 940) == 10.0
	assert L.settlement_difference(1000, 50, 960) == -10.0


def test_pin():
	assert L.valid_pin("1234") and L.valid_pin("123456")
	assert not L.valid_pin("123") and not L.valid_pin("12ab") and not L.valid_pin("1234567") and not L.valid_pin("")
	h = L.hash_pin("4821")
	assert h.startswith("pbkdf2_sha256$") and "4821" not in h
	assert L.verify_pin("4821", h) and not L.verify_pin("4822", h)
	assert not L.verify_pin("4821", "") and not L.verify_pin("4821", "garbage")
	assert L.hash_pin("4821") != L.hash_pin("4821")


def test_signature():
	body = b'{"reference":"PTX-1","status":"Success"}'
	sig = L.sign("s3cret", body)
	assert L.verify_signature("s3cret", body, sig)
	assert L.verify_signature("s3cret", body, "sha256=" + sig.upper())
	assert not L.verify_signature("other", body, sig)
	assert not L.verify_signature("s3cret", body + b" ", sig)
	assert not L.verify_signature("", body, sig) and not L.verify_signature("s3cret", body, "")
