"""
Scenario 5: Environment variable filtering — vars that should pass through.

Confirms that vars in ``allow_vars`` survive the exec boundary.

Tests:

1. ``test_conda_prefix_passthrough``       — CONDA_PREFIX is visible (harness sets it).
2. ``test_virtual_env_passthrough``        — VIRTUAL_ENV passes through when set.
3. ``test_tmpdir_passthrough``             — TMPDIR passes through (harness sets it).
4. ``test_pythonpycacheprefix_passthrough`` — PYTHONPYCACHEPREFIX passes through.
5. ``test_mamba_wildcard_passthrough``     — MAMBA_* wildcard: MAMBA_ROOT_PREFIX passes through.
"""

from __future__ import annotations

TEST_PREFIX = "/tmp/nono-pypack-test"


# ---------------------------------------------------------------------------
# 1. CONDA_PREFIX must pass through
# ---------------------------------------------------------------------------


def test_conda_prefix_passthrough(sandbox):
    """
    CONDA_PREFIX is set to the test prefix by the harness automatically.
    It must be visible inside the sandbox because it is in allow_vars.
    """
    result = sandbox(
        f"""
        import os
        assert os.environ.get("CONDA_PREFIX") == {TEST_PREFIX!r}, \\
            os.environ.get("CONDA_PREFIX")
        print("CONDA_PREFIX_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "CONDA_PREFIX_OK" in result.stdout, (
        f"Marker CONDA_PREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. VIRTUAL_ENV must pass through
# ---------------------------------------------------------------------------


def test_virtual_env_passthrough(sandbox):
    """
    VIRTUAL_ENV is in allow_vars; when set in the parent environment it must
    be visible inside the sandbox.
    """
    result = sandbox(
        """
        import os
        assert os.environ.get("VIRTUAL_ENV") == "/tmp/pybox-test-venv", \\
            os.environ.get("VIRTUAL_ENV")
        print("VIRTUAL_ENV_OK")
        """,
        extra_env={"VIRTUAL_ENV": "/tmp/pybox-test-venv"},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "VIRTUAL_ENV_OK" in result.stdout, (
        f"Marker VIRTUAL_ENV_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. TMPDIR must pass through
# ---------------------------------------------------------------------------


def test_tmpdir_passthrough(sandbox):
    """
    TMPDIR is set to $PREFIX/tmp by the harness automatically.
    It must be visible inside the sandbox because it is in allow_vars.
    """
    result = sandbox(
        """
        import os
        assert "TMPDIR" in os.environ
        print("TMPDIR_PASSED_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "TMPDIR_PASSED_OK" in result.stdout, (
        f"Marker TMPDIR_PASSED_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 4. PYTHONPYCACHEPREFIX must pass through
# ---------------------------------------------------------------------------


def test_pythonpycacheprefix_passthrough(sandbox):
    """
    PYTHONPYCACHEPREFIX is in allow_vars; when set explicitly in the parent
    environment it must be visible inside the sandbox.
    """
    pycache_dir = f"{TEST_PREFIX}/__pycache__"
    result = sandbox(
        f"""
        import os
        assert os.environ.get("PYTHONPYCACHEPREFIX") == {pycache_dir!r}, \\
            os.environ.get("PYTHONPYCACHEPREFIX")
        print("PYTHONPYCACHEPREFIX_OK")
        """,
        extra_env={"PYTHONPYCACHEPREFIX": pycache_dir},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "PYTHONPYCACHEPREFIX_OK" in result.stdout, (
        f"Marker PYTHONPYCACHEPREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 5. MAMBA_* wildcard — MAMBA_ROOT_PREFIX must pass through
# ---------------------------------------------------------------------------


def test_mamba_wildcard_passthrough(sandbox):
    """
    MAMBA_ROOT_PREFIX is matched by the ``MAMBA_*`` wildcard in allow_vars;
    when set in the parent environment it must be visible inside the sandbox.
    """
    result = sandbox(
        """
        import os
        assert os.environ.get("MAMBA_ROOT_PREFIX") == "/opt/mamba", \\
            os.environ.get("MAMBA_ROOT_PREFIX")
        print("MAMBA_ROOT_PREFIX_OK")
        """,
        extra_env={"MAMBA_ROOT_PREFIX": "/opt/mamba"},
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "MAMBA_ROOT_PREFIX_OK" in result.stdout, (
        f"Marker MAMBA_ROOT_PREFIX_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
