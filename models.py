"""Pydantic schema for the extracted invoice data.

Every field is optional so a missing value becomes `null` in the JSON
instead of crashing the program.
"""
from pydantic import BaseModel, Field


class Item(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None


class Invoice(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None  # ISO format: YYYY-MM-DD
    supplier_name: str | None = None
    currency: str | None = None
    items: list[Item] = Field(default_factory=list)
    subtotal: float | None = None
    vat_rate_percent: float | None = None
    vat_amount: float | None = None
    total_amount: float | None = None
