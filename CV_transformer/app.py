"""
app.py
Streamlit web app — upload a lawyer's CV (PDF or DOCX),
get back a client-facing Word profile in the Clario format.

Run locally:   streamlit run app.py
Deploy:        push to GitHub, connect to Streamlit Cloud (free tier)
"""
import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from extract import extract_text
from transform import transform_cv
from build_docx import build_docx

load_dotenv()

# ── page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Lawyer Profile Generator",
    page_icon="⚖️",
    layout="centered",
)

st.title("Lawyer Profile Generator")
st.caption(
    "Upload a lawyer's CV (PDF or Word) and download a clean client-facing profile document."
)

# ── API key: load from env silently, only prompt if absent ───────────────────

api_key = os.getenv("OPENAI_API_KEY", "")

with st.sidebar:
    st.header("Configuration")
    if not api_key:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Your key from platform.openai.com — never stored by this app.",
        )
        if not api_key:
            st.warning("Enter your API key to enable transformation.")

    st.divider()
    st.markdown(
        """
**How it works**
1. Upload any lawyer's CV
2. Click **Generate Profile**
3. Download the formatted Word document
4. Edit as needed before sending to the client

Supports PDF and DOCX input.
"""
    )

# ── main: file upload ────────────────────────────────────────────────────────

uploaded = st.file_uploader(
    "Upload CV",
    type=["pdf", "docx"],
    help="PDF or Word document — the full CV the lawyer provided.",
)

if uploaded:
    st.info(f"**{uploaded.name}** ({uploaded.size / 1024:.0f} KB)")

    if st.button("Generate Profile", type="primary", disabled=not api_key):

        # ── step 1: extract ──────────────────────────────────────────────

        with st.spinner("Extracting CV text…"):
            suffix = Path(uploaded.name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                cv_text = extract_text(tmp_path)
            except Exception as exc:
                st.error(f"Could not extract text from the file: {exc}")
                st.stop()
            finally:
                os.unlink(tmp_path)

        if not cv_text.strip():
            st.error("No text could be extracted from the file. Is it a scanned image PDF?")
            st.stop()

        # ── step 2: transform ────────────────────────────────────────────

        with st.spinner("Transforming with Claude…"):
            try:
                profile = transform_cv(cv_text, api_key)
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            except Exception as exc:
                st.error(f"Transformation failed: {exc}")
                st.stop()

        # ── step 3: build Word document ──────────────────────────────────

        with st.spinner("Building Word document…"):
            try:
                docx_bytes = build_docx(profile)
            except Exception as exc:
                st.error(f"Failed to build document: {exc}")
                st.stop()

        # ── result ───────────────────────────────────────────────────────

        name = profile.get("name", "Lawyer Profile")
        filename = f"{name} - Lawyer Profile.docx"

        st.success("Profile ready!")

        st.download_button(
            label="⬇️  Download Profile (.docx)",
            data=docx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

        # Optional: show the extracted structure for review
        with st.expander("Review extracted data (click to expand)"):
            st.json(profile)
