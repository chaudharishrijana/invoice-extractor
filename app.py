"""Streamlit web interface for the invoice extractor


"""
import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime
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

# On Streamlit Cloud the key comes from Secrets; locally from the environment.
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

MAX_HISTORY = 10  # keep only the latest invoices per visitor

st.session_state.setdefault("history", [])
st.session_state.setdefault("selected", None)
st.session_state.setdefault("last_key", None)
st.session_state.setdefault("error", None)


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


def add_to_history(name: str, image: bytes, result: dict) -> None:
    entry = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "time": datetime.now().strftime("%H:%M:%S"),
        "image": image,
        "result": result,
    }
    history = st.session_state["history"]
    history.insert(0, entry)
    del history[MAX_HISTORY:]
    st.session_state["selected"] = entry["id"]


def render(entry: dict) -> None:
    """Show one extraction result."""
    invoice, validation = entry["result"]["invoice"], entry["result"]["validation"]
    left, right = st.columns(2)

    with left:
        st.subheader("Invoice image")
        st.image(entry["image"])

    with right:
        st.subheader("Extracted data")
        st.write(f"**Invoice number:** {invoice['invoice_number']}")
        st.write(f"**Invoice date:** {invoice['invoice_date']}")
        st.write(f"**Supplier:** {invoice['supplier_name']}")
        st.write(f"**Currency:** {invoice['currency']}")
        st.dataframe(invoice["items"], hide_index=True)

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

    json_text = json.dumps(entry["result"], indent=2, ensure_ascii=False)
    with st.expander("Raw JSON"):
        st.code(json_text, language="json")
    st.download_button(
        "Download JSON",
        json_text,
        file_name="output.json",
        mime="application/json",
        key=f"download_{entry['id']}",
    )


# Main area: upload and extract
st.title("Invoice Data Extractor")
st.write(
    "Upload an invoice image. The app reads it with the Google Gemini API, "
    "extracts the key fields, checks the totals and VAT, and returns JSON."
)

uploaded = st.file_uploader("Invoice image", type=["png", "jpg", "jpeg", "webp", "gif"])
sample_path = Path(__file__).parent / "invoice.png"
use_sample = sample_path.exists() and st.button("Try with the sample invoice")

job = None
if uploaded is not None:
    data = uploaded.getvalue()
    key = hashlib.md5(data).hexdigest()
    if key != st.session_state["last_key"]:  # process each new upload only once
        job = (uploaded.name, data, Path(uploaded.name).suffix or ".png")
        st.session_state["last_key"] = key
else:
    st.session_state["last_key"] = None  # uploader emptied: allow the same file again
if use_sample:
    job = ("invoice.png (sample)", sample_path.read_bytes(), ".png")

if job:
    name, data, suffix = job
    with st.spinner("Reading the invoice..."):
        try:
            add_to_history(name, data, run_extraction(data, suffix))
            st.session_state["error"] = None
        except ExtractionError as exc:
            st.session_state["error"] = str(exc)

#  Sidebar: history
with st.sidebar:
    st.header("History")
    st.caption("Only you can see this. Refreshing the page clears it.")
    if not st.session_state["history"]:
        st.write("No invoices yet.")
    for entry in list(st.session_state["history"]):
        status = entry["result"]["validation"]["status"]
        st.write(f"**{entry['name']}**  \n{entry['time']} - {status}")
        col_view, col_del = st.columns(2)
        if col_view.button("View", key=f"view_{entry['id']}"):
            st.session_state["selected"] = entry["id"]
            st.session_state["error"] = None
        if col_del.button("Delete", key=f"delete_{entry['id']}"):
            st.session_state["history"] = [
                e for e in st.session_state["history"] if e["id"] != entry["id"]
            ]
            if st.session_state["selected"] == entry["id"]:
                st.session_state["selected"] = None
            st.session_state["error"] = None
            st.rerun()
        st.divider()
    if st.session_state["history"] and st.button("Clear all history"):
        st.session_state["history"] = []
        st.session_state["selected"] = None
        st.session_state["error"] = None
        st.rerun()

#  Results 
if st.session_state["error"]:
    st.error(st.session_state["error"])

history = st.session_state["history"]
current = next((e for e in history if e["id"] == st.session_state["selected"]), None)
if current is None and history:
    current = history[0]
if current is not None:
    render(current)
