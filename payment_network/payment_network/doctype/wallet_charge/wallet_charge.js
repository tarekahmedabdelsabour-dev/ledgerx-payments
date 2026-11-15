frappe.ui.form.on("Wallet Charge", {
	setup(frm) {
		frm.set_query("to_profile", () => ({ filters: { status: "Active" } }));
		frm.set_query("from_profile", () => ({ filters: { status: "Active" } }));
	},
});
