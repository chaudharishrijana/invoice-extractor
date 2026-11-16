
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from extractor import (
    ExtractionError,
    call_gemini_with_retry,
    load_image,
    parse_model_output,
)
from validator import validate

st.set_page_config(page_title="Invoice Data Extractor", layout="wide")


try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass


def run_extraction(data: bytes, suffix: str) -> dict:
    """Same pipeline as the command-line app: load -> AI -> parse -> validate."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        media_type, image_bytes = load_image(path)
        raw_text = call_gemini_with_retry(media_type, image_bytes)
        invoice = parse_model_output(raw_text)
    finally:
        Path(path).unlink(missing_ok=True)
    return {
        "invoice": invoice.model_dump(),
        "validation": validate(invoice),
        "error": None,
    }


st.title("Invoice Data Extractor")
st.caption("Key loaded: " + str(bool(os.environ.get("GEMINI_API_KEY"))))
st.write(
    "Upload an invoice image. The app reads it with the Google Gemini API, "
    "extracts the key fields, checks the totals and VAT, and returns JSON."
)

uploaded = st.file_uploader("Invoice image", type=["png", "jpg", "jpeg", "webp", "gif"])
sample_path = Path(__file__).parent / "invoice.png"
use_sample = sample_path.exists() and st.button("Try with the sample invoice")

image_bytes, suffix = None, ".png"
if uploaded is not None:
    image_bytes, suffix = uploaded.getvalue(), Path(uploaded.name).suffix or ".png"
elif use_sample:
    image_bytes = sample_path.read_bytes()

if image_bytes is not None:
    with st.spinner("Reading the invoice..."):
        try:
            st.session_state["result"] = run_extraction(image_bytes, suffix)
            st.session_state["image"] = image_bytes
            st.session_state["error"] = None
        except ExtractionError as exc:
            st.session_state["result"] = None
            st.session_state["error"] = str(exc)

if st.session_state.get("error"):
    st.error(st.session_state["error"])

result = st.session_state.get("result")
if result:
    invoice, validation = result["invoice"], result["validation"]
    left, right = st.columns(2)

    with left:
        st.subheader("Invoice image")
        st.image(st.session_state["image"], use_container_width=True)

    with right:
        st.subheader("Extracted data")
        st.write(f"**Invoice number:** {invoice['invoice_number']}")
        st.write(f"**Invoice date:** {invoice['invoice_date']}")
        st.write(f"**Supplier:** {invoice['supplier_name']}")
        st.write(f"**Currency:** {invoice['currency']}")
        st.dataframe(invoice["items"], hide_index=True, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal", invoice["subtotal"])
        c2.metric("VAT", invoice["vat_amount"])
        c3.metric("Total", invoice["total_amount"])

        st.subheader("Validation")
        status = validation["status"]
        if status == "valid":
            st.success("All checks passed.")
        elif status == "invalid":
            st.error("Some checks failed.")
        else:
            st.warning("Some checks were skipped because data is missing.")
        for check in validation["checks"]:
            line = f"{check['check']}: {check['message']}"
            if check["status"] == "pass":
                st.success(line)
            elif check["status"] == "fail":
                st.error(line)
            else:
                st.warning(line)

    json_text = json.dumps(result, indent=2, ensure_ascii=False)
    with st.expander("Raw JSON"):
        st.code(json_text, language="json")
    st.download_button("Download JSON", json_text, file_name="output.json", mime="application/json")
