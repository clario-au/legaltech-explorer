"""
build_docx.py
Fill the Clario template Word document with new lawyer profile data.

Strategy: open 'Julie Marcus - Lawyer Profile.docx' as a template and replace
content in-place. This guarantees exact formatting (borders, shading, column
widths, fonts, bullet list style, footer logo) without re-implementing any of it.
"""

import copy
import io
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table

TEMPLATE = Path(__file__).parent / "Julie Marcus - Lawyer Profile.docx"
NAVY = "243C66"
WHITE = "FFFFFF"

# numId / ilvl for the bullet list — sourced from the template
BULLET_NUM_ID = "2"
BULLET_ILVL = "0"


# ── low-level XML helpers ────────────────────────────────────────────────────

def _make_run(text: str, *, bold: bool = False, italic: bool = False,
              pt: int | None = None, color: str = NAVY) -> OxmlElement:
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Montserrat")
    fonts.set(qn("w:hAnsi"), "Montserrat")
    rPr.append(fonts)

    if bold:
        rPr.append(OxmlElement("w:b"))
        rPr.append(OxmlElement("w:bCs"))
    if italic:
        rPr.append(OxmlElement("w:i"))
        rPr.append(OxmlElement("w:iCs"))
    if pt is not None:
        for tag in ("w:sz", "w:szCs"):
            el = OxmlElement(tag)
            el.set(qn("w:val"), str(pt * 2))
            rPr.append(el)

    col = OxmlElement("w:color")
    col.set(qn("w:val"), color)
    rPr.append(col)

    r.append(rPr)

    t = OxmlElement("w:t")
    t.text = text
    if text != text.strip():
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


def _bullet_pPr() -> OxmlElement:
    """Return a fresh pPr element matching the template's bullet list style."""
    pPr = OxmlElement("w:pPr")

    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), BULLET_ILVL)
    numId = OxmlElement("w:numId")
    numId.set(qn("w:val"), BULLET_NUM_ID)
    numPr.append(ilvl)
    numPr.append(numId)
    pPr.append(numPr)

    snap = OxmlElement("w:snapToGrid")
    snap.set(qn("w:val"), "0")
    pPr.append(snap)

    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:line"), "276")
    spacing.set(qn("w:lineRule"), "auto")
    pPr.append(spacing)

    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "320")
    ind.set(qn("w:hanging"), "357")
    pPr.append(ind)

    pPr.append(OxmlElement("w:contextualSpacing"))
    return pPr


def _make_bullet_para(text: str) -> OxmlElement:
    """
    Create a bulleted paragraph.
    Handles '**Bold Lead**: rest of sentence' pattern.
    """
    p = OxmlElement("w:p")
    p.append(_bullet_pPr())

    match = re.match(r"\*\*(.+?)\*\*:?\s*(.*)", text, re.DOTALL)
    if match:
        lead = match.group(1).strip() + ":"
        rest = match.group(2).strip()
        p.append(_make_run(lead, bold=True, pt=10))
        if rest:
            p.append(_make_run(" " + rest, pt=10))
    else:
        p.append(_make_run(text, pt=10))

    return p


# ── cell-level helpers ───────────────────────────────────────────────────────

def _set_cell(cell, text: str, *, bold: bool = False, italic: bool = False,
              pt: int | None = None, color: str = NAVY):
    """
    Replace a cell's text content with a single paragraph.
    Preserves existing pPr (alignment, borders, spacing) — only runs are replaced.
    """
    tc = cell._tc
    # Keep only the first paragraph, remove the rest
    paras = tc.findall(qn("w:p"))
    for p in paras[1:]:
        tc.remove(p)
    p = paras[0]
    # Remove all existing runs (pPr survives)
    for r in p.findall(qn("w:r")):
        p.remove(r)
    p.append(_make_run(text, bold=bold, italic=italic, pt=pt, color=color))


def _set_desc_cell(cell, description: str):
    """
    Replace a description cell with one bulleted paragraph per sentence.
    Handles '**Bold**: rest' pattern within sentences.
    """
    sentences = [s.strip() for s in description.split("\n") if s.strip()]
    tc = cell._tc
    for old_p in list(tc.findall(qn("w:p"))):
        tc.remove(old_p)
    for sentence in sentences:
        tc.append(_make_bullet_para(sentence))


# ── table-level fillers ──────────────────────────────────────────────────────

def _fill_name(tbl, name: str):
    _set_cell(tbl.cell(1, 0), name, bold=True, pt=36, color=WHITE)


def _fill_first_exp(tbl, exp: dict):
    # Row 0: "Experience" label — unchanged
    # Row 1: date (full-width merged)
    _set_cell(tbl.cell(1, 0), exp["dates"], bold=True)
    # Row 2: company | role
    _set_cell(tbl.cell(2, 0), exp["company"], bold=True, pt=11)
    _set_cell(tbl.cell(2, 1), exp["role"], italic=True, pt=11)
    # Row 3: description (full-width merged)
    _set_desc_cell(tbl.cell(3, 0), exp["description"])


def _fill_exp(tbl, exp: dict):
    # Row 0: date (full-width merged)
    _set_cell(tbl.cell(0, 0), exp["dates"], bold=True)
    # Row 1: company | role
    _set_cell(tbl.cell(1, 0), exp["company"], bold=True, pt=11)
    _set_cell(tbl.cell(1, 1), exp["role"], italic=True, pt=11)
    # Row 2: description (full-width merged)
    _set_desc_cell(tbl.cell(2, 0), exp["description"])


def _fill_prior_exp(tbl, text: str):
    _set_cell(tbl.cell(1, 0), text, pt=10)


def _fill_education(tbl, education: list[dict]):
    # Row 0: "Education" header — unchanged
    # Add rows if needed (clone last data row)
    while len(tbl.rows) - 1 < len(education):
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
    # Remove surplus rows
    while len(tbl.rows) - 1 > len(education):
        tbl._tbl.remove(tbl.rows[-1]._tr)
    # Fill
    for i, edu in enumerate(education):
        _set_cell(tbl.cell(i + 1, 0), edu.get("institution", ""), pt=10)
        _set_cell(tbl.cell(i + 1, 1), edu.get("degree", ""), pt=10)


def _fill_admissions(tbl, admissions: list[dict]):
    while len(tbl.rows) - 1 < len(admissions):
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
    while len(tbl.rows) - 1 > len(admissions):
        tbl._tbl.remove(tbl.rows[-1]._tr)
    for i, adm in enumerate(admissions):
        _set_cell(tbl.cell(i + 1, 0), adm.get("court", ""), pt=10)


def _remove_table(doc: Document, tbl):
    """Remove a table and the immediately following separator paragraph."""
    body = doc.element.body
    tbl_el = tbl._tbl
    siblings = list(body)
    idx = siblings.index(tbl_el)
    body.remove(tbl_el)
    # Remove one following empty paragraph if present
    siblings = list(body)
    if idx < len(siblings):
        nxt = siblings[idx]
        if nxt.tag.split("}")[-1] == "p":
            runs = nxt.findall(qn("w:r"))
            if not any(t.text for r in runs for t in r.findall(qn("w:t")) if t.text):
                body.remove(nxt)


# ── public API ───────────────────────────────────────────────────────────────

def build_docx(profile: dict) -> bytes:
    """
    Accept the structured profile dict from transform.py and return
    bytes of a .docx file using the Clario template for exact formatting.
    """
    doc = Document(str(TEMPLATE))

    # Template table layout (0-indexed):
    #   0 = name header
    #   1 = first experience (4 rows inc. 'Experience' heading)
    #   2–5 = subsequent experiences (3 rows each)  →  total 5 exp tables
    #   6 = prior experience
    #   7 = education
    #   8 = admissions
    tables = doc.tables
    name_tbl       = tables[0]
    first_exp_tbl  = tables[1]
    other_exp_tbls = list(tables[2:6])   # 4 tables → slots for exps 2–5
    prior_exp_tbl  = tables[6]
    edu_tbl        = tables[7]
    adm_tbl        = tables[8]

    experiences = profile.get("experiences") or []

    # ── name ────────────────────────────────────────────────────────────────
    _fill_name(name_tbl, profile.get("name", ""))

    # ── first experience ────────────────────────────────────────────────────
    if experiences:
        _fill_first_exp(first_exp_tbl, experiences[0])

    # ── other experience tables ─────────────────────────────────────────────
    for i, tbl in enumerate(other_exp_tbls):
        slot = i + 1   # index into experiences list
        if slot < len(experiences):
            _fill_exp(tbl, experiences[slot])
        else:
            _remove_table(doc, tbl)

    # ── extra experiences beyond the 5 template slots ──────────────────────
    if len(experiences) > 5:
        clone_src = other_exp_tbls[0]._tbl   # use first non-header exp as clone base
        insert_before = prior_exp_tbl._tbl
        body = doc.element.body
        for exp in experiences[5:]:
            new_tbl_el = copy.deepcopy(clone_src)
            body.insert(list(body).index(insert_before), new_tbl_el)
            _fill_exp(Table(new_tbl_el, doc), exp)

    # ── prior experience ────────────────────────────────────────────────────
    if profile.get("prior_experience"):
        _fill_prior_exp(prior_exp_tbl, profile["prior_experience"])
    else:
        _remove_table(doc, prior_exp_tbl)

    # ── education ───────────────────────────────────────────────────────────
    _fill_education(edu_tbl, profile.get("education") or [])

    # ── admissions ──────────────────────────────────────────────────────────
    _fill_admissions(adm_tbl, profile.get("admissions") or [])

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
