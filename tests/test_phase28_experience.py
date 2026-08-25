from newsroom.experience import ExperienceService
from newsroom.migrations import apply_migrations


def test_experience_mode_is_presentation_state_not_a_capability_authority(tmp_db):
    apply_migrations(tmp_db)
    experience = ExperienceService(tmp_db)
    assert experience.get() == {"mode": "simple"}
    assert experience.set_mode("advanced") == {"mode": "advanced"}
