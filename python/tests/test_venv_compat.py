"""
Scenario 9: Virtual environment compatibility.

Goal: Confirm that a venv built on top of the test prefix is detected
correctly by CPython — sys.prefix points at the inner venv, not the base
prefix.

This exercises that the profile does not interfere with standard venv
behaviour. The nested venv python is invoked directly (not via the base
prefix python), requiring ``sandbox.run_in`` rather than the plain callable.

Tests:

1. ``test_nested_venv_prefix``      — sys.prefix is the nested venv.
2. ``test_nested_venv_base_prefix`` — sys.base_prefix is the base prefix.
3. ``test_nested_venv_site_packages`` — nested site-packages on sys.path;
                                        base site-packages absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

NESTED_VENV = Path("/tmp/pybox-nested-venv")


# ---------------------------------------------------------------------------
# Session-scoped fixture: create (and tear down) the nested venv
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def nested_venv(patched_policy: str, python_prefix: Path) -> None:  # type: ignore[return]  # noqa: PT004
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
        [str(python_prefix / "bin" / "python"), "-m", "venv", str(NESTED_VENV)],
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


def test_nested_venv_prefix(nested_venv: None, sandbox, python_prefix: Path) -> None:
    """
    Inside the nested venv, ``sys.prefix`` must resolve to the nested venv
    path, not to the base conda prefix.

    Expected: exits 0, prints NESTED_PREFIX_OK.
    """
    result = sandbox.run_in(
        NESTED_VENV / "bin" / "python",
        ["-c", """
import sys, os
expected = os.path.realpath("/tmp/pybox-nested-venv")
actual = os.path.realpath(sys.prefix)
assert actual == expected, f"got {actual!r}"
print("NESTED_PREFIX_OK")
""".strip()],
        extra_allow=[str(NESTED_VENV)],
        extra_env={"CONDA_PREFIX": str(python_prefix)},
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


def test_nested_venv_base_prefix(nested_venv: None, sandbox, python_prefix: Path) -> None:
    """
    Inside the nested venv, ``sys.base_prefix`` must resolve to the base
    conda prefix (``CONDA_PREFIX``), which the harness sets to the test prefix.

    Expected: exits 0, prints BASE_PREFIX_OK.
    """
    result = sandbox.run_in(
        NESTED_VENV / "bin" / "python",
        ["-c", """
import sys, os
expected = os.path.realpath(os.environ["CONDA_PREFIX"])
actual = os.path.realpath(sys.base_prefix)
assert actual == expected, f"got {actual!r}"
print("BASE_PREFIX_OK")
""".strip()],
        extra_allow=[str(NESTED_VENV)],
        extra_env={"CONDA_PREFIX": str(python_prefix)},
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


def test_nested_venv_site_packages(nested_venv: None, sandbox, python_prefix: Path) -> None:
    """
    Inside the nested venv, ``sys.path`` must include a path from the nested
    venv's ``lib/`` tree that contains ``site-packages``, while the base
    prefix's ``lib/`` must not contribute any ``site-packages`` entry.

    Expected: exits 0, prints SITE_PACKAGES_OK.
    """
    result = sandbox.run_in(
        NESTED_VENV / "bin" / "python",
        ["-c", """
import sys, os
nested_lib = os.path.realpath("/tmp/pybox-nested-venv/lib")
base_lib   = os.path.realpath(os.environ["CONDA_PREFIX"] + "/lib")
paths = [os.path.realpath(p) for p in sys.path]
assert any(p.startswith(nested_lib) and "site-packages" in p for p in paths), \
    f"nested site-packages missing: {paths}"
assert not any(p.startswith(base_lib) and "site-packages" in p for p in paths), \
    f"base site-packages leaked: {paths}"
print("SITE_PACKAGES_OK")
""".strip()],
        extra_allow=[str(NESTED_VENV)],
        extra_env={"CONDA_PREFIX": str(python_prefix)},
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
