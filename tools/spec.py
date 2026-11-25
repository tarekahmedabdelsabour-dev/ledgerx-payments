"""Field specs for every Payment Network DocType. See gen.py."""


def F(fieldname, ftype, label, **o):
	return ("F", fieldname, ftype, label, o)


def S(label="", **o):
	return ("S", label, o)


def C(**o):
	return ("C", o)


DOCTYPES = []
RO = dict(read_only=1, no_copy=1)

# perms: list of (role, codes) -- r w cr d exp rep prt eml shr sub can amd
MGR, SUP, AGT, AUD, SYS = "Payment Manager", "Payment Supervisor", "Payment Agent", "Payment Auditor", "System Manager"
READ = "r_rep_prt_exp"

# --------------------------------------------------------------------------- settings
DOCTYPES.append(dict(
	name="Payment Settings", single=True, icon="fa fa-cog",
	perms=[(MGR, "r_w"), (SYS, "r_w"), (AUD, "r")],
	fields=[
		S("General"),
		F("company", "Link", "Company", options="Company"),
		F("cost_center", "Link", "Cost Center", options="Cost Center"),
		C(),
		F("provider", "Select", "Payment Provider", options="Mock", default="Mock",
			description="Pick the real provider here once its adapter is installed (see docs/PROVIDERS.md)."),
		F("mode", "Select", "Mode", options="Sandbox\nLive", default="Sandbox",
			description="Sandbox never contacts a real provider and allows the demo data. Switch to Live only after testing."),
		S("Limits"),
		F("global_txn_limit", "Currency", "Max Amount per Transaction (all agents)", description="0 = no global limit."),
		F("global_daily_limit", "Currency", "Max Daily Total per Agent (all agents)", description="0 = no global limit."),
		C(),
		F("approval_threshold", "Currency", "Amount Needing Approval", description="A transaction at or above this waits for a supervisor/manager approval. 0 = never."),
		F("max_pin_attempts", "Int", "Wrong PIN Attempts Before Lock", default=5),
		F("lock_minutes", "Int", "PIN Lock Duration (minutes)", default=15),
		S("Pending Transactions"),
		F("pending_review_minutes", "Int", "Review Pending Transactions After (minutes)", default=5,
			description="A scheduled job asks the provider about transactions still processing after this long."),
		C(),
		F("enable_supplier_payments", "Check", "Allow Paying Suppliers Electronically", default=0),
		S("Provider Connection"),
		F("provider_api_base", "Data", "Provider API Address"),
		F("provider_api_key", "Password", "Provider API Key"),
		C(),
		F("provider_secret", "Password", "Provider Secret"),
		F("webhook_secret", "Password", "Webhook Signing Secret",
			description="The provider signs each callback with this secret (HMAC-SHA256, header X-Signature). Unsigned or wrongly signed callbacks are rejected."),
		S("Accounts"),
		F("agent_custody_account", "Link", "Agents Cash Custody Account", options="Account"),
		F("provider_clearing_account", "Link", "Payment Provider Clearing Account", options="Account"),
		F("wallet_liability_account", "Link", "Wallet Balances Liability Account", options="Account"),
		C(),
		F("commission_income_account", "Link", "Commission Income Account", options="Account"),
		F("commission_expense_account", "Link", "Agents Commission Expense Account", options="Account"),
		F("cash_account", "Link", "Company Cash Account (receives settlements)", options="Account"),
		F("difference_account", "Link", "Cash Difference Account", options="Account"),
		S("Sales Link"),
		F("mode_of_payment", "Link", "Electronic Payment Mode", options="Mode of Payment", default="Electronic Payment"),
	],
))

# --------------------------------------------------------------------------- profile
DOCTYPES.append(dict(
	name="Payment Agent Profile", autoname="format:PA-{#####}", title_field="full_name", icon="fa fa-user",
	search_fields="full_name,user,mobile_no", perms=[(MGR, "r_cr_w_d_exp_rep_prt"), (SYS, "r_cr_w_d_exp_rep_prt"), (SUP, "r_rep_prt"), (AGT, "r"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("user", "Link", "Login User", options="User", reqd=1, unique=1, in_list_view=1),
		F("full_name", "Data", "Full Name", fetch_from="user.full_name", read_only=1, in_list_view=1),
		F("role_type", "Select", "Role Type", options="Agent\nSupervisor\nManager", default="Agent", reqd=1, in_list_view=1, in_standard_filter=1),
		F("supervisor", "Link", "Supervisor", options="Payment Agent Profile", in_standard_filter=1,
			depends_on="eval:doc.role_type=='Agent'", description="The supervisor this agent reports to; he sees this agent's data."),
		C(),
		F("status", "Select", "Status", options="Active\nSuspended", default="Active", in_list_view=1, in_standard_filter=1),
		F("mobile_no", "Data", "Mobile No", options="Phone"),
		F("company", "Link", "Company", options="Company"),
		S("Limits"),
		F("txn_limit", "Currency", "Max Amount per Transaction"),
		F("daily_limit", "Currency", "Max Daily Total"),
		C(),
		F("cash_custody_limit", "Currency", "Cash Custody Limit", description="Operations stop automatically when the cash held reaches this. 0 = no limit."),
		S("Device and PIN"),
		F("device_id", "Data", "Registered Device"),
		F("pin_set", "Check", "PIN is Set", **RO),
		C(),
		F("failed_pin_attempts", "Int", "Failed PIN Attempts", **RO),
		F("locked_until", "Datetime", "Locked Until", **RO),
		F("pin_hash", "Data", "PIN Hash", hidden=1, print_hide=1, **RO),
		F("wallet", "Link", "Wallet", options="Agent Wallet", **RO),
	],
))

# --------------------------------------------------------------------------- wallet
DOCTYPES.append(dict(
	name="Agent Wallet", autoname="field:profile", title_field="agent_name", icon="fa fa-credit-card",
	perms=[(MGR, "r_rep_prt_exp"), (SYS, "r_rep_prt_exp"), (SUP, "r_rep_prt"), (AGT, "r"), (AUD, "r_rep_prt_exp")],
	no_copy_doc=True,
	fields=[
		F("profile", "Link", "Agent Profile", options="Payment Agent Profile", reqd=1, unique=1, read_only=1, in_list_view=1),
		F("agent_name", "Data", "Name", fetch_from="profile.full_name", read_only=1, in_list_view=1),
		F("role_type", "Data", "Role Type", fetch_from="profile.role_type", read_only=1, in_list_view=1),
		F("company", "Link", "Company", options="Company", read_only=1),
		S("Balances (calculated from the ledger, never edited by hand)"),
		F("balance", "Currency", "Available Balance", read_only=1, in_list_view=1, description="Balance the holder can spend on transactions."),
		F("commission_balance", "Currency", "Commission Balance", read_only=1, in_list_view=1, description="Commission earned and not yet settled."),
		C(),
		F("custody_balance", "Currency", "Cash Held", read_only=1, in_list_view=1, description="Cash collected from customers and not yet handed over."),
		F("last_entry_at", "Datetime", "Last Entry", read_only=1),
	],
))

# --------------------------------------------------------------------------- ledger
DOCTYPES.append(dict(
	name="Wallet Ledger Entry", autoname="format:WLE-{########}", icon="fa fa-book", sort_field="creation", no_copy_doc=True,
	perms=[(MGR, "r_rep_prt_exp"), (SYS, "r_rep_prt_exp"), (SUP, "r_rep_prt_exp"), (AGT, "r_rep_prt"), (AUD, "r_rep_prt_exp")],
	allow_import=0, track_changes=0,
	fields=[
		F("wallet", "Link", "Wallet", options="Agent Wallet", reqd=1, read_only=1, in_list_view=1, in_standard_filter=1),
		F("agent", "Link", "Agent Profile", options="Payment Agent Profile", read_only=1, in_standard_filter=1),
		F("bucket", "Select", "Balance Type", options="Available\nCommission\nCash Held", read_only=1, in_list_view=1, in_standard_filter=1),
		F("direction", "Select", "Direction", options="Debit\nCredit", read_only=1, in_list_view=1, description="Credit adds to the balance, Debit subtracts from it."),
		F("amount", "Currency", "Amount", read_only=1, in_list_view=1),
		F("balance_after", "Currency", "Balance After", read_only=1, in_list_view=1),
		S(),
		F("posting_datetime", "Datetime", "Posted On", read_only=1),
		F("reference_doctype", "Link", "Reference Type", options="DocType", read_only=1),
		F("reference_name", "Dynamic Link", "Reference", options="reference_doctype", read_only=1),
		C(),
		F("group_id", "Data", "Entry Group", read_only=1, search_index=1, description="The two opposite entries of one transfer share this."),
		F("remarks", "Small Text", "Remarks", read_only=1),
	],
))

# --------------------------------------------------------------------------- service / commission
DOCTYPES.append(dict(
	name="Commission Tier", istable=True,
	fields=[
		F("from_amount", "Currency", "From Amount", in_list_view=1, reqd=1),
		F("to_amount", "Currency", "To Amount", in_list_view=1, description="0 = no upper limit."),
		F("commission_amount", "Currency", "Fixed Commission", in_list_view=1),
		F("commission_percent", "Percent", "Commission %", in_list_view=1),
	],
))
DOCTYPES.append(dict(
	name="Commission Rule", autoname="field:rule_name", icon="fa fa-percent", title_field="rule_name",
	perms=[(MGR, "r_cr_w_d_exp_rep_prt"), (SYS, "r_cr_w_d_exp_rep_prt"), (SUP, "r_rep_prt"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("rule_name", "Data", "Rule Name", reqd=1, unique=1, in_list_view=1),
		F("enabled", "Check", "Enabled", default=1, in_list_view=1),
		F("basis", "Select", "Calculated As", options="Percent\nTiered", default="Percent", reqd=1, in_list_view=1),
		F("percent", "Percent", "Commission %", depends_on="eval:doc.basis=='Percent'", description="Percent of the transaction amount."),
		S("Tiers", depends_on="eval:doc.basis=='Tiered'"),
		F("tiers", "Table", "Tiers", options="Commission Tier"),
		S("Distribution (must total 100%)"),
		F("agent_share", "Percent", "Agent Share %", default=60),
		F("supervisor_share", "Percent", "Supervisor Share %", default=20),
		C(),
		F("company_share", "Percent", "Company Share %", default=20),
	],
))
DOCTYPES.append(dict(
	name="Payment Service", autoname="field:service_name", icon="fa fa-plug", title_field="service_name",
	perms=[(MGR, "r_cr_w_d_exp_rep_prt"), (SYS, "r_cr_w_d_exp_rep_prt"), (SUP, "r_rep_prt"), (AGT, "r"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("service_name", "Data", "Service Name", reqd=1, unique=1, in_list_view=1),
		F("category", "Select", "Category", options="Bill Payment\nMobile Top-up\nVoucher\nOther", default="Bill Payment", in_list_view=1, in_standard_filter=1),
		F("enabled", "Check", "Enabled", default=1, in_list_view=1),
		F("provider_code", "Data", "Provider Service Code", description="The code the provider uses for this service."),
		C(),
		F("commission_rule", "Link", "Commission Rule", options="Commission Rule"),
		F("requires_reference", "Check", "Customer Reference Required", default=1),
		F("reference_label", "Data", "Reference Label", default="Mobile or Account Number"),
		S("Amounts and Fees"),
		F("min_amount", "Currency", "Minimum Amount"),
		F("max_amount", "Currency", "Maximum Amount", description="0 = no maximum."),
		C(),
		F("fee_fixed", "Currency", "Fixed Fee Charged to Customer"),
		F("fee_percent", "Percent", "Fee % Charged to Customer"),
		F("description", "Small Text", "Description"),
	],
))

# --------------------------------------------------------------------------- transaction
DOCTYPES.append(dict(
	name="Payment Transaction", autoname="format:PTX-{#######}", icon="fa fa-exchange", title_field="customer_reference",
	search_fields="customer_reference,provider_ref,idempotency_key", sort_field="creation", no_copy_doc=True, allow_import=0,
	perms=[(MGR, "r_rep_prt_exp"), (SYS, "r_rep_prt_exp"), (SUP, "r_rep_prt_exp"), (AGT, "r_rep_prt"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("kind", "Select", "Kind", options="Service\nInvoice Payment\nSupplier Payment", default="Service", read_only=1, in_list_view=1, in_standard_filter=1),
		F("status", "Select", "Status", options="Pending\nProcessing\nSuccess\nFailed\nReversed", default="Pending", read_only=1, in_list_view=1, in_standard_filter=1),
		F("agent", "Link", "Agent Profile", options="Payment Agent Profile", read_only=1, in_list_view=1, in_standard_filter=1),
		F("agent_name", "Data", "Agent", fetch_from="agent.full_name", read_only=1),
		C(),
		F("supervisor", "Link", "Supervisor", options="Payment Agent Profile", read_only=1, in_standard_filter=1),
		F("wallet", "Link", "Wallet", options="Agent Wallet", read_only=1),
		F("company", "Link", "Company", options="Company", read_only=1),
		F("sandbox", "Check", "Sandbox", read_only=1),
		S("Operation"),
		F("service", "Link", "Service", options="Payment Service", read_only=1, in_list_view=1, in_standard_filter=1),
		F("customer", "Link", "Customer", options="Customer", read_only=1),
		F("customer_reference", "Data", "Customer Reference", read_only=1, in_list_view=1),
		C(),
		F("amount", "Currency", "Amount", read_only=1, in_list_view=1),
		F("fee", "Currency", "Fee", read_only=1),
		F("total_collected", "Currency", "Total Collected from Customer", read_only=1),
		S("Provider"),
		F("idempotency_key", "Data", "Idempotency Key", unique=1, reqd=1, read_only=1, no_copy=1, search_index=1),
		F("provider", "Data", "Provider", read_only=1),
		F("provider_ref", "Data", "Provider Reference", read_only=1, search_index=1),
		C(),
		F("provider_status", "Data", "Provider Status", read_only=1),
		F("failure_reason", "Small Text", "Failure Reason", read_only=1),
		S("Commission"),
		F("agent_commission", "Currency", "Agent Commission", read_only=1),
		F("supervisor_commission", "Currency", "Supervisor Commission", read_only=1),
		C(),
		F("company_commission", "Currency", "Company Share", read_only=1),
		S("Links"),
		F("sales_invoice", "Link", "Sales Invoice", options="Sales Invoice", read_only=1),
		F("pos_invoice", "Link", "POS Invoice", options="POS Invoice", read_only=1),
		F("supplier", "Link", "Supplier", options="Supplier", read_only=1),
		F("purchase_invoice", "Link", "Purchase Invoice", options="Purchase Invoice", read_only=1),
		C(),
		F("payment_entry", "Link", "Payment Entry", options="Payment Entry", read_only=1),
		F("journal_entry", "Link", "Journal Entry", options="Journal Entry", read_only=1),
		F("reversal_journal_entry", "Link", "Reversal Journal Entry", options="Journal Entry", read_only=1),
		F("approval_request", "Link", "Approval Request", options="Payment Approval Request", read_only=1),
		S("Audit"),
		F("device_id", "Data", "Device", read_only=1),
		F("ip_address", "Data", "IP Address", read_only=1),
		C(),
		F("started_at", "Datetime", "Started", read_only=1),
		F("completed_at", "Datetime", "Completed", read_only=1),
		F("reversed_at", "Datetime", "Reversed", read_only=1),
	],
))

# --------------------------------------------------------------------------- charge / settlement / approval / audit
DOCTYPES.append(dict(
	name="Wallet Charge", autoname="format:WCH-{#####}", submittable=True, icon="fa fa-plus-circle",
	perms=[(MGR, "r_cr_w_d_exp_rep_prt_sub_can"), (SYS, "r_cr_w_d_exp_rep_prt_sub_can"), (SUP, "r_w_cr_rep_prt_sub"), (AGT, "r"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("charge_type", "Select", "Type", options="Transfer\nCompany Funding", default="Transfer", reqd=1, in_list_view=1,
			description="Company Funding adds money from the company's bank or cash to a manager's wallet. Transfer moves balance down the chain manager > supervisor > agent (or back up)."),
		F("posting_date", "Date", "Date", default="Today", reqd=1),
		F("company", "Link", "Company", options="Company"),
		C(),
		F("amount", "Currency", "Amount", reqd=1, in_list_view=1),
		F("remarks", "Small Text", "Remarks"),
		S("Wallets"),
		F("from_profile", "Link", "From", options="Payment Agent Profile", depends_on="eval:doc.charge_type=='Transfer'", mandatory_depends_on="eval:doc.charge_type=='Transfer'", in_list_view=1),
		F("to_profile", "Link", "To", options="Payment Agent Profile", reqd=1, in_list_view=1),
		C(),
		F("funding_account", "Link", "Paid From (bank or cash account)", options="Account", depends_on="eval:doc.charge_type=='Company Funding'", mandatory_depends_on="eval:doc.charge_type=='Company Funding'"),
		F("journal_entry", "Link", "Journal Entry", options="Journal Entry", **RO),
		F("amended_from", "Link", "Amended From", options="Wallet Charge", read_only=1, no_copy=1, print_hide=1),
	],
))
DOCTYPES.append(dict(
	name="Cash Settlement", autoname="format:CSE-{#####}", submittable=True, icon="fa fa-handshake-o",
	perms=[(MGR, "r_cr_w_d_exp_rep_prt_sub_can"), (SYS, "r_cr_w_d_exp_rep_prt_sub_can"), (SUP, "r_w_cr_rep_prt_sub"), (AGT, "r_w_cr_rep_prt"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("stage", "Select", "Stage", options="Agent to Supervisor\nSupervisor to Manager", reqd=1, in_list_view=1, in_standard_filter=1),
		F("settlement_date", "Date", "Date", default="Today", reqd=1),
		F("company", "Link", "Company", options="Company"),
		C(),
		F("from_profile", "Link", "Handed By", options="Payment Agent Profile", reqd=1, in_list_view=1, in_standard_filter=1),
		F("to_profile", "Link", "Received By", options="Payment Agent Profile", reqd=1, in_list_view=1, in_standard_filter=1),
		S("Amounts"),
		F("custody_before", "Currency", "Cash Held Before", read_only=1, no_copy=1),
		F("amount_due", "Currency", "Cash Being Settled", reqd=1, in_list_view=1, description="The part of the cash held that this settlement clears."),
		C(),
		F("commission_offset", "Currency", "Commission Deducted", description="Earned commission the sender keeps from the cash instead of being paid later."),
		F("amount_handed", "Currency", "Cash Actually Handed", reqd=1, in_list_view=1),
		F("difference", "Currency", "Difference (shortage +, excess -)", read_only=1, no_copy=1),
		F("notes", "Small Text", "Notes"),
		S("Confirmation"),
		F("confirmed_by", "Link", "Confirmed By", options="User", **RO),
		F("journal_entry", "Link", "Journal Entry", options="Journal Entry", **RO),
		F("amended_from", "Link", "Amended From", options="Cash Settlement", read_only=1, no_copy=1, print_hide=1),
	],
))
DOCTYPES.append(dict(
	name="Payment Approval Request", autoname="format:PAR-{#####}", icon="fa fa-check-square-o",
	perms=[(MGR, "r_w_exp_rep_prt"), (SYS, "r_w_exp_rep_prt"), (SUP, "r_w_rep_prt"), (AGT, "r"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("request_type", "Select", "Request Type", options="Large Transaction\nReversal", reqd=1, read_only=1, in_list_view=1, in_standard_filter=1),
		F("status", "Select", "Status", options="Pending\nApproved\nRejected", default="Pending", read_only=1, in_list_view=1, in_standard_filter=1),
		F("transaction", "Link", "Transaction", options="Payment Transaction", read_only=1, in_list_view=1),
		F("agent", "Link", "Agent Profile", options="Payment Agent Profile", read_only=1, in_standard_filter=1),
		C(),
		F("amount", "Currency", "Amount", read_only=1, in_list_view=1),
		F("requested_by", "Link", "Requested By", options="User", read_only=1),
		F("reason", "Small Text", "Reason", read_only=1),
		S("Decision"),
		F("decided_by", "Link", "Decided By", options="User", **RO),
		F("decided_on", "Datetime", "Decided On", **RO),
		C(),
		F("decision_note", "Small Text", "Decision Note"),
	],
))
DOCTYPES.append(dict(
	name="Payment Audit Log", autoname="format:PAL-{########}", icon="fa fa-shield", sort_field="creation", no_copy_doc=True, allow_import=0,
	perms=[(MGR, "r_rep_prt_exp"), (SYS, "r_rep_prt_exp"), (AUD, "r_rep_prt_exp")],
	fields=[
		F("timestamp", "Datetime", "When", read_only=1, in_list_view=1),
		F("user", "Link", "User", options="User", read_only=1, in_list_view=1, in_standard_filter=1),
		F("action", "Data", "Action", read_only=1, in_list_view=1, in_standard_filter=1),
		F("reference_doctype", "Link", "Reference Type", options="DocType", read_only=1),
		F("reference_name", "Dynamic Link", "Reference", options="reference_doctype", read_only=1, in_list_view=1),
		C(),
		F("ip_address", "Data", "IP Address", read_only=1),
		F("device_id", "Data", "Device", read_only=1),
		F("details", "Long Text", "Details", read_only=1),
	],
))

EXTRA_STRINGS = [
	"Payment Agent", "Payment Supervisor", "Payment Manager", "Payment Auditor",
]
