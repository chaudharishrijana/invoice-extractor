from models import Invoice, Item
from validator import validate


def make_invoice(**overrides) -> Invoice:
    """A correct invoice matching the sample from the assignment."""
    data = dict(
        invoice_number="RT-2024-1052",
        invoice_date="2024-10-14",
        supplier_name="Rivertech Supplies Ltd.",
        currency="NPR",
        items=[
            Item(description="HDPE Pipe 110mm (6m length)", quantity=50, unit="pcs", unit_price=1250),
            Item(description="HDPE Elbow 90 degree 110mm", quantity=20, unit="pcs", unit_price=450),
            Item(description="HDPE Coupling 110mm", quantity=30, unit="pcs", unit_price=300),
            Item(description="Welding Service", quantity=10, unit="hrs", unit_price=1500),
            Item(description="Delivery Charge", quantity=1, unit="lot", unit_price=5000),
        ],
        subtotal=100500,
        vat_rate_percent=13,
        vat_amount=13065,
        total_amount=113565,
    )
    data.update(overrides)
    return Invoice(**data)


def test_correct_invoice_is_valid():
    result = validate(make_invoice())
    assert result["status"] == "valid"
    assert all(c["status"] == "pass" for c in result["checks"])


def test_wrong_total_is_detected():
    result = validate(make_invoice(total_amount=120000))
    assert result["status"] == "invalid"
    failed = [c for c in result["checks"] if c["status"] == "fail"]
    assert failed[0]["check"] == "subtotal_plus_vat_vs_total"


def test_wrong_vat_is_detected():
    result = validate(make_invoice(vat_amount=10000))
    assert result["status"] == "invalid"


def test_items_not_matching_subtotal_is_detected():
    result = validate(make_invoice(subtotal=99999))
    assert result["checks"][0]["status"] == "fail"


def test_missing_subtotal_is_incomplete_not_crash():
    result = validate(make_invoice(subtotal=None))
    assert result["status"] == "incomplete"
    assert result["checks"][0]["status"] == "skipped"


def test_no_items_is_handled():
    result = validate(make_invoice(items=[]))
    assert result["checks"][0]["status"] == "skipped"
