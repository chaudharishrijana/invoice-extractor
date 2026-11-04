"""CLI entry point: python main.py invoice.png"""
import argparse
import json
import sys

from extractor import ExtractionError, extract_invoice
from validator import validate


def emit(result: dict, output_path: str) -> None:
    """Print the result as JSON and save it to a file."""
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError as exc:
        print(f"Warning: could not write {output_path}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract structured data from an invoice image.")
    parser.add_argument("image", help="Path to the invoice image (PNG, JPEG, GIF or WEBP)")
    parser.add_argument("-o", "--output", default="output.json", help="Output JSON file (default: output.json)")
    args = parser.parse_args(argv)

    try:
        invoice = extract_invoice(args.image)
    except ExtractionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        emit({"invoice": None, "validation": None, "error": str(exc)}, args.output)
        return 1

    result = {
        "invoice": invoice.model_dump(),
        "validation": validate(invoice),
        "error": None,
    }
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
