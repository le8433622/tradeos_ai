frappe.ui.form.on("Quote Evidence", {
    supplier_quote: function (frm) {
        if (frm.doc.supplier_quote) {
            frappe.db.get_value("Supplier Quote", frm.doc.supplier_quote, ["sourcing_request", "supplier"], function (r) {
                if (r) {
                    if (r.sourcing_request) frm.set_value("sourcing_request", r.sourcing_request);
                    if (r.supplier) frm.set_value("supplier", r.supplier);
                }
            });
        }
    },
});