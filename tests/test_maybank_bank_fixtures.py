from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_maybank_bank_fixture_verifier() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_maybank_bank_fixtures.py")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK: 18 reported bank facts")
