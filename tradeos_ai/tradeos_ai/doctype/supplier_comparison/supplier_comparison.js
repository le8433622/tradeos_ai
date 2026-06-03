frappe.ui.form.on("Supplier Comparison", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.decision_status === "Ready for Approval") {
        }
    },

    sourcing_request: function (frm) {
        if (frm.doc.sourcing_request) {
            frappe.db.get_value("Sourcing Request", frm.doc.sourcing_request, ["current_price", "target_price"], function (r) {
                if (r && frm.doc.__islocal) {
                    frm.set_value("baseline_price", r.current_price || r.target_price || 0);
                }
            });
        }
    },
});