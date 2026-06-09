"""
api.py
FastAPI endpoint — routes:
  POST /convert-text  accepts raw CV text as JSON (used by ChatGPT GPT Actions)
  POST /convert       accepts a file upload (PDF or DOCX)
  GET  /download/{id} serves the generated DOCX for one download
  GET  /health        liveness check
"""
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from build_docx import build_docx
from extract import extract_text
from transform import transform_cv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://cv-transformer.onrender.com")

app = FastAPI(title="Clario CV Transformer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# In-memory store: {file_id: (docx_bytes, filename)}
# Files are deleted after the first download.
_pending: dict[str, tuple[bytes, str]] = {}


class CVTextRequest(BaseModel):
    cv_text: str


def _store_and_url(docx_bytes: bytes, filename: str) -> str:
    file_id = str(uuid.uuid4())
    _pending[file_id] = (docx_bytes, filename)
    return f"{BASE_URL}/download/{file_id}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/download/{file_id}")
def download(file_id: str):
    entry = _pending.pop(file_id, None)
    if entry is None:
        return Response(status_code=404, content="File not found or already downloaded")
    docx_bytes, filename = entry
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        filename = f"{profile.get('name', 'Lawyer Profile')} - Lawyer Profile.docx"
        return {
            "download_url": _store_and_url(docx_bytes, filename),
            "filename": filename,
            "name": profile.get("name", ""),
        }
    except Exception as exc:
        return {"error": str(exc)}


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
        filename = f"{profile.get('name', 'Lawyer Profile')} - Lawyer Profile.docx"
        return {
            "download_url": _store_and_url(docx_bytes, filename),
            "filename": filename,
            "name": profile.get("name", ""),
        }
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        os.unlink(tmp_path)
