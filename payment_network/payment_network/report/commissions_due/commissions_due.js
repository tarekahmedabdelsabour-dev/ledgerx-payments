frappe.query_reports["Commissions Due"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "role_type",
			label: __("Role Type"),
			fieldtype: "Select",
			options: "\nAgent\nSupervisor\nManager",
		},
	],
};
