"""
Scenario 4: Environment variable filtering — vars that should be stripped.

Confirms that env vars not in ``allow_vars`` are stripped before the sandboxed
process sees them.

Tests:

1. ``test_secret_key_stripped``  — SECRET_KEY=hunter2 set in parent is absent.
2. ``test_custom_var_stripped``  — MY_CUSTOM_VAR=canary set in parent is absent.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. SECRET_KEY must be stripped
# ---------------------------------------------------------------------------


def test_secret_key_stripped(sandbox):
    """
    SECRET_KEY is not in allow_vars, so it must be absent inside the sandbox
    even when set in the parent environment via extra_env.
    """
    result = sandbox(
        """
        import os
        assert "SECRET_KEY" not in os.environ, f"leaked: {os.environ['SECRET_KEY']!r}"
        print("SECRET_STRIPPED_OK")
        """,
        extra_env={"SECRET_KEY": "hunter2"},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "SECRET_STRIPPED_OK" in result.stdout, (
        f"Marker SECRET_STRIPPED_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. MY_CUSTOM_VAR must be stripped
# ---------------------------------------------------------------------------


def test_custom_var_stripped(sandbox):
    """
    MY_CUSTOM_VAR is not in allow_vars, so it must be absent inside the
    sandbox even when set in the parent environment via extra_env.
    """
    result = sandbox(
        """
        import os
        assert "MY_CUSTOM_VAR" not in os.environ, f"leaked: {os.environ['MY_CUSTOM_VAR']!r}"
        print("CUSTOM_VAR_STRIPPED_OK")
        """,
        extra_env={"MY_CUSTOM_VAR": "canary"},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "CUSTOM_VAR_STRIPPED_OK" in result.stdout, (
        f"Marker CUSTOM_VAR_STRIPPED_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
