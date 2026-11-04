import pytest

from extractor import ExtractionError, load_image, parse_model_output

VALID_JSON = '{"invoice_number": "RT-2024-1052", "total_amount": 113565, "items": []}'


def test_parses_plain_json():
    invoice = parse_model_output(VALID_JSON)
    assert invoice.invoice_number == "RT-2024-1052"
    assert invoice.supplier_name is None  # missing field -> None


def test_parses_json_wrapped_in_fences():
    invoice = parse_model_output(f"```json\n{VALID_JSON}\n```")
    assert invoice.total_amount == 113565


def test_invalid_json_raises():
    with pytest.raises(ExtractionError):
        parse_model_output('{"invoice_number": ')


def test_no_json_raises():
    with pytest.raises(ExtractionError):
        parse_model_output("Sorry, I cannot read this image.")


def test_not_an_invoice_raises():
    with pytest.raises(ExtractionError, match="not_an_invoice"):
        parse_model_output('{"error": "not_an_invoice"}')


def test_missing_file_raises():
    with pytest.raises(ExtractionError, match="File not found"):
        load_image("does_not_exist.png")


def test_non_image_file_raises(tmp_path):
    fake = tmp_path / "fake.png"
    fake.write_text("this is not an image")
    with pytest.raises(ExtractionError, match="Unreadable"):
        load_image(str(fake))
