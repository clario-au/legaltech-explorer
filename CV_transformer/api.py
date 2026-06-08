"""
api.py
FastAPI endpoint — two routes:
  POST /convert       accepts a file upload (PDF or DOCX)
  POST /convert-text  accepts raw CV text as JSON (used by ChatGPT GPT Actions)
Both return a Clario-formatted Word document as a base64-encoded string.
"""
import base64
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class CVTextRequest(BaseModel):
    cv_text: str


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


@app.post("/convert-text")
def convert_text(request: CVTextRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured on server"}

    if not request.cv_text.strip():
        return {"error": "cv_text is empty"}

    try:
        profile = transform_cv(request.cv_text, api_key)
        docx_bytes = build_docx(profile)
        return {
            "filename": f"{profile.get('name', 'Lawyer Profile')} - Lawyer Profile.docx",
            "file_base64": base64.b64encode(docx_bytes).decode(),
            "name": profile.get("name", ""),
        }
    except Exception as exc:
        return {"error": str(exc)}
