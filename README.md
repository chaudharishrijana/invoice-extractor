# Invoice Data Extractor

A small Python app that reads an invoice image, extracts the key data with an
AI vision model (Google Gemini), validates the numbers, and outputs structured JSON.

## Features

- Extracts invoice number, date, supplier, line items, subtotal, VAT and total
- Validates: sum of items = subtotal, VAT = 13% of subtotal, subtotal + VAT = total
- Prints JSON to the console and saves it to `output.json`
- Handles errors gracefully: missing file, unreadable image, API failure,
  invalid model output, missing fields (returned as `null`)
- Retries automatically on temporary API errors (503 / rate limit)

## Setup

Requires Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate          # Windows Git Bash: source venv/Scripts/activate
python -m pip install -r requirements.txt
```

Get a free API key at https://aistudio.google.com ("Get API key") and set it as
an environment variable. The key is never stored in the code.

```bash
export GEMINI_API_KEY="your-key-here"       # PowerShell: $env:GEMINI_API_KEY="your-key-here"
```

Optional: choose another model with `GEMINI_MODEL` (default: `gemini-3.1-flash-lite`).

## Run

```bash
python main.py invoice.png
python main.py invoice.png --output result.json
```

## Run tests

The tests do not call the API.

```bash
python -m pytest
```

## Files

- `main.py`: command-line entry point, prints and saves the JSON
- `extractor.py`: loads the image, calls Gemini, parses the response, retries
- `validator.py`: arithmetic checks on the extracted data
- `models.py`: Pydantic schema for the invoice
- `tests/`: pytest tests for validation and parsing

## Notes

- The prompt tells the model to copy numbers exactly and never calculate.
  Validation runs separately in Python, so mistakes in an invoice are caught
  instead of being silently "fixed" by the AI.
- Missing fields become `null`. Validation status is `valid`, `invalid`
  (a check failed) or `incomplete` (a check was skipped because data was missing).
- Limits: PNG, JPEG, GIF or WEBP images up to 5 MB; VAT rate is fixed at 13%.

## Example output (from `invoice.png`)

```json
{
  "invoice": {
    "invoice_number": "RT-2024-1052",
    "invoice_date": "2024-10-14",
    "supplier_name": "RIVERTECH SUPPLIES LTD.",
    "currency": "NPR",
    "items": [
      {
        "description": "HDPE Pipe 110mm (6m length)",
        "quantity": 50.0,
        "unit": "pcs",
        "unit_price": 1250.0
      },
      {
        "description": "HDPE Elbow 90° 110mm",
        "quantity": 20.0,
        "unit": "pcs",
        "unit_price": 450.0
      },
      {
        "description": "HDPE Coupling 110mm",
        "quantity": 30.0,
        "unit": "pcs",
        "unit_price": 300.0
      },
      {
        "description": "Welding Service",
        "quantity": 10.0,
        "unit": "hrs",
        "unit_price": 1500.0
      },
      {
        "description": "Delivery Charge",
        "quantity": 1.0,
        "unit": "lot",
        "unit_price": 5000.0
      }
    ],
    "subtotal": 100500.0,
    "vat_rate_percent": 13.0,
    "vat_amount": 13065.0,
    "total_amount": 113565.0
  },
  "validation": {
    "status": "valid",
    "checks": [
      {
        "check": "items_sum_vs_subtotal",
        "status": "pass",
        "expected": 100500.0,
        "actual": 100500.0,
        "message": "Sum of items (qty x unit price) vs subtotal matches."
      },
      {
        "check": "vat_amount",
        "status": "pass",
        "expected": 13065.0,
        "actual": 13065.0,
        "message": "VAT amount (13% of subtotal) matches."
      },
      {
        "check": "subtotal_plus_vat_vs_total",
        "status": "pass",
        "expected": 113565.0,
        "actual": 113565.0,
        "message": "Subtotal + VAT vs total amount matches."
      }
    ]
  },
  "error": null
}
```
# invoice-extractor
