"""
api.py
FastAPI endpoint — accepts a CV file upload, returns a Clario-formatted
Word document as a base64-encoded string for use with ChatGPT GPT Actions.
"""
import base64
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from build_docx import build_docx
from extract import extract_text
from transform import transform_cv

load_dotenv()

app = FastAPI(title="Clario CV Transformer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured on server"}

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        return {"error": f"Unsupported file type: {suffix}. Upload a PDF or DOCX."}

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = extract_text(tmp_path)
        if not text.strip():
            return {"error": "No text could be extracted. Is it a scanned PDF?"}

        profile = transform_cv(text, api_key)
        docx_bytes = build_docx(profile)

        return {
            "filename": f"{profile.get('name', 'Lawyer Profile')} - Lawyer Profile.docx",
            "file_base64": base64.b64encode(docx_bytes).decode(),
            "name": profile.get("name", ""),
        }
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        os.unlink(tmp_path)
