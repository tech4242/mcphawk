import pytest

from mcphawk.query import Query
from mcphawk.store import Recorder


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real ~/.mcphawk from tests."""
    home = tmp_path / "mcphawk-home"
    monkeypatch.setenv("MCPHAWK_HOME", str(home))
    monkeypatch.setenv("MCPHAWK_DB", str(home / "test.db"))
    return home


@pytest.fixture
def db(isolated_home):
    return isolated_home / "test.db"


@pytest.fixture
def recorder(db):
    rec = Recorder(db)
    yield rec
    rec.close()


@pytest.fixture
def query(db, recorder):
    q = Query(db)
    yield q
    q.close()
