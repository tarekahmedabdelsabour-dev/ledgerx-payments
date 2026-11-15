frappe.query_reports["Transactions Today"] = {
	filters: [
		{
			fieldname: "date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "agent",
			label: __("Agent"),
			fieldtype: "Link",
			options: "Payment Agent Profile",
		},
		{
			fieldname: "service",
			label: __("Service"),
			fieldtype: "Link",
			options: "Payment Service",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPending\nProcessing\nSuccess\nFailed\nReversed",
		},
	],
};
