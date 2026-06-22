"""
Scenario 18: PYTHON_HISTORY is redirected inside the sandbox.

The CPython REPL writes readline history to ``~/.python_history`` on exit.
Inside the sandbox ``$HOME`` is read-only, so that write fails.  Python 3.13+
emits a ``UserWarning`` about it; earlier versions silently swallow the error.

The fix: policy.json sets ``PYTHON_HISTORY=$PREFIX/tmp/.python_history`` via
``set_vars``, redirecting the history file to the writable prefix.

Tests:

1. ``test_python_history_home_write_blocked`` — confirms that writing to
   ``~/.python_history`` is blocked inside the sandbox.  This is the root
   cause of the warning and proves the test can detect the underlying condition
   regardless of Python version.

2. ``test_python_history_env_var_set`` — confirms that ``PYTHON_HISTORY`` is
   injected (via ``set_vars``) and points inside ``$PREFIX``.

3. ``test_python_history_prefix_path_writable`` — confirms that the path
   ``PYTHON_HISTORY`` points to is actually writable inside the sandbox,
   meaning the REPL can successfully save history.
"""

from __future__ import annotations

import os
from pathlib import Path

TEST_PREFIX = Path("/tmp/nono-pypack-test")


# ---------------------------------------------------------------------------
# 1. ~/.python_history write is blocked (root cause of the warning)
# ---------------------------------------------------------------------------


def test_python_history_home_write_blocked(sandbox):
    """
    Attempting to open ``~/.python_history`` for writing inside the sandbox
    must raise ``PermissionError``.

    This confirms the condition that causes the UserWarning in Python 3.13+
    REPLs, independently of Python version.
    """
    result = sandbox(
        """
        import os
        history_path = os.path.expanduser("~/.python_history")
        try:
            open(history_path, "a").close()
            print("WRITE_ALLOWED")
        except PermissionError:
            print("WRITE_BLOCKED")
        """
    )

    assert result.returncode == 0, (
        f"Script exited {result.returncode}.\n"
        f"stderr: {result.stderr!r}"
    )
    assert "WRITE_BLOCKED" in result.stdout, (
        f"Expected ~/.python_history write to be blocked inside the sandbox, "
        f"but it succeeded.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. PYTHON_HISTORY is injected via set_vars
# ---------------------------------------------------------------------------


def test_python_history_env_var_set(sandbox):
    """
    ``PYTHON_HISTORY`` must be set inside the sandbox (injected by
    ``set_vars``) and must point to a path inside ``$PREFIX``.
    """
    result = sandbox(
        f"""
        import os
        val = os.environ.get("PYTHON_HISTORY", "")
        assert val, "PYTHON_HISTORY is not set"
        assert val.startswith({str(TEST_PREFIX)!r}), (
            f"PYTHON_HISTORY {{val!r}} does not start with PREFIX"
        )
        print("PYTHON_HISTORY_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "PYTHON_HISTORY_OK" in result.stdout, (
        f"PYTHON_HISTORY check failed.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. The PYTHON_HISTORY path is writable inside the sandbox
# ---------------------------------------------------------------------------


def test_python_history_prefix_path_writable(sandbox):
    """
    The path that ``PYTHON_HISTORY`` points to must be writable inside the
    sandbox.  This confirms the REPL can actually save history without error.
    """
    result = sandbox(
        """
        import os
        history_path = os.environ.get("PYTHON_HISTORY", "")
        assert history_path, "PYTHON_HISTORY is not set"
        # Ensure parent directory exists (set_vars points to $PREFIX/tmp/...)
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        try:
            with open(history_path, "a") as f:
                f.write("")
            print("HISTORY_WRITABLE")
        except PermissionError as e:
            print(f"PERMISSION_DENIED: {e}")
        """
    )

    assert result.returncode == 0, (
        f"Script exited {result.returncode}.\n"
        f"stderr: {result.stderr!r}"
    )
    assert "HISTORY_WRITABLE" in result.stdout, (
        f"Expected PYTHON_HISTORY path to be writable inside the sandbox.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
