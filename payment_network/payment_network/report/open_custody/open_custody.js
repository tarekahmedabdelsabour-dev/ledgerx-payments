frappe.query_reports["Open Custody"] = {
	filters: [
		{
			fieldname: "supervisor",
			label: __("Supervisor"),
			fieldtype: "Link",
			options: "Payment Agent Profile",
		},
	],
};
