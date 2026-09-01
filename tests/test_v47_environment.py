from pathlib import Path
from unittest.mock import patch

import pytest

from app.github import github_readiness, normalize_github_repository_url


def test_github_repository_url_is_normalized_and_rejects_non_github():
    assert normalize_github_repository_url("https://github.com/example/sermon/") == "https://github.com/example/sermon"
    with pytest.raises(ValueError):
        normalize_github_repository_url("https://gitlab.com/example/sermon")


def test_github_readiness_is_read_only_when_project_has_no_git(tmp_path: Path):
    with patch("app.github.subprocess.run") as run:
        run.return_value.returncode = 128
        result = github_readiness(tmp_path, tmp_path / "settings.sqlite3")
    assert result["repository"] is False
    assert result["state"] == "warn"
    run.assert_called_once()
