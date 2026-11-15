frappe.ui.form.on("Cash Settlement", {
	from_profile(frm) { frm.trigger("load_custody"); },
	load_custody(frm) {
		if (!frm.doc.from_profile) return;
		frappe.db.get_value("Agent Wallet", { profile: frm.doc.from_profile }, ["custody_balance", "commission_balance"]).then((r) => {
			const v = r.message || {};
			frm.set_value("custody_before", v.custody_balance || 0);
			if (!frm.doc.amount_due) frm.set_value("amount_due", v.custody_balance || 0);
			frm.dashboard.set_headline(__("Cash held: {0} | Commission earned: {1}", [v.custody_balance || 0, v.commission_balance || 0]));
		});
	},
	refresh(frm) { if (frm.doc.docstatus === 0) frm.trigger("load_custody"); },
	amount_due(frm) { frm.trigger("calc"); }, commission_offset(frm) { frm.trigger("calc"); }, amount_handed(frm) { frm.trigger("calc"); },
	calc(frm) {
		const d = flt(frm.doc.amount_due) - flt(frm.doc.commission_offset) - flt(frm.doc.amount_handed);
		frm.set_value("difference", Math.round(d * 100) / 100);
	},
});
