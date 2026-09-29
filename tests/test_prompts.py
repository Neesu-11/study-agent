from study_tutor.materials import Material, select_excerpts
from study_tutor.prompts import ask_request, format_outline, system_prompt


def test_system_prompt_keeps_the_topic_and_the_source():
    prompt = system_prompt(
        subject_name="Business Analytics",
        kind="general",
        syllabus_text="Unit II covers pivot tables.",
        outline=format_outline([("Unit II", ["Pivot tables"])]),
        unit_title="Unit II",
        topic_title="Pivot tables",
        objective="Summarise sales by region.",
        focus="excel",
        materials_excerpt="Source: Class notes\nUse Insert, PivotTable.",
    )
    assert "Pivot tables" in prompt
    assert "outside" in prompt
    assert "Source: Class notes" in prompt
    assert "ribbon" in prompt.lower()
    assert "workbook" in prompt.lower()


def test_python_prompt_asks_for_code_not_a_file_edit():
    prompt = system_prompt(
        subject_name="Analytics",
        kind="python",
        syllabus_text="pandas",
        outline="Unit IV\n- pandas",
        unit_title="Unit IV",
        topic_title="Reading a CSV",
        objective="",
        focus="python",
        materials_excerpt="",
    )
    assert "Python" in prompt
    assert "Do not claim you created or edited a file." in prompt


def test_follow_up_stays_on_the_question():
    assert "contribution margin" in ask_request("What is contribution margin?")


def test_material_excerpt_prefers_the_matching_note():
    materials = [
        Material("Other", "note", "Brand equity is the value of a name in the market today."),
        Material(
            "Excel lab",
            "textbook",
            "A pivot table summarises regional sales without rewriting every formula by hand.",
        ),
    ]
    excerpt = select_excerpts(materials, "Pivot tables")
    assert "Excel lab" in excerpt
    assert excerpt.index("Excel lab") < excerpt.index("Brand equity") if "Brand equity" in excerpt else True
