frappe.query_reports["Wallet Balances"] = {
	filters: [
		{
			fieldname: "role_type",
			label: __("Role Type"),
			fieldtype: "Select",
			options: "\nAgent\nSupervisor\nManager",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
	],
};
