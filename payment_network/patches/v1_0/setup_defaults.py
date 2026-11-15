"""Migrations step 1: roles, module, Electronic Payment mode of payment (the custom fields come from fixtures)."""
from payment_network import install


def execute():
	install.ensure_modules()
	install.ensure_roles()
	install.ensure_mode_of_payment()
