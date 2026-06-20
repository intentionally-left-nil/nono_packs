"""
Scenario 9: Virtual environment compatibility.

Goal: Confirm that a venv built on top of the test prefix is detected
correctly by CPython — sys.prefix points at the inner venv, not the base
prefix.

This exercises that the profile does not interfere with standard venv
behaviour. The nested venv python is invoked directly (not via the base
prefix python), requiring a module-level helper rather than the ``sandbox``
fixture.

Tests:

1. ``test_nested_venv_prefix``      — sys.prefix is the nested venv.
2. ``test_nested_venv_base_prefix`` — sys.base_prefix is the base prefix.
3. ``test_nested_venv_site_packages`` — nested site-packages on sys.path;
                                        base site-packages absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_PREFIX = Path("/tmp/nono-pypack-test")
NESTED_VENV = Path("/tmp/pybox-nested-venv")

PROFILE_NAME = "intentionally-left-nil/python"

NONO = shutil.which("nono-sideload") or "nono-sideload"


# ---------------------------------------------------------------------------
# Module-level helper: run code in nested venv via nono-sideload
# ---------------------------------------------------------------------------


def _run_in_nested_venv(
    code: str,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """
    Invoke ``/tmp/pybox-nested-venv/bin/python -c <code>`` through
    ``nono-sideload run``.

    Both ``TEST_PREFIX`` and ``NESTED_VENV`` are added to ``--allow``.
    ``CONDA_PREFIX`` is set to ``TEST_PREFIX`` (mirroring the sandbox fixture).
    """
    venv_python = NESTED_VENV / "bin" / "python"

    cmd = [
        NONO, "run",
        "--profile", PROFILE_NAME,
        "--allow", str(TEST_PREFIX),
        "--allow", str(NESTED_VENV),
        "--", str(venv_python), "-c", textwrap.dedent(code),
    ]

    env = os.environ.copy()
    env["CONDA_PREFIX"] = str(TEST_PREFIX)
    env["TMPDIR"] = str(TEST_PREFIX / "tmp")
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


# ---------------------------------------------------------------------------
# Session-scoped fixture: create (and tear down) the nested venv
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def nested_venv(patched_policy: str) -> None:  # type: ignore[return]  # noqa: PT004
    """
    Create ``/tmp/pybox-nested-venv`` from the test prefix Python, then
    yield.  The venv is removed after the session.

    Depends on ``patched_policy`` (which depends on ``python_prefix`` and
    ``sideloaded_pack``) to ensure the pack is sideloaded and the prefix
    exists before we try to use it.
    """
    if NESTED_VENV.exists():
        shutil.rmtree(NESTED_VENV)

    subprocess.run(
        [str(TEST_PREFIX / "bin" / "python"), "-m", "venv", str(NESTED_VENV)],
        check=True,
    )

    yield  # type: ignore[misc]

    try:
        shutil.rmtree(NESTED_VENV)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. sys.prefix is the nested venv, not the base prefix
# ---------------------------------------------------------------------------


def test_nested_venv_prefix(nested_venv: None) -> None:
    """
    Inside the nested venv, ``sys.prefix`` must resolve to the nested venv
    path, not to the base conda prefix.

    Expected: exits 0, prints NESTED_PREFIX_OK.
    """
    result = _run_in_nested_venv(
        """
        import sys, os
        expected = os.path.realpath("/tmp/pybox-nested-venv")
        actual = os.path.realpath(sys.prefix)
        assert actual == expected, f"got {actual!r}"
        print("NESTED_PREFIX_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "NESTED_PREFIX_OK" in result.stdout, (
        f"Marker NESTED_PREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. sys.base_prefix is the base prefix (the Python installation)
# ---------------------------------------------------------------------------


def test_nested_venv_base_prefix(nested_venv: None) -> None:
    """
    Inside the nested venv, ``sys.base_prefix`` must resolve to the base
    conda prefix (``CONDA_PREFIX``), which the harness sets to ``TEST_PREFIX``.

    Expected: exits 0, prints BASE_PREFIX_OK.
    """
    result = _run_in_nested_venv(
        """
        import sys, os
        expected = os.path.realpath(os.environ["CONDA_PREFIX"])
        actual = os.path.realpath(sys.base_prefix)
        assert actual == expected, f"got {actual!r}"
        print("BASE_PREFIX_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "BASE_PREFIX_OK" in result.stdout, (
        f"Marker BASE_PREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. Nested venv's site-packages is on sys.path; base prefix's is not
# ---------------------------------------------------------------------------


def test_nested_venv_site_packages(nested_venv: None) -> None:
    """
    Inside the nested venv, ``sys.path`` must include a path from the nested
    venv's ``lib/`` tree that contains ``site-packages``, while the base
    prefix's ``lib/`` must not contribute any ``site-packages`` entry.

    Expected: exits 0, prints SITE_PACKAGES_OK.
    """
    result = _run_in_nested_venv(
        """
        import sys, os
        nested_lib = os.path.realpath("/tmp/pybox-nested-venv/lib")
        base_lib   = os.path.realpath(os.environ["CONDA_PREFIX"] + "/lib")
        paths = [os.path.realpath(p) for p in sys.path]
        assert any(p.startswith(nested_lib) and "site-packages" in p for p in paths), \
            f"nested site-packages missing: {paths}"
        assert not any(p.startswith(base_lib) and "site-packages" in p for p in paths), \
            f"base site-packages leaked: {paths}"
        print("SITE_PACKAGES_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "SITE_PACKAGES_OK" in result.stdout, (
        f"Marker SITE_PACKAGES_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
