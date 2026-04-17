from __future__ import annotations
import io
import re


async def extract_text(content: bytes, filename: str) -> tuple[str | None, int | None, str | None]:
    """Extract text from PDF, DOCX, or TXT. Returns (text, word_count, error)."""
    lower = filename.lower()
    try:
        if lower.endswith(".pdf"):
            return _extract_pdf(content)
        elif lower.endswith(".docx"):
            return _extract_docx(content)
        elif lower.endswith(".txt"):
            text = content.decode("utf-8", errors="replace")
            return text, _count_words(text), None
        else:
            for fn in (_extract_pdf, _extract_docx):
                try:
                    return fn(content)
                except Exception:
                    pass
            text = content.decode("utf-8", errors="replace")
            return text, _count_words(text), None
    except Exception as e:
        return None, None, str(e)


def _extract_pdf(content: bytes) -> tuple[str, int, None]:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)
    return text, _count_words(text), None


def _extract_docx(content: bytes) -> tuple[str, int, None]:
    from docx import Document
    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs)
    return text, _count_words(text), None


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))
