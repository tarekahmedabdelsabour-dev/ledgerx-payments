app_name = "payment_network"
app_title = "Payment Network"
app_publisher = "LedgerX"
app_description = "Electronic payments and a network of field agents: wallets, cash custody, commissions, settlements and accounting links"
app_email = "hello@ledgerx.local"
app_license = "mit"

required_apps = ["erpnext"]

# The look of the product comes from its branding app; this app only adds its own screens' styles.
app_include_css = ["/assets/payment_network/css/payment_network.css"]
app_include_icons = ["/assets/payment_network/icons/module-icons.svg"]

add_to_apps_screen = [
	{
		"name": "payment_network",
		"logo": "/assets/payment_network/images/payment.svg",
		"title": "Payment Network",
		"route": "/desk/payment-network",
		"has_permission": "payment_network.install.check_app_permission",
	}
]

# Isolation between agents, supervisors and managers is enforced here, in the backend.
permission_query_conditions = {
	"Payment Agent Profile": "payment_network.permissions.pqc_profile",
	"Agent Wallet": "payment_network.permissions.pqc_wallet",
	"Wallet Ledger Entry": "payment_network.permissions.pqc_ledger",
	"Payment Transaction": "payment_network.permissions.pqc_transaction",
	"Cash Settlement": "payment_network.permissions.pqc_settlement",
	"Wallet Charge": "payment_network.permissions.pqc_charge",
	"Payment Approval Request": "payment_network.permissions.pqc_approval",
	"Payment Audit Log": "payment_network.permissions.pqc_audit",
}
has_permission = {dt: "payment_network.permissions.has_permission" for dt in (
	"Payment Agent Profile", "Agent Wallet", "Wallet Ledger Entry", "Payment Transaction", "Cash Settlement",
	"Wallet Charge", "Payment Approval Request", "Payment Audit Log")}

# Custom Fields on the standard documents travel as fixtures; nothing is customised through Customize Form.
fixtures = [{"dt": "Custom Field", "filters": [["name", "like", "%-pn\\_%"]]}]

doc_events = {
	"Payment Entry": {"on_cancel": "payment_network.events.block_cancel"},
	"Journal Entry": {"on_cancel": "payment_network.events.block_cancel"},
	"User": {"on_update": "payment_network.events.user_updated"},
}

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["payment_network.tasks.review_pending"],
	},
}

after_install = "payment_network.install.after_install"
after_migrate = "payment_network.install.after_migrate"
