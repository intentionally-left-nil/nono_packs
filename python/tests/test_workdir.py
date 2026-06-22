"""
Scenario 2: Working-directory read and write via explicit --allow.

Confirms that passing CWD explicitly via ``extra_allow`` (i.e. ``--allow
<cwd>`` on the nono-sideload command line) grants the sandboxed process access
to the current working directory.

The profile does NOT set ``workdir: readwrite`` — CWD access is opt-in and
must be granted explicitly by the caller. These tests verify that the
explicit-allow path works correctly.

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
    When CWD is explicitly allowed via ``extra_allow``, the sandbox must
    permit writing a file into CWD, reading it back, and deleting it.

    The profile does not grant CWD access; ``extra_allow=[cwd]`` translates
    to ``--allow <cwd>`` on the nono-sideload command line, which is the
    intended mechanism for callers that need working-directory access.
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
    readable from inside the sandbox when CWD is explicitly allowed.

    We create a sentinel file in ``os.getcwd()`` (the pytest process's CWD,
    which is the same directory the sandboxed process will inherit), then
    confirm the sandbox can open and read it via ``extra_allow=[str(sentinel.parent)]``.
    The file is cleaned up unconditionally in a ``finally`` block.
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
