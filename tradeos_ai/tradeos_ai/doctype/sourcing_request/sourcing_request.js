frappe.ui.form.on("Sourcing Request", {
    refresh: function (frm) {
        if (frm.doc.status === "Approved" && !frm.doc.purchase_order) {
            frm.add_custom_button(__("Create Purchase Order Draft"), function () {
                frm.call({
                    method: "create_purchase_order",
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
