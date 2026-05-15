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
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(path)
    parts = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            para = Paragraph(element, doc)
            text = para.text.strip()
            if text:
                parts.append(text)

        elif tag == "tbl":
            table = Table(element, doc)
            for row in table.rows:
                seen = []
                for cell in row.cells:
                    text = cell.text.strip()
                    if text and text not in seen:
                        seen.append(text)
                if seen:
                    parts.append(" | ".join(seen))

    return "\n".join(parts)
