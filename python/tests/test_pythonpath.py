"""
Scenario 13: PYTHONPATH injection has no effect.

Goal: PYTHONPATH is unconditionally stripped by nono regardless of
allow_vars. Confirm it is not visible inside the sandbox even when set
in the parent shell.

Tests:

1. ``test_pythonpath_stripped`` — PYTHONPATH=/tmp/evil-modules set in parent
   is absent inside the sandbox.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 13. PYTHONPATH must be stripped unconditionally
# ---------------------------------------------------------------------------


def test_pythonpath_stripped(sandbox):
    """
    PYTHONPATH is not in allow_vars and must never leak into the sandbox,
    even when explicitly set in the parent environment via extra_env.

    Sets PYTHONPATH=/tmp/evil-modules in the invoking environment and asserts
    the variable is absent inside the sandboxed process.
    """
    result = sandbox(
        """
        import os
        assert "PYTHONPATH" not in os.environ, \
            f"PYTHONPATH leaked: {os.environ['PYTHONPATH']!r}"
        print("PYTHONPATH_STRIPPED_OK")
        """,
        extra_env={"PYTHONPATH": "/tmp/evil-modules"},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "PYTHONPATH_STRIPPED_OK" in result.stdout, (
        f"Marker PYTHONPATH_STRIPPED_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
