from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path):
    from newsroom.paths import set_db_path_override

    path = tmp_path / "newsroom.db"
    set_db_path_override(path)
    yield path
    set_db_path_override(None)
