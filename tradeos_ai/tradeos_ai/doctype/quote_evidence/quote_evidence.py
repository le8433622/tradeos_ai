import frappe
from frappe.model.document import Document


class QuoteEvidence(Document):
    def validate(self):
        if self.supplier_quote:
            sq = frappe.get_doc("Supplier Quote", self.supplier_quote)
            if not self.sourcing_request:
                self.sourcing_request = sq.sourcing_request
            if not self.supplier:
                self.supplier = sq.supplier

        if self.sourcing_request:
            sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
            if sr.status == "Converted" and not self.has_system_manager_role():
                frappe.throw(
                    "Cannot modify Quote Evidence when Sourcing Request is Converted. "
                    "Contact System Manager if audit changes are needed."
                )

    def before_insert(self):
        if not self.captured_at:
            self.captured_at = frappe.utils.now()
        if not self.captured_by:
            self.captured_by = frappe.session.user

    def after_insert(self):
        msg = f"Quote Evidence added: {self.evidence_title}"
        if self.supplier_quote:
            sq = frappe.get_doc("Supplier Quote", self.supplier_quote)
            sq.add_comment("Info", msg)
        if self.sourcing_request:
            sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
            sr.add_comment("Info", msg)

    def has_system_manager_role(self):
        user_roles = frappe.get_roles(frappe.session.user)
        return "System Manager" in user_roles