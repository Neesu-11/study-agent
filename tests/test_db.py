from datetime import date

from study_tutor.db import Database
from study_tutor.progress import apply_score
from study_tutor.syllabus import SAMPLE_SYLLABUS, parse_syllabus_locally


def test_subject_round_trip_and_cascade(tmp_path):
    database = Database(tmp_path / "tutor.db")
    draft = parse_syllabus_locally(SAMPLE_SYLLABUS, "Business Analytics")
    subject_id = database.create_subject(draft, SAMPLE_SYLLABUS)
    topics = database.topics_for_subject(subject_id)
    assert len(topics) == 12
    assert database.outline_pairs(subject_id)[1][0].startswith("Unit II")
    database.add_material(subject_id, "Lecture 1", "note", "Choose one metric before you open Excel.")
    database.add_message(subject_id, topics[0].id, "teach", "user", "Teach me this topic.")
    database.set_setting("gemini_model", "gemini-3.8-flash")
    assert database.get_setting("gemini_model", "") == "gemini-3.8-flash"
    assert database.next_new_topic(subject_id).id == topics[0].id
    state = apply_score(topics[0].review_state(), 40, date(2026, 9, 29))
    database.save_review(topics[0].id, state)
    database.add_attempt(topics[0].id, "quiz", 2, 5, 40, ["metrics"], "Missed the metric.")
    weak = database.weak_topics(subject_id, date(2026, 9, 29))
    assert weak[0].id == topics[0].id
    assert "metric" in database.recent_weak_points(topics[0].id).lower()
    summaries = database.list_subjects(date(2026, 9, 29))
    assert summaries[0].topic_count == 12
    assert summaries[0].weak_count == 1
    database.delete_subject(subject_id)
    assert database.list_subjects() == []
    assert database.list_materials(subject_id) == []
    database.close()
