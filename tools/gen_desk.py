"""Generate the desk files exactly like HRMS ships them: app tile (Desktop Icon), module rail (Dock),
one Workspace + Workspace Sidebar per module, and the icon sprite.   python3 tools/gen_desk.py"""
import json
import os
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPNAME = "payment_network"
APP = os.path.join(ROOT, APPNAME)
MODULE = "Payment Network"
MODDIR = "payment_network"
APP_LABEL = "Payment Network"
APP_ROUTE = "/desk/payment-network"
STAMP = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")  # newer than the DB copy, or migrate skips the file

# (title, lucide icon, dock icon, [(label, link_to, kind, icon)], [related (label, doctype, icon)])
MODULES = [
	("Payment Network", "credit-card", "payment-network-soft", [
		("Agent Screen", "/agent-pay", "URL", "smartphone"),
		("Payment Transaction", "Payment Transaction", "DocType", "arrow-left-right"),
		("Payment Agent Profile", "Payment Agent Profile", "DocType", "user-round"),
		("Agent Wallet", "Agent Wallet", "DocType", "wallet"),
		("Wallet Charge", "Wallet Charge", "DocType", "plus-circle"),
		("Cash Settlement", "Cash Settlement", "DocType", "handshake"),
		("Payment Approval Request", "Payment Approval Request", "DocType", "check-square"),
		("Wallet Ledger Entry", "Wallet Ledger Entry", "DocType", "book-open"),
		("Payment Service", "Payment Service", "DocType", "plug"),
		("Commission Rule", "Commission Rule", "DocType", "percent"),
		("Payment Audit Log", "Payment Audit Log", "DocType", "shield-check"),
		("Payment Settings", "Payment Settings", "DocType", "settings"),
		("Transactions Today", "Transactions Today", "Report", "calendar-check"),
		("Wallet Balances", "Wallet Balances", "Report", "wallet"),
		("Open Custody", "Open Custody", "Report", "banknote"),
		("Commissions Due", "Commissions Due", "Report", "hand-coins"),
		("Failed and Pending Transactions", "Failed and Pending Transactions", "Report", "alert-triangle"),
		("Settlement Differences", "Settlement Differences", "Report", "scale"),
		("Agent and Supervisor Performance", "Agent and Supervisor Performance", "Report", "trending-up"),
	], [("Sales Invoice", "Sales Invoice", "receipt"), ("Payment Entry", "Payment Entry", "wallet"),
		("Journal Entry", "Journal Entry", "book"), ("Purchase Invoice", "Purchase Invoice", "file-text"),
		("Mode of Payment", "Mode of Payment", "credit-card")]),
]

REPORT_DT = {
	"Transactions Today": "Payment Transaction", "Wallet Balances": "Agent Wallet", "Open Custody": "Agent Wallet",
	"Commissions Due": "Agent Wallet", "Failed and Pending Transactions": "Payment Transaction",
	"Settlement Differences": "Cash Settlement", "Agent and Supervisor Performance": "Payment Transaction",
}


def dump(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=True)
		fh.write("\n")


def scrub(n):
	return n.lower().replace(" ", "_")


def item(label, link_to, link_type, icon="", child=0):
	if link_type == "URL":
		return {"child": child, "collapsible": 1, "icon": icon, "indent": 0, "keep_closed": 0, "label": label,
			"url": link_to, "link_type": "URL", "show_arrow": 0, "type": "Link"}
	return {"child": child, "collapsible": 1, "icon": icon, "indent": 0, "keep_closed": 0, "label": label,
		"link_to": link_to, "link_type": link_type, "show_arrow": 0, "type": "Link"}


def section(label, icon, closed=1):
	return {"child": 0, "collapsible": 1, "icon": icon, "indent": 1, "keep_closed": closed, "label": label,
		"link_type": "DocType", "show_arrow": 0, "type": "Section Break"}


# ---------------------------------------------------------------- dashboards
def _f(*rows):
	return json.dumps([list(r) for r in rows])


# name: (doctype, filters, function, sum_field)
CARDS = {
	"Transactions Today": ("Payment Transaction", _f(("Payment Transaction", "creation", "Timespan", "today")), "Count", None),
	"Successful Amount Today": ("Payment Transaction", _f(("Payment Transaction", "status", "=", "Success"), ("Payment Transaction", "creation", "Timespan", "today")), "Sum", "amount"),
	"Failed Transactions This Month": ("Payment Transaction", _f(("Payment Transaction", "status", "=", "Failed"), ("Payment Transaction", "creation", "Timespan", "this month")), "Count", None),
	"Processing Transactions": ("Payment Transaction", _f(("Payment Transaction", "status", "=", "Processing")), "Count", None),
	"Pending Approvals": ("Payment Approval Request", _f(("Payment Approval Request", "status", "=", "Pending")), "Count", None),
	"Active Agents": ("Payment Agent Profile", _f(("Payment Agent Profile", "status", "=", "Active"), ("Payment Agent Profile", "role_type", "=", "Agent")), "Count", None),
}

# name: (doctype, kind, type, filters, group_by_or_(based_on,value_field))
CHARTS = {
	"Payments per Month": ("Payment Transaction", "Sum", "Bar", _f(("Payment Transaction", "status", "=", "Success")), ("creation", "amount")),
	"Transactions by Status": ("Payment Transaction", "Group By", "Donut", _f(), "status"),
	"Transactions by Service": ("Payment Transaction", "Group By", "Donut", _f(("Payment Transaction", "status", "=", "Success")), "service"),
}

DASH = {
	"Payment Network": (["Transactions Today", "Successful Amount Today", "Processing Transactions", "Pending Approvals"], ["Payments per Month", "Transactions by Status"]),
}


def write_dashboards():
	for name, (dt, flt, fn, field) in CARDS.items():
		card = {"creation": STAMP, "docstatus": 0, "doctype": "Number Card", "document_type": dt, "filters_json": flt,
			"function": fn, "idx": 0, "is_public": 1, "is_standard": 1, "label": name, "modified": STAMP,
			"modified_by": "Administrator", "module": MODULE, "name": name, "owner": "Administrator",
			"show_percentage_stats": 1, "stats_time_interval": "Monthly", "type": "Document Type"}
		if field:
			card["aggregate_function_based_on"] = field
		dump(os.path.join(APP, MODDIR, "number_card", scrub(name), scrub(name) + ".json"), card)
	for name, (dt, kind, typ, flt, spec) in CHARTS.items():
		ch = {"chart_name": name, "chart_type": kind, "creation": STAMP, "docstatus": 0, "doctype": "Dashboard Chart",
			"document_type": dt, "dynamic_filters_json": "", "filters_json": flt, "idx": 0, "is_public": 1,
			"is_standard": 1, "modified": STAMP, "modified_by": "Administrator", "module": MODULE, "name": name,
			"number_of_groups": 0, "owner": "Administrator", "type": typ, "use_report_chart": 0, "y_axis": []}
		if kind == "Group By":
			ch.update({"group_by_based_on": spec, "group_by_type": "Count", "timeseries": 0})
		else:
			ch.update({"based_on": spec[0], "value_based_on": spec[1], "timeseries": 1, "timespan": "Last Year",
				"time_interval": "Monthly"})
		dump(os.path.join(APP, MODDIR, "dashboard_chart", scrub(name), scrub(name) + ".json"), ch)


def main():
	write_dashboards()
	dock_items, icons = [], []
	for idx, (title, lucide, dock_icon, items, related) in enumerate(MODULES):
		# ---- workspace (landing page of the module)
		content = [{"id": uuid.uuid4().hex[:10], "type": "header",
			"data": {"text": f'<span class="h4"><b>{title}</b></span>', "col": 12}}]
		cards, charts = DASH.get(title, ([], []))
		for c in charts:
			content.append({"id": uuid.uuid4().hex[:10], "type": "chart", "data": {"chart_name": c, "col": 6}})
		for c in cards:
			content.append({"id": uuid.uuid4().hex[:10], "type": "number_card", "data": {"number_card_name": c, "col": 3}})
		shortcuts = []
		for label, target, kind, ic in items:
			content.append({"id": uuid.uuid4().hex[:10], "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
			sc = {"label": label, "link_to": target, "type": kind}
			if kind == "URL":
				sc = {"label": label, "url": target, "type": "URL"}
			elif kind == "DocType":
				sc["doc_view"] = "List"
			else:
				sc["report_ref_doctype"] = REPORT_DT[target]
			shortcuts.append(sc)
		mod = os.path.join(APP, scrub(title))
		os.makedirs(mod, exist_ok=True)
		open(os.path.join(mod, "__init__.py"), "a").close()
		dump(os.path.join(mod, "workspace", scrub(title), scrub(title) + ".json"), {
			"charts": [{"chart_name": c, "label": c} for c in charts], "content": json.dumps(content), "creation": STAMP, "custom_blocks": [], "docstatus": 0,
			"doctype": "Workspace", "for_user": "", "hide_custom": 1, "icon": lucide, "idx": idx + 1,
			"is_hidden": 0, "label": title, "links": [], "modified": STAMP, "modified_by": "Administrator",
			"module": title, "name": title, "number_cards": [{"label": c, "number_card_name": c} for c in cards], "owner": "Administrator", "parent_page": "",
			"public": 1, "quick_lists": [], "roles": [], "sequence_id": float(idx + 20), "shortcuts": shortcuts,
			"title": title, "type": "Workspace",
		})
		# ---- sidebar (frappe 16.5x: a standard `Sidebar` rooted at the app, owned by the module)
		sb = [item("Home", title, "Workspace", "house")]
		for label, target, kind, ic in items:
			sb.append(item(label, target, kind, ic))
		if related:
			sb.append(section("Related", "link-2"))
			for label, target, ic in related:
				sb.append(item(label, target, "DocType", ic, child=1))
		for i, it in enumerate(sb, start=1):
			it.update({"doctype": "Sidebar Item", "parentfield": "items", "parenttype": "Sidebar", "idx": i})
		dump(os.path.join(APP, "sidebar", scrub(title), scrub(title) + ".json"), {
			"doctype": "Sidebar", "name": title, "module": title, "title": title, "header_icon": lucide,
			"app": "payment_network", "standard": 1, "items": sb,
		})
		# ---- dock entry
		dock_items.append({"added": 0, "hidden": 0, "icon": dock_icon, "link_to": title, "link_type": "Sidebar", "title": title})

	dump(os.path.join(APP, "dock", "payment_network", "payment_network.json"), {
		"app": "payment_network", "creation": STAMP, "docstatus": 0, "doctype": "Dock", "idx": 0, "items": dock_items,
		"modified": STAMP, "modified_by": "Administrator", "name": "payment_network", "owner": "Administrator", "standard": 1,
	})


if __name__ == "__main__":
	main()
