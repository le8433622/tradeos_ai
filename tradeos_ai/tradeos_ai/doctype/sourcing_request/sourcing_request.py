import frappe
from frappe.model.document import Document


class SourcingRequest(Document):
    def validate(self):
        if self.status == "Approved" and not self.approved_by:
            frappe.throw("Approved By is required before setting status to Approved.")

    def before_update_after_submit(self):
        if self.status == "Approved" and not self.approved_at:
            self.approved_at = frappe.utils.now()

    def before_submit(self):
        if self.status in ("Draft", "Pending"):
            self.status = "Sourcing"

    def on_update_after_submit(self):
        if self.status == "Converted" and not self.purchase_order:
            frappe.throw("Purchase Order must be linked before converting.")

    @frappe.whitelist()
    def create_purchase_order(self):
        if self.status != "Approved":
            frappe.throw("Sourcing Request must be in Approved status to create Purchase Order.")
        if not self.approved_by or not self.approved_at:
            frappe.throw("Approved By and Approved At are required.")
        if self.purchase_order:
            frappe.throw("Purchase Order already exists for this Sourcing Request.")

        item_code = frappe.db.get_value("Item", {"item_name": self.item_description}, "name")
        if not item_code:
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": self.item_description,
                "item_name": self.item_description,
                "item_type": "Stock",
                "item_group": "All Item Groups",
                "stock_uom": self.uom or "Nos"
            })
            item.flags.ignore_permissions = True
            item.insert()
            item_code = item.name

        po = frappe.new_doc("Purchase Order")
        po.company = self.company
        po.supplier = self.current_supplier
        po.schedule_date = self.required_date
        po.conversion_rate = 1
        po.plc_conversion_rate = 1
        po.buying_price_list = "Standard Buying"
        po.set_warehouse = "Stores - TC"

        item_row = po.append("items", {})
        item_row.item_code = item_code
        item_row.item_name = self.item_description
        item_row.description = self.item_description
        item_row.qty = self.quantity or 1
        item_row.uom = self.uom or "Nos"
        item_row.rate = self.target_price or 0
        item_row.conversion_factor = 1

        po.flags.ignore_permissions = True
        po.insert()

        self.purchase_order = po.name
        self.status = "Converted"
        self.flags.ignore_validate = True
        self.flags.ignore_mandatory = True
        self.save()

        frappe.msgprint(f"Purchase Order {po.name} created successfully.")
