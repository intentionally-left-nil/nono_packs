"""
Scenario 2: Working-directory read and write.

Confirms that ``workdir: readwrite`` grants the sandboxed process access to
the current working directory.

Tests:

1. ``test_cwd_write_read_unlink`` — write a file in CWD, read it back, delete it.
2. ``test_cwd_read_existing``     — create a file outside the sandbox in CWD,
                                    confirm it is readable from inside.
"""

from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Write, read back, and delete a file inside CWD
# ---------------------------------------------------------------------------


def test_cwd_write_read_unlink(sandbox):
    """
    The sandbox must allow the sandboxed process to write a file into CWD,
    read it back, and delete it.

    The ``workdir: readwrite`` policy directive should grant full read/write
    access to whatever directory the process has as its CWD at runtime.
    We pass the CWD explicitly via ``extra_allow`` because nono skips the CWD
    prompt in non-interactive mode (``--allow-cwd`` is not set by the harness).
    """
    cwd = os.getcwd()
    result = sandbox(
        """
        import os
        p = os.path.join(os.getcwd(), "sandbox_write_test.txt")
        open(p, "w").write("hello")
        assert open(p).read() == "hello", "file content mismatch"
        os.unlink(p)
        print("WRITE_CWD_OK")
        """,
        extra_allow=[cwd],
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "WRITE_CWD_OK" in result.stdout, (
        f"Marker WRITE_CWD_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. Read an existing file from CWD (created outside the sandbox)
# ---------------------------------------------------------------------------


def test_cwd_read_existing(sandbox):
    """
    A file created by the pytest process (outside the sandbox) in CWD must be
    readable from inside the sandbox.

    We create a sentinel file in ``os.getcwd()`` (the pytest process's CWD,
    which is the same directory the sandboxed process will inherit), then
    confirm the sandbox can open and read it.  The file is cleaned up
    unconditionally in a ``finally`` block.
    """
    sentinel = Path(os.getcwd()) / "sandbox_read_existing_test.txt"
    sentinel_content = "sentinel-content-42"

    sentinel.write_text(sentinel_content)
    try:
        result = sandbox(
            f"""
            p = {str(sentinel)!r}
            content = open(p).read()
            assert content == {sentinel_content!r}, f"unexpected content: {{content!r}}"
            print("READ_EXISTING_OK")
            """,
            extra_allow=[str(sentinel.parent)],
        )
    finally:
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "READ_EXISTING_OK" in result.stdout, (
        f"Marker READ_EXISTING_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
