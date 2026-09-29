from pathlib import Path

import pytest
from pypdf import PdfWriter

from study_tutor.errors import ScannedDocumentError
from study_tutor.syllabus import SAMPLE_SYLLABUS, assess_text_layer, parse_syllabus_locally, read_document


def test_sample_syllabus_keeps_units_and_lesson_styles():
    draft = parse_syllabus_locally(SAMPLE_SYLLABUS, "")
    assert draft.subject_name == "Business Analytics"
    assert draft.kind == "general"
    assert [unit.title for unit in draft.units] == [
        "Unit I: Framing a decision",
        "Unit II: Excel for analysis",
        "Unit III: Power BI dashboards",
        "Unit IV: Python for a repeatable check",
    ]
    excel = draft.units[1].topics
    assert excel[1].focus == "excel"
    assert draft.units[2].topics[1].focus == "powerbi"
    assert draft.units[3].topics[0].focus == "python"
    assert draft.units[0].topics[0].focus == "concept"


def test_table_row_becomes_a_unit():
    text = "Accounting\nI | Framework | Journal entries; Trial balance\n"
    draft = parse_syllabus_locally(text, "")
    assert draft.units[0].title == "Unit I: Framework"
    assert [topic.title for topic in draft.units[0].topics] == ["Journal entries", "Trial balance"]


def test_bullets_without_units_still_make_topics():
    text = "Notes\n- Contribution margin\n- Break-even point\n"
    draft = parse_syllabus_locally(text, "Costing")
    assert draft.subject_name == "Costing"
    assert [topic.title for topic in draft.units[0].topics] == ["Contribution margin", "Break-even point"]


def test_scanned_pdf_is_rejected(tmp_path: Path):
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ScannedDocumentError):
        read_document(path)


def test_docx_paragraphs_and_table(tmp_path: Path):
    import docx

    path = tmp_path / "syllabus.docx"
    document = docx.Document()
    document.add_paragraph("Marketing Management")
    document.add_paragraph("Unit I: Segmentation")
    document.add_paragraph("Targeting and positioning")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "II"
    table.rows[0].cells[1].text = "Brand equity"
    document.save(path)
    text = read_document(path)
    draft = parse_syllabus_locally(text, "")
    titles = [unit.title for unit in draft.units]
    assert any("Segmentation" in title for title in titles)
    assert any(topic.title == "Brand equity" for unit in draft.units for topic in unit.topics)


def test_text_layer_threshold():
    assess_text_layer("x" * 50, 1)
    with pytest.raises(ScannedDocumentError):
        assess_text_layer("hi", 2)
