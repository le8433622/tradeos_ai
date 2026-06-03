import frappe
from frappe.model.document import Document


class SupplierComparison(Document):
    def validate(self):
        if self.sourcing_request:
            sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
            if sr.status == "Converted":
                frappe.throw(
                    "Cannot create Supplier Comparison when Sourcing Request is already Converted."
                )

    def before_insert(self):
        if not self.generated_by:
            self.generated_by = frappe.session.user
        if not self.comparison_date:
            self.comparison_date = frappe.utils.now()

    def after_insert(self):
        if self.sourcing_request:
            sr = frappe.get_doc("Sourcing Request", self.sourcing_request)
            sr.add_comment(
                "Info",
                f"Supplier Comparison {self.name} generated. "
                f"Recommended: {self.recommended_supplier or 'N/A'}, "
                f"Saving: {self.expected_saving_percent or 0:.1f}%",
            )


@frappe.whitelist()
def generate_supplier_comparison(sourcing_request):
    sr = frappe.get_doc("Sourcing Request", sourcing_request)
    if sr.status == "Converted":
        frappe.throw("Cannot generate comparison for a Converted Sourcing Request.")

    quotes = frappe.get_all(
        "Supplier Quote",
        filters={"sourcing_request": sourcing_request, "docstatus": 0},
        order_by="creation",
    )
    if len(quotes) < 2:
        frappe.throw("At least 2 Supplier Quotes are required to generate a comparison.")

    rows_data = []
    for q in quotes:
        sq = frappe.get_doc("Supplier Quote", q.name)
        ev_stats = get_evidence_stats(q.name)
        rows_data.append(
            {
                "sq": sq,
                "ev_count": ev_stats["total"],
                "ev_verified": ev_stats["verified"],
            }
        )

    best_price = min(r["sq"].unit_price or 0 for r in rows_data)
    worst_price = max(r["sq"].unit_price or 0 for r in rows_data)
    min_lead = min(r["sq"].lead_time_days or 999 for r in rows_data)
    max_lead = max(r["sq"].lead_time_days or 0 for r in rows_data)
    min_risk = min(r["sq"].risk_score or 0 for r in rows_data)
    max_risk = max(r["sq"].risk_score or 0 for r in rows_data)
    max_verified = max(r["ev_verified"] for r in rows_data)

    for r in rows_data:
        sq = r["sq"]
        r["price_score"] = calculate_score(sq.unit_price, best_price, worst_price, higher_better=False)
        r["lead_time_score"] = calculate_score(
            sq.lead_time_days, min_lead, max_lead, higher_better=False
        )
        r["risk_score_normalized"] = calculate_score(
            sq.risk_score, min_risk, max_risk, higher_better=False
        )
        r["evidence_score"] = calculate_score(
            r["ev_verified"], 0, max_verified, higher_better=True, zero_guard=True
        )
        r["total_score"] = (
            r["price_score"] * 0.4
            + r["lead_time_score"] * 0.2
            + r["risk_score_normalized"] * 0.25
            + r["evidence_score"] * 0.15
        )

    rows_data.sort(key=lambda r: r["total_score"], reverse=True)
    for i, r in enumerate(rows_data, 1):
        r["ranking"] = i

    doc = frappe.new_doc("Supplier Comparison")
    doc.sourcing_request = sourcing_request
    doc.comparison_title = f"Comparison for {sourcing_request}"
    doc.baseline_price = sr.current_price or sr.target_price or 0
    doc.best_unit_price = best_price
    doc.expected_saving = (doc.baseline_price - best_price) if doc.baseline_price else 0
    doc.expected_saving_percent = (
        (doc.expected_saving / doc.baseline_price * 100) if doc.baseline_price else 0
    )
    doc.generated_by = frappe.session.user
    doc.comparison_date = frappe.utils.now()

    for r in rows_data:
        row = doc.append("comparison_rows", {})
        row.supplier_quote = r["sq"].name
        row.supplier = r["sq"].supplier
        row.unit_price = r["sq"].unit_price
        row.quantity = r["sq"].quantity
        row.moq = r["sq"].moq
        row.lead_time_days = r["sq"].lead_time_days
        row.risk_score = r["sq"].risk_score
        row.evidence_count = r["ev_count"]
        row.verified_evidence_count = r["ev_verified"]
        row.price_score = r["price_score"]
        row.lead_time_score = r["lead_time_score"]
        row.risk_score_normalized = r["risk_score_normalized"]
        row.evidence_score = r["evidence_score"]
        row.total_score = r["total_score"]
        row.ranking = r["ranking"]

    best_row = rows_data[0]
    doc.recommended_supplier_quote = best_row["sq"].name
    doc.recommended_supplier = best_row["sq"].supplier

    reasons = []
    if doc.expected_saving > 0:
        reasons.append(
            f"Expected saving of {doc.expected_saving:,.0f} ({doc.expected_saving_percent:.1f}%) "
            f"vs baseline of {doc.baseline_price:,.0f}"
        )
    if best_row["sq"].lead_time_days:
        reasons.append(f"Lead time of {best_row['sq'].lead_time_days} days")
    if best_row["sq"].risk_score is not None:
        reasons.append(f"Risk score of {best_row['sq'].risk_score}")
    reasons.append(f"Total scoring: {best_row['total_score']:.2f}/10")
    doc.recommendation_reason = ". ".join(reasons)

    risk_lines = []
    for r in rows_data:
        sq = r["sq"]
        if sq.risk_score and sq.risk_score >= 5:
            risk_lines.append(
                f"#{r['ranking']} {sq.supplier or sq.name}: risk score {sq.risk_score}"
            )
    doc.risk_summary = "\n".join(risk_lines) if risk_lines else "No significant risks identified"

    ev_lines = []
    for r in rows_data:
        sq = r["sq"]
        ev_lines.append(
            f"#{r['ranking']} {sq.supplier or sq.name}: "
            f"{r['ev_verified']} verified / {r['ev_count']} total evidence(s)"
        )
    doc.evidence_summary = "\n".join(ev_lines)

    doc.decision_status = "Ready for Approval"

    supersede_previous(sourcing_request)
    doc.insert()
    frappe.db.commit()

    return doc.name


def get_evidence_stats(supplier_quote):
    all_ev = frappe.get_all(
        "Quote Evidence",
        filters={"supplier_quote": supplier_quote},
        pluck="verification_status",
    )
    return {
        "total": len(all_ev),
        "verified": sum(1 for s in all_ev if s == "Verified"),
    }


def calculate_score(value, best, worst, higher_better=True, zero_guard=False):
    if value is None:
        return 1.0
    if zero_guard and worst == 0 and best == 0:
        return 1.0
    if worst == best:
        return 5.0
    if higher_better:
        return 1.0 + 9.0 * (value - best) / (worst - best)
    else:
        return 1.0 + 9.0 * (worst - value) / (worst - best)


def supersede_previous(sourcing_request):
    existing = frappe.get_all(
        "Supplier Comparison",
        filters={
            "sourcing_request": sourcing_request,
            "decision_status": "Ready for Approval",
        },
    )
    for e in existing:
        doc = frappe.get_doc("Supplier Comparison", e.name)
        doc.decision_status = "Superseded"
        doc.flags.ignore_permissions = True
        doc.save()