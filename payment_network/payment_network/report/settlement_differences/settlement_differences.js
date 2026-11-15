frappe.query_reports["Settlement Differences"] = {
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
			fieldname: "stage",
			label: __("Stage"),
			fieldtype: "Select",
			options: "\nAgent to Supervisor\nSupervisor to Manager",
		},
		{
			fieldname: "from_profile",
			label: __("Handed By"),
			fieldtype: "Link",
			options: "Payment Agent Profile",
		},
	],
};
