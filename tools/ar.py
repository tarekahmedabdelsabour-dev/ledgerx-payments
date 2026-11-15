"""Arabic strings of payment_network. PN holds the strings written for this app (ar_pn.py);
FALLBACK is a generic dictionary used only for plain words (Customer, Company...)."""
from ar_fleet_base import AR as FALLBACK  # noqa: E402

PN = {}
try:
	from ar_pn import PN as _P  # noqa: E402

	PN.update(_P)
except ImportError:
	pass

AR = dict(PN)
