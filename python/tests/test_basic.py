"""
Basic smoke tests for the nono python pack.

These two tests cover the most fundamental "works / doesn't work" axis:

1. ``test_stdlib_works``   — the sandbox allows normal Python execution.
2. ``test_tmp_write_blocked`` — the sandbox blocks writes outside the prefix.

Both rely on the ``sandbox`` fixture from conftest.py, which handles:
  - creating the isolated conda/venv prefix
  - sideloading the pack
  - writing the patched policy (``$PREFIX`` expanded to the real path)
  - wiring up the ``nono-sideload run`` invocation
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. "works" — sandbox allows normal Python execution
# ---------------------------------------------------------------------------


def test_stdlib_works(sandbox):
    """
    The sandbox must allow a sandboxed Python process to import the standard
    library and print output.

    This is the minimum bar: if this test fails, nothing else matters.
    """
    result = sandbox(
        """
        import json, csv, pathlib, hashlib, urllib.parse, datetime, re, os, sys
        print("STDLIB_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "STDLIB_OK" in result.stdout, (
        f"Marker not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 1b. "works" — C-extension stdlib imports work inside the sandbox
# ---------------------------------------------------------------------------


def test_cext_imports(sandbox):
    """
    The sandbox must allow importing C-extension stdlib modules that require
    access to shared libraries (e.g. _json, _csv, _hashlib).

    These modules are backed by .so files inside the prefix and exercise
    shared-library loading within the sandbox.
    """
    result = sandbox(
        """
        import _json, _csv, _hashlib
        print("CEXT_OK")
        """
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "CEXT_OK" in result.stdout, (
        f"Marker not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. "doesn't work" — sandbox blocks writes to /tmp
# ---------------------------------------------------------------------------


def test_tmp_write_blocked(sandbox):
    """
    The sandbox must deny write access to ``/tmp`` (outside the prefix).

    The profile grants ``--allow $PREFIX`` and redirects ``TMPDIR`` to
    ``$PREFIX/tmp``, but plain ``/tmp`` is *not* in the allow list.  A
    ``PermissionError`` (or similar OS-level error) must be raised.

    We check two things:
    - The Python process exits non-zero (the write attempt was not silently
      swallowed).
    - The sentinel file was NOT created (the kernel actually blocked the
      syscall; the process didn't just report an error and create it anyway).
    """
    import os
    from pathlib import Path

    sentinel = "/var/tmp/nono-pypack-escape-test.txt"

    # Make sure any leftover from a previous run is gone.
    try:
        Path(sentinel).unlink()
    except FileNotFoundError:
        pass

    result = sandbox(
        f"""
        try:
            open({sentinel!r}, "w").write("escaped")
            print("WRITE_SUCCEEDED")   # should NOT appear
        except (PermissionError, OSError) as e:
            print(f"WRITE_BLOCKED: {{e}}")
        """
    )

    # The process itself should exit 0 (the exception was caught), but the
    # sentinel file must not exist.
    assert "WRITE_SUCCEEDED" not in result.stdout, (
        "Sandbox did NOT block the write — the escape file was created!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "WRITE_BLOCKED" in result.stdout, (
        f"Expected WRITE_BLOCKED marker.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert not Path(sentinel).exists(), (
        f"Sentinel file {sentinel!r} exists on the host — sandbox did not "
        "block the write at the kernel level!"
    )
