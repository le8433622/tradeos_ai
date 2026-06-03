import frappe
from frappe.model.document import Document


class SupplierQuote(Document):
    def validate(self):
        sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
        if sr.status == "Converted":
            frappe.throw(
                "Cannot create or modify Supplier Quote when the Sourcing Request is already Converted."
            )

    @frappe.whitelist()
    def select_supplier_quote(self):
        sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
        if sr.status == "Converted":
            frappe.throw("Cannot select a quote for an already Converted Sourcing Request.")

        self.quote_status = "Selected"
        self.save()

        other_quotes = frappe.get_all(
            "Supplier Quote",
            filters={"sourcing_request": self.sourcing_request, "name": ["!=", self.name]},
        )
        for q in other_quotes:
            doc = frappe.get_doc("Supplier Quote", q.name)
            doc.quote_status = "Rejected"
            doc.save()

        sr.db_set("current_supplier", self.supplier)
        sr.db_set("current_price", self.unit_price)
        if sr.status not in ("Approved", "Converted"):
            sr.db_set("status", "Waiting Approval")

        sr.add_comment(
            "Info",
            f"Supplier Quote {self.name} selected. "
            f"Supplier: {self.supplier or self.supplier_name}, "
            f"Price: {self.unit_price}",
        )

        frappe.msgprint(f"Supplier Quote {self.name} selected successfully.")