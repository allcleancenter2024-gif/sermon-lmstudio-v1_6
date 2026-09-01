from pathlib import Path

from app.github import DEFAULT_GITHUB_REPOSITORY_URL, get_github_repository_url


def test_github_default_is_allcleancenter_repository(tmp_path: Path):
    assert get_github_repository_url(tmp_path / "settings.sqlite3") == DEFAULT_GITHUB_REPOSITORY_URL
