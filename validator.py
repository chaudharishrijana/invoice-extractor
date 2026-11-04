"""Checks that the extracted invoice numbers are internally consistent.

Validation is done in plain Python (not by the AI) so it independently
verifies what the model extracted.
"""
from models import Invoice

EXPECTED_VAT_RATE = 13.0  # percent
TOLERANCE = 0.01          # allowed rounding difference


def _items_sum(invoice: Invoice) -> float | None:
    """Sum of quantity x unit_price, or None if any item is incomplete."""
    if not invoice.items:
        return None
    total = 0.0
    for item in invoice.items:
        if item.quantity is None or item.unit_price is None:
            return None
        total += item.quantity * item.unit_price
    return total


def _compare(name: str, expected: float | None, actual: float | None, label: str) -> dict:
    """Compare two numbers and return a result record."""
    if expected is None or actual is None:
        return {
            "check": name,
            "status": "skipped",
            "message": f"Cannot check {label}: required data is missing.",
        }

    ok = abs(expected - actual) <= TOLERANCE
    return {
        "check": name,
        "status": "pass" if ok else "fail",
        "expected": round(expected, 2),
        "actual": round(actual, 2),
        "message": (
            f"{label} matches." if ok
            else f"{label} mismatch: expected {expected:,.2f}, found {actual:,.2f}."
        ),
    }


def validate(invoice: Invoice) -> dict:
    """Run all checks and return a summary."""
    items_total = _items_sum(invoice)

    expected_vat = (
        invoice.subtotal * EXPECTED_VAT_RATE / 100 if invoice.subtotal is not None else None
    )
    expected_total = (
        invoice.subtotal + invoice.vat_amount
        if invoice.subtotal is not None and invoice.vat_amount is not None
        else None
    )

    checks = [
        _compare("items_sum_vs_subtotal", items_total, invoice.subtotal,
                 "Sum of items (qty x unit price) vs subtotal"),
        _compare("vat_amount", expected_vat, invoice.vat_amount,
                 f"VAT amount ({EXPECTED_VAT_RATE:g}% of subtotal)"),
        _compare("subtotal_plus_vat_vs_total", expected_total, invoice.total_amount,
                 "Subtotal + VAT vs total amount"),
    ]

    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        status = "invalid"
    elif "skipped" in statuses:
        status = "incomplete"
    else:
        status = "valid"

    return {"status": status, "checks": checks}
