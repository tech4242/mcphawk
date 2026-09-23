from mcphawk import paths


def test_defaults_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("MCPHAWK_HOME", raising=False)
    monkeypatch.delenv("MCPHAWK_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.data_dir() == tmp_path / ".mcphawk"
    assert paths.db_path() == tmp_path / ".mcphawk" / "mcphawk.db"
    assert (tmp_path / ".mcphawk").is_dir()


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("MCPHAWK_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("MCPHAWK_DB", str(tmp_path / "d" / "x.db"))
    assert paths.data_dir() == tmp_path / "h"
    assert paths.db_path() == tmp_path / "d" / "x.db"
    assert (tmp_path / "d").is_dir()
