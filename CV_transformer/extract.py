"""
extract.py
Extract plain text from a PDF or DOCX CV file for passing to the AI transformation step.
"""
from pathlib import Path


def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}. Please upload a PDF or DOCX file.")


def _extract_pdf(path: str) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if text:
                pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_docx(path: str) -> str:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    parts = []

    # iter() does a full depth-first walk of the XML tree, capturing text from
    # regular paragraphs, table cells, text boxes, and SDT content controls alike.
    for p_el in doc.element.body.iter(qn("w:p")):
        texts = [t.text for t in p_el.iter(qn("w:t")) if t.text]
        line = "".join(texts).strip()
        if line:
            parts.append(line)

    return "\n".join(parts)
