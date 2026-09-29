"""Read pasted text, text PDFs, and DOCX syllabi into an editable outline."""

from __future__ import annotations

import re
from pathlib import Path

from study_tutor.config import MAX_DOCUMENT_CHARS, MAX_FILE_BYTES
from study_tutor.errors import ScannedDocumentError, TutorError
from study_tutor.schemas import SyllabusDraft, TopicDraft, UnitDraft, detect_focus, infer_kind

UNIT_LINE = re.compile(
    r"^\s*(?:unit|module|chapter|part|week)\s*[-–:]?\s*([0-9]+|[ivxlcdm]+)\b\s*[-–:.)]*\s*(.*)$",
    re.IGNORECASE,
)
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-z][.)])\s+(.*)$", re.IGNORECASE)
UNIT_CELL = re.compile(
    r"^(?:unit|module|chapter|part|week)?\s*[-–:]?\s*([0-9]+|[ivxlcdm]+)\b",
    re.IGNORECASE,
)

SAMPLE_SYLLABUS = """Business Analytics
MBA 204

Unit I: Framing a decision
- What a business question is asking
- Descriptive, diagnostic, and predictive views
- How to choose a metric

Unit II: Excel for analysis
- Cleaning a transaction list on a worksheet
- Pivot tables for regional sales
- XLOOKUP for a product master

Unit III: Power BI dashboards
- Star schema and relationships
- DAX measures for year-to-date sales
- Building a report page for a weekly review

Unit IV: Python for a repeatable check
- Reading a CSV with pandas
- Filtering rows and summarising a column
- A small script that flags missing prices
"""


def read_document(path: str | Path) -> str:
    source = Path(path)
    if not source.is_file():
        raise TutorError("That file could not be found.")
    if source.stat().st_size > MAX_FILE_BYTES:
        raise TutorError("That file is larger than 15 MB. Split it or paste the relevant section.")
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(source)
    elif suffix == ".docx":
        text = _read_docx(source)
    elif suffix in {".txt", ".md"}:
        text = _read_text(source)
    else:
        raise TutorError("Use a text PDF, a DOCX file, or paste the syllabus.")
    cleaned = text.strip()
    if not cleaned:
        raise TutorError("That file did not contain any text.")
    if len(cleaned) > MAX_DOCUMENT_CHARS:
        cleaned = cleaned[:MAX_DOCUMENT_CHARS]
    return cleaned


def assess_text_layer(text: str, page_count: int) -> None:
    compact = len(re.sub(r"\s+", "", text))
    minimum = 40 * max(1, page_count)
    if page_count >= 1 and compact < minimum:
        raise ScannedDocumentError(
            "This PDF has almost no selectable text. Scanned pages need OCR, "
            "which this version does not include. Paste the syllabus or use a text-based PDF or DOCX."
        )


def parse_syllabus_locally(text: str, subject_name: str = "") -> SyllabusDraft:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    units: list[UnitDraft] = []
    current: UnitDraft | None = None
    preface: list[str] = []

    def start_unit(title: str) -> None:
        nonlocal current
        unit = UnitDraft(title=_tidy(title)[:160], topics=[])
        units.append(unit)
        current = unit

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        table_unit = _unit_from_table(line)
        if table_unit is not None:
            units.append(table_unit)
            current = table_unit
            continue
        match = UNIT_LINE.match(line)
        if match:
            suffix = match.group(2).strip(" -:.")
            number = match.group(1).upper()
            title = f"Unit {number}: {suffix}" if suffix else f"Unit {number}"
            start_unit(title)
            continue
        if current is None:
            preface.append(line)
            continue
        bullet = BULLET.match(line)
        body = bullet.group(1).strip() if bullet else line
        if len(body) > 180 and bullet is None:
            if current.topics and not current.topics[-1].objective:
                current.topics[-1].objective = body[:400]
            continue
        if len(body) < 3:
            continue
        current.topics.append(_topic(body))

    if not units:
        bullet_topics = []
        for line in preface:
            match = BULLET.match(line)
            if match and len(match.group(1).strip()) >= 3:
                bullet_topics.append(_topic(match.group(1)))
        if bullet_topics:
            units.append(UnitDraft(title="Syllabus", topics=bullet_topics))
        else:
            usable = [_topic(line) for line in preface if 3 <= len(line) <= 120]
            if usable:
                units.append(UnitDraft(title=subject_name.strip() or "Syllabus", topics=usable[:30]))

    for unit in units:
        if not unit.topics:
            unit.topics.append(
                TopicDraft(
                    title=unit.title,
                    objective="Study the main ideas in this unit.",
                    focus=detect_focus(unit.title),
                )
            )
    if not units:
        raise TutorError("No units or topics were found. Paste a syllabus that lists units and topics.")

    name = subject_name.strip() or _guess_name(preface) or units[0].title
    return SyllabusDraft(subject_name=name[:120], kind=infer_kind(units), units=units)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise TutorError("PDF support is not installed.") from exc
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise TutorError("That PDF could not be opened. If it is password protected, unlock it first.") from exc
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(pages)
    assess_text_layer(text, len(reader.pages))
    return text


def _read_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as exc:
        raise TutorError("DOCX support is not installed.") from exc
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise TutorError("That DOCX file could not be opened.") from exc
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                value = " ".join(cell.text.split())
                if not cells or cells[-1] != value:
                    cells.append(value)
            line = " | ".join(cell for cell in cells if cell)
            if line:
                lines.append(line)
    return "\n".join(lines)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TutorError("That text file is not UTF-8 or Windows-1252.")


def _unit_from_table(line: str) -> UnitDraft | None:
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in line.split("|") if cell.strip()]
    if len(cells) < 2:
        return None
    if cells[0].lower() in {"unit", "module", "chapter", "topics", "content"}:
        return None
    match = UNIT_CELL.match(cells[0])
    if match is None:
        return None
    number = match.group(1).upper()
    body_cells = cells[1:]
    title = f"Unit {number}"
    topic_source = " ".join(body_cells)
    if len(body_cells) >= 2 and len(body_cells[0]) <= 80 and not re.search(r"[;,]", body_cells[0]):
        title = f"Unit {number}: {body_cells[0]}"
        topic_source = " ".join(body_cells[1:])
    pieces = [piece.strip(" -") for piece in re.split(r"[;\n•]", topic_source) if piece.strip(" -")]
    if len(pieces) == 1 and "," in pieces[0]:
        pieces = [piece.strip() for piece in pieces[0].split(",") if piece.strip()]
    topics = [_topic(piece) for piece in pieces if len(piece) >= 3]
    if not topics:
        topics = [_topic(title)]
    return UnitDraft(title=_tidy(title)[:160], topics=topics)


def _topic(title: str) -> TopicDraft:
    cleaned = _tidy(title)
    return TopicDraft(title=cleaned[:160], objective="", focus=detect_focus(cleaned))


def _tidy(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -:;")


def _guess_name(preface: list[str]) -> str:
    for line in preface:
        if UNIT_LINE.match(line) or BULLET.match(line):
            continue
        if 3 <= len(line) <= 80:
            return _tidy(line)
    return ""
