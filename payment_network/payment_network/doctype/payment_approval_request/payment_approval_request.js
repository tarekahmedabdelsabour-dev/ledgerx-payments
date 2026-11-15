frappe.ui.form.on("Payment Approval Request", {
	refresh(frm) {
		if (frm.doc.status !== "Pending") return;
		const act = (method, title) => () => frappe.prompt({ fieldname: "note", fieldtype: "Small Text", label: __("Decision Note") }, (v) => {
			frm.call(method, { note: v.note }).then(() => frm.reload_doc());
		}, title);
		frm.add_custom_button(__("Approve"), act("approve", __("Approve")), __("Decision"));
		frm.add_custom_button(__("Reject"), act("reject", __("Reject")), __("Decision"));
		if (frm.doc.transaction) frm.add_custom_button(__("Transaction"), () => frappe.set_route("Form", "Payment Transaction", frm.doc.transaction));
	},
});
