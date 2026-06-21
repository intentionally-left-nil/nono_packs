"""
Scenario 17: pip install works inside the sandbox.

Confirms that the $PREFIX write grant actually allows pip to install a package
into the sandboxed environment end-to-end.  This is the happy-path counterpart
to Scenario 16b (which tests that a *malicious* install hook is blocked).

Tests:

1. ``test_pip_install_package``  — runs ``pip install`` for a small, pure-Python
   package (``cowsay``) inside the sandbox and asserts the package is importable
   afterwards.

2. ``test_pip_uninstall_package`` — runs ``pip uninstall`` inside the sandbox
   and asserts the package is no longer importable afterwards.

``cowsay`` is chosen because it is tiny (~10 KB), pure-Python, has no C
extensions, no post-install scripts, and no transitive dependencies — so the
test is fast and exercises only the filesystem write path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

TEST_PREFIX = Path("/tmp/nono-pypack-test")

# Package used for install/uninstall round-trip.  Must be:
#   - small and pure-Python (fast, no build step)
#   - not already a dependency of anything else in the test suite
#   - stable on PyPI
_TEST_PKG = "cowsay"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pip(sandbox, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run ``pip <args>`` inside the sandbox."""
    pip_bin = TEST_PREFIX / "bin" / "pip"
    return sandbox.run_in(pip_bin, list(args), timeout=timeout)


def _can_import(sandbox, module: str) -> bool:
    result = sandbox(f"import {module}; print('IMPORT_OK')", timeout=15)
    return result.returncode == 0 and "IMPORT_OK" in result.stdout


# ---------------------------------------------------------------------------
# Ensure the package is *not* already installed before the suite runs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def ensure_uninstalled(sandbox):
    """Remove cowsay from the test prefix (if present) before/after tests."""
    pip_bin = TEST_PREFIX / "bin" / "pip"
    sandbox.run_in(pip_bin, ["uninstall", _TEST_PKG, "--yes"], timeout=60)
    yield
    sandbox.run_in(pip_bin, ["uninstall", _TEST_PKG, "--yes"], timeout=60)


# ---------------------------------------------------------------------------
# 1. pip install succeeds inside the sandbox
# ---------------------------------------------------------------------------


def test_pip_install_package(sandbox):
    """
    ``pip install cowsay`` must succeed when run inside the nono sandbox.

    The profile grants read+write to $PREFIX, so pip must be able to write
    into ``$PREFIX/lib/pythonX.Y/site-packages/`` and create any entry-points
    in ``$PREFIX/bin/``.
    """
    result = _pip(sandbox, "install", _TEST_PKG, "--quiet")

    assert result.returncode == 0, (
        f"pip install exited {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )

    # Confirm the package is now importable inside the sandbox.
    assert _can_import(sandbox, _TEST_PKG), (
        f"Package '{_TEST_PKG}' is not importable after pip install.\n"
        f"install stdout: {result.stdout!r}\n"
        f"install stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. pip uninstall succeeds inside the sandbox
# ---------------------------------------------------------------------------


def test_pip_uninstall_package(sandbox):
    """
    ``pip uninstall cowsay --yes`` must succeed inside the sandbox and leave
    the package unimportable.

    Depends on ``test_pip_install_package`` having installed cowsay first.
    """
    result = _pip(sandbox, "uninstall", _TEST_PKG, "--yes")

    assert result.returncode == 0, (
        f"pip uninstall exited {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )

    # Confirm the package is no longer importable.
    assert not _can_import(sandbox, _TEST_PKG), (
        f"Package '{_TEST_PKG}' is still importable after pip uninstall."
    )
