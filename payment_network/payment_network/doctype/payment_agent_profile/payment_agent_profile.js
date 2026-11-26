frappe.ui.form.on("Payment Agent Profile", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Set PIN"), () => {
			frappe.prompt({ fieldname: "pin", fieldtype: "Password", label: __("New PIN (4 to 6 digits)"), reqd: 1 }, (v) => {
				frm.call("set_pin", { pin: v.pin }).then(() => { frappe.show_alert(__("PIN saved")); frm.reload_doc(); });
			}, __("Set PIN"));
		}, __("Security"));
		if (frm.doc.pending_device_id) {
			frm.add_custom_button(__("Approve Device"), () => frm.call("approve_device").then(() => frm.reload_doc()), __("Security"));
		}
		frm.add_custom_button(__("Reset Device"), () => frm.call("reset_device").then(() => frm.reload_doc()), __("Security"));
		frm.add_custom_button(__("Unlock PIN"), () => frm.call("unlock").then(() => frm.reload_doc()), __("Security"));
		if (frm.doc.wallet) frm.add_custom_button(__("Wallet"), () => frappe.set_route("Form", "Agent Wallet", frm.doc.wallet));
	},
});
