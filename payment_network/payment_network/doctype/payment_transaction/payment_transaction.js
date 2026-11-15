frappe.ui.form.on("Payment Transaction", {
	refresh(frm) {
		frm.disable_save();
		if (frm.doc.status === "Success" && frappe.user_roles.includes("Payment Manager")) {
			frm.add_custom_button(__("Reverse Transaction"), () => {
				frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }, (v) => {
					frm.call("reverse", { reason: v.reason }).then(() => frm.reload_doc());
				}, __("Reverse Transaction"));
			});
		}
		["journal_entry", "payment_entry"].forEach((f) => { if (frm.doc[f]) frm.add_custom_button(frm.doc[f], () => frappe.set_route("Form", frm.fields_dict[f].df.options, frm.doc[f]), __("Open")); });
	},
});
