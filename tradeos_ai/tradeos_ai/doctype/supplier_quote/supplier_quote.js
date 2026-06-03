frappe.ui.form.on("Supplier Quote", {
    refresh: function (frm) {
        if (frm.doc.quote_status !== "Selected" && frm.doc.quote_status !== "Rejected") {
            frm.add_custom_button(__("Select This Quote"), function () {
                frm.call({
                    method: "select_supplier_quote",
                    doc: frm.doc,
                    callback: function (r) {
                        if (!r.exc) {
                            frm.refresh();
                        }
                    },
                });
            });
        }
    },
});