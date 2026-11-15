frappe.ui.form.on("Agent Wallet", {
	refresh(frm) {
		frm.add_custom_button(__("Verify Balances"), () => {
			frm.call("verify_balances").then((r) => {
				const m = r.message || {};
				frappe.msgprint(m.ok ? __("The balances match the ledger.") : __("The balances do NOT match the ledger: {0}", [JSON.stringify(m.mismatch)]));
			});
		});
		frm.add_custom_button(__("Ledger"), () => frappe.set_route("List", "Wallet Ledger Entry", { wallet: frm.doc.name }));
	},
});
