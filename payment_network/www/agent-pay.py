import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/agent-pay"
		raise frappe.Redirect
	context.no_cache = 1
	context.show_sidebar = False
	context.title = "شبكة الدفع"
	context.csrf_token = frappe.sessions.get_csrf_token()
