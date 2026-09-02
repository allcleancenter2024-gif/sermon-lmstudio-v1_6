"""Keep test-created temporary files inside the project test workspace.

Some managed Windows installations point TEMP/TMP at a protected shared
directory.  pytest's ``tmp_path`` and the standard library's
``TemporaryDirectory`` must use the same writable location so tests do not
depend on that machine-wide setting.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def pytest_configure(config) -> None:
    temp_root = Path(config.rootpath) / ".test-runs" / "pytest-tempfile"
    temp_root.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = str(temp_root)
    os.environ["TEMP"] = str(temp_root)
    tempfile.tempdir = str(temp_root)
