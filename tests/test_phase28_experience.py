from newsroom.experience import ExperienceService
from newsroom.migrations import apply_migrations


def test_experience_mode_controls_advanced_capabilities(tmp_db):
    apply_migrations(tmp_db)
    experience = ExperienceService(tmp_db)
    assert experience.get()["mode"] == "simple"
    assert experience.get()["capabilities"]["hypotheses"] is False
    assert experience.set_mode("advanced")["capabilities"]["hypotheses"] is True
