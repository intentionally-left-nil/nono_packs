"""
Scenario 8: Subprocess sandbox propagation.

Goal: Confirm that a child Python process spawned by ``subprocess`` inherits
the sandbox and that internal env vars are cleaned up correctly.

Tests:

1. ``test_child_subprocess_runs``     — child spawned via subprocess can import
                                        stdlib and run normally.
2. ``test_pybox_argv0_absent_in_child`` — PYBOX_ORIGINAL_ARGV0 is not visible
                                          in the child's environment.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. Child process can import stdlib and run normally
# ---------------------------------------------------------------------------


def test_child_subprocess_runs(sandbox):
    """
    A child Python process spawned via subprocess must be able to import stdlib
    and run normally inside the sandbox.

    The sandbox policy covers the entire process tree, so the child inherits the
    same allow-list as the parent. A failure here would indicate that the child
    process cannot access the prefix or stdlib.

    Expected: exits 0, prints SUBPROCESS_OK.
    """
    result = sandbox(
        """
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-c", "import json; print('CHILD_OK')"],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 0, result.stderr
        assert "CHILD_OK" in result.stdout
        print("SUBPROCESS_OK")
        """,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "SUBPROCESS_OK" in result.stdout, (
        f"Marker SUBPROCESS_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. PYBOX_ORIGINAL_ARGV0 is not visible in the child's environment
# ---------------------------------------------------------------------------


def test_pybox_argv0_absent_in_child(sandbox):
    """
    The launcher-internal variable PYBOX_ORIGINAL_ARGV0 must not leak into
    child processes spawned via subprocess.

    The launcher strips this variable before handing control to the user script,
    but we verify it is absent from the child's environment to catch any
    regression where stripping is skipped or deferred past the exec boundary.

    Expected: exits 0, prints ARGV0_ABSENT_OK.
    """
    result = sandbox(
        """
        import subprocess, sys, os
        result = subprocess.run(
            [sys.executable, "-c",
             "import os; print(os.environ.get('PYBOX_ORIGINAL_ARGV0', '__ABSENT__'))"],
            capture_output=True, text=True, timeout=10
        )
        assert "__ABSENT__" in result.stdout, f"leaked: {result.stdout.strip()!r}"
        print("ARGV0_ABSENT_OK")
        """,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "ARGV0_ABSENT_OK" in result.stdout, (
        f"Marker ARGV0_ABSENT_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
