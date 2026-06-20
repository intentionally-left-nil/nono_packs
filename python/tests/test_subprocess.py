"""
Scenario 8: Subprocess sandbox propagation.

Goal: Confirm that a child Python process spawned by ``subprocess`` inherits
the sandbox and that internal env vars are cleaned up correctly.

Tests:

1. ``test_child_subprocess_runs`` — child spawned via subprocess can import
                                    stdlib and run normally.
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
