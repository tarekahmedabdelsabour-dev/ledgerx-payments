frappe.ui.form.on("Payment Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Create Accounts"), () => {
			frappe.confirm(__("Create the missing payment accounts under the standard account groups?"), () => {
				frappe.call({
					method: "payment_network.payment_network.doctype.payment_settings.payment_settings.create_accounts",
					callback: (r) => { frappe.msgprint((r.message || []).length ? (r.message || []).join("<br>") : __("Nothing to create: all accounts are set.")); frm.reload_doc(); },
				});
			});
		}, __("Setup"));
		frappe.call({
			method: "payment_network.payment_network.doctype.payment_settings.payment_settings.webhook_url",
			callback: (r) => frm.set_intro(__("Callback address for the provider: {0}", [`<code style="user-select:all">${r.message}</code>`]), "blue"),
		});
	},
});
