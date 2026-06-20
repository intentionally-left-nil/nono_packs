"""
Scenario 3: $PREFIX access.

Confirms that ``--allow $PREFIX`` (expanded in the test profile) grants the
Python process access to the venv's stdlib, site-packages, and shared libraries.
This is a structural test of the profile's ``filesystem.allow`` section.

Tests:

1. ``test_sys_prefix_matches_conda_prefix`` — ``sys.prefix`` resolves to the
   same real path as ``CONDA_PREFIX`` (set by the harness to the test prefix).
2. ``test_tmpdir_write``                    — ``tempfile.NamedTemporaryFile``
   succeeds when ``TMPDIR`` is redirected into the prefix's ``tmp/`` subdir.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

TEST_PREFIX = Path("/tmp/nono-pypack-test")


# ---------------------------------------------------------------------------
# 1. sys.prefix resolves to the test prefix
# ---------------------------------------------------------------------------


def test_sys_prefix_matches_conda_prefix(sandbox):
    """
    Inside the sandbox, ``sys.prefix`` must resolve to the same real path
    as the ``CONDA_PREFIX`` environment variable.

    The harness sets ``CONDA_PREFIX=$PREFIX`` before invoking nono-sideload,
    so this confirms the Python interpreter is actually running from the
    expected prefix.
    """
    result = sandbox(
        """
        import sys, os
        expected = os.path.realpath(os.environ["CONDA_PREFIX"])
        actual   = os.path.realpath(sys.prefix)
        assert actual == expected, f"got {actual!r}, expected {expected!r}"
        print("PREFIX_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "PREFIX_OK" in result.stdout, (
        f"Marker PREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. Write to $PREFIX/tmp (the redirected TMPDIR)
# ---------------------------------------------------------------------------


def test_tmpdir_write(sandbox):
    """
    ``tempfile.NamedTemporaryFile`` must succeed inside the sandbox when
    ``TMPDIR`` is redirected to ``$PREFIX/tmp``.

    The harness sets ``TMPDIR=$PREFIX/tmp`` in the environment, but does NOT
    pre-create the directory.  We create it here (outside the sandbox) before
    invoking nono-sideload, and clean it up after.
    """
    tmpdir = TEST_PREFIX / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        result = sandbox(
            """
            import tempfile, os
            assert os.environ["TMPDIR"].startswith(os.environ["CONDA_PREFIX"]), (
                f"TMPDIR {os.environ['TMPDIR']!r} does not start with "
                f"CONDA_PREFIX {os.environ['CONDA_PREFIX']!r}"
            )
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"x")
            print("TMPDIR_OK")
            """
        )
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "TMPDIR_OK" in result.stdout, (
        f"Marker TMPDIR_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
