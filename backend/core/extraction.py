"""Turn an uploaded PDF, DOCX or TXT file into clean text plus a structured list of sections."""
import re
import zipfile
from pathlib import Path

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_PDF_PAGES = 200
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MIN_TEXT_CHARS = 20  # fewer readable characters than this = treated as "no text" (e.g. a scanned PDF)


class ExtractionError(Exception):
    """Raised with a message that is safe to show to the user."""


def get_extension(filename):
    return Path(filename).suffix.lower().lstrip(".")


def clean_text(text):
    """Normalise line endings and remove characters PostgreSQL or JSON cannot store."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    text = text.encode("utf-8", "ignore").decode("utf-8")  # drops broken surrogate characters
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def verify_content(path, extension):
    """Check the file really is what its extension says (the name alone is not trusted)."""
    with open(path, "rb") as handle:
        head = handle.read(8192)
    if not head:
        raise ExtractionError("The file is empty.")

    if extension == "pdf":
        if b"%PDF-" not in head[:1024]:
            raise ExtractionError("This file is not a valid PDF.")

    elif extension == "docx":
        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ExtractionError("This file is not a valid DOCX document.")
                if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise ExtractionError("This document is unsafe to open because it expands to a huge size.")
        except zipfile.BadZipFile:
            raise ExtractionError("This file is not a valid DOCX document.")

    elif extension == "txt":
        if b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise ExtractionError("This file does not look like a plain text file.")


def extract_pdf(path):
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("This PDF is password protected.")

        total_pages = len(reader.pages)
        if total_pages > MAX_PDF_PAGES:
            raise ExtractionError(f"This PDF has {total_pages} pages. The limit is {MAX_PDF_PAGES}.")

        sections = []
        for number, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            if text:
                sections.append({"label": f"Page {number}", "page": number, "text": text})
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError("We couldn't read this PDF. It may be damaged.")

    return sections, total_pages


def extract_docx(path):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(str(path))
        sections = []
        current = {"label": "Document", "lines": []}

        def flush():
            text = clean_text("\n".join(current["lines"]))
            if text:
                sections.append({"label": current["label"], "text": text})

        for child in document.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]

            if tag == "p":
                paragraph = Paragraph(child, document)
                text = paragraph.text.strip()
                if not text:
                    continue
                style = (paragraph.style.name if paragraph.style is not None else "") or ""
                if style.lower().startswith("heading") or style == "Title":
                    flush()  # a heading starts a new section
                    current = {"label": text[:120], "lines": [text]}
                else:
                    current["lines"].append(text)

            elif tag == "tbl":
                table = Table(child, document)
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    line = " | ".join(cell for cell in cells if cell)
                    if line:
                        current["lines"].append(line)

        flush()
    except Exception:
        raise ExtractionError("We couldn't read this DOCX file. It may be damaged.")

    return sections


def extract_txt(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")

    text = clean_text(text)
    return [{"label": "Text", "text": text}] if text else []


def extract_document(path, extension):
    """Return a dict: text, sections, page_count, word_count, char_count."""
    path = Path(path)
    verify_content(path, extension)

    page_count = None
    if extension == "pdf":
        sections, page_count = extract_pdf(path)
    elif extension == "docx":
        sections = extract_docx(path)
    else:
        sections = extract_txt(path)

    sections = [{"index": number, **section} for number, section in enumerate(sections, start=1)]
    full_text = "\n\n".join(section["text"] for section in sections)

    if len(full_text) < MIN_TEXT_CHARS:
        raise ExtractionError(
            "No readable text found in this file. Scanned documents and images are not supported yet."
        )

    return {
        "text": full_text,
        "sections": sections,
        "page_count": page_count,
        "word_count": len(full_text.split()),
        "char_count": len(full_text),
    }