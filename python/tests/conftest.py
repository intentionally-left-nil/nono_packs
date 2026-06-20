"""
conftest.py — pytest fixtures for the nono python pack test suite.

The Makefile (python/tests/Makefile) is responsible for creating the conda
environment that pytest itself runs in.  These fixtures only manage the
*sandboxed* Python prefix — the isolated conda env (or venv fallback) that
the nono sandbox wraps during tests.

Key design points
-----------------
- ``python_prefix``  — session-scoped; creates /tmp/nono-pypack-test, tears
                       it down after the session.
- ``patched_policy`` — session-scoped; sideloads the pack then patches
                       ``$PREFIX`` in the *installed* profile (in the pack
                       store), so nono resolves the profile by name and can
                       expand ``$PACK_DIR`` in session_hooks normally.
- ``sandbox``        — session-scoped callable; thin wrapper around
                       ``nono-sideload run`` using the profile name, not a
                       file path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent  # …/nono_packs
PACK_DIR = REPO_ROOT / "python"
POLICY_SRC = PACK_DIR / "policy.json"

TEST_PREFIX = Path("/tmp/nono-pypack-test")

# Profile name as known to nono after sideloading (install_as in package.json).
PROFILE_NAME = "intentionally-left-nil/python"

NONO = shutil.which("nono-sideload") or "nono-sideload"
CONDA = shutil.which("conda")


# ---------------------------------------------------------------------------
# Fixture: isolated sandboxed Python prefix
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def python_prefix() -> Generator[Path, None, None]:
    """
    Create an isolated Python prefix for the sandboxed process to run in.

    Prefers conda (``conda create -p``); falls back to ``python3 -m venv``.
    Cleaned up after the session.
    """
    prefix = TEST_PREFIX

    if prefix.exists():
        shutil.rmtree(prefix)

    if CONDA:
        subprocess.run(
            [CONDA, "create", "-p", str(prefix),
             "--override-channels", "-c", "defaults",
             "python=3.12", "--yes", "--quiet"],
            check=True,
        )
    else:
        subprocess.run(
            [sys.executable, "-m", "venv", str(prefix)],
            check=True,
        )

    yield prefix

    try:
        shutil.rmtree(prefix)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixture: sideload the pack
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sideloaded_pack(python_prefix: Path) -> Generator[None, None, None]:
    """
    Patch ``$PREFIX`` in the source policy, sideload, then restore.

    nono-sideload records a hash of each artifact at install time and
    verifies it on every ``run``.  Patching after sideloading therefore
    fails the tamper check.  Instead we patch the source file before
    sideloading so the stored hash matches the patched content, then
    restore the original afterwards so the repo stays clean.
    """
    original = POLICY_SRC.read_text()
    POLICY_SRC.write_text(original.replace("$PREFIX", str(python_prefix)))
    try:
        subprocess.run(
            [NONO, "sideload", str(PACK_DIR)],
            check=True,
            cwd=str(REPO_ROOT),
        )
    finally:
        POLICY_SRC.write_text(original)

    yield


# ---------------------------------------------------------------------------
# Fixture: pre-create tmp dirs and expose profile name
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def patched_policy(python_prefix: Path, sideloaded_pack: None) -> Generator[str, None, None]:
    """Yield the profile name for use with ``nono-sideload run --profile``."""
    yield PROFILE_NAME


# ---------------------------------------------------------------------------
# Fixture: sandbox callable
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sandbox(patched_policy: str, python_prefix: Path):
    """
    Return a callable that runs Python code inside the nono sandbox.

    Usage::

        def test_something(sandbox):
            result = sandbox("print('hello')")
            assert result.returncode == 0
            assert "hello" in result.stdout

    Parameters accepted by the returned callable
    ---------------------------------------------
    code : str
        Python source passed to ``python -c``.  Leading indentation is
        stripped via ``textwrap.dedent``.
    extra_env : dict[str, str] | None
        Extra variables merged into the parent environment before invoking
        nono-sideload.  The sandbox's own allow_vars / set_vars apply on top.
    extra_allow : list[str] | None
        Additional ``--allow <path>`` flags.
    timeout : int
        Seconds before the subprocess is killed (default 30).
    """

    def _run(
        code: str,
        *,
        extra_env: dict[str, str] | None = None,
        extra_allow: list[str] | None = None,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        python_bin = python_prefix / "bin" / "python"

        cmd = [
            NONO, "run",
            "--profile", patched_policy,
            "--allow", str(python_prefix),
        ]
        for path in (extra_allow or []):
            cmd += ["--allow", path]
        cmd += ["--", str(python_bin), "-c", textwrap.dedent(code)]

        env = os.environ.copy()
        env["CONDA_PREFIX"] = str(python_prefix)
        env["TMPDIR"] = str(python_prefix / "tmp")
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    return _run
