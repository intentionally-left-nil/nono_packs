"""
Scenario 12: Filesystem write/overwrite/delete/copy outside CWD all blocked.

Confirms that four fundamental filesystem attack vectors are each independently
blocked by the sandbox:

1. Write a new file to an external directory          → PermissionError
2. Overwrite an existing file in an external directory → PermissionError
3. Delete a file in an external directory             → PermissionError
4. shutil.copy to an external directory               → PermissionError

Note on macOS /tmp enforcement gap: granting --allow /tmp/nono-pypack-test
implicitly promotes /tmp to writable, so /var/tmp is used as the blocked
target directory instead of /tmp.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Scenario 12: all four write attack vectors blocked
# ---------------------------------------------------------------------------


def test_writes_outside_cwd_blocked(sandbox):
    """
    All four filesystem attack vectors must be blocked when targeting a
    directory outside CWD (/var/tmp, which is never in the allow list).

    Setup:
    - Create two sentinel files in /var/tmp from outside the sandbox.

    Inside one sandboxed invocation:
    - Try to write a new file to /var/tmp          → catch PermissionError, print WRITE_BLOCKED
    - Try to overwrite sentinel1 in /var/tmp       → catch PermissionError, print OVERWRITE_BLOCKED
    - Try to unlink sentinel2 in /var/tmp          → catch PermissionError, print DELETE_BLOCKED
    - Try to shutil.copy into /var/tmp             → catch PermissionError, print COPY_BLOCKED

    Post-sandbox assertions (from outside):
    - All four *_BLOCKED markers appear in stdout.
    - Both sentinel files still exist and have original content.
    - The "new file" and "stolen script" targets do not exist.
    """
    sentinel1 = Path("/var/tmp/nono-pypack-sentinel1.txt")
    sentinel2 = Path("/var/tmp/nono-pypack-sentinel2.txt")
    new_file = Path("/var/tmp/nono-pypack-new-file.txt")
    stolen = Path("/var/tmp/nono-pypack-stolen-script.py")

    # Clean up any leftovers from prior runs.
    for p in (sentinel1, sentinel2, new_file, stolen):
        try:
            p.unlink()
        except FileNotFoundError:
            pass

    # Create sentinel files outside the sandbox.
    sentinel1.write_text("sentinel\n")
    sentinel2.write_text("sentinel2\n")

    # Use a known readable file as the copy source — __file__ inside
    # `python -c` is unreliable; the prefix python binary is always present.
    copy_source = str(sandbox._prefix / "bin" / "python")

    # Use a real temp dir as CWD so the sandbox has a legitimate CWD.
    with tempfile.TemporaryDirectory() as cwd:
        result = sandbox(
            f"""
import pathlib
import shutil

# --- 1. Write a new file ---
try:
    open("/var/tmp/nono-pypack-new-file.txt", "w").write("escaped")
    print("WRITE_SUCCEEDED")
except (PermissionError, OSError):
    print("WRITE_BLOCKED")

# --- 2. Overwrite an existing file ---
try:
    open("/var/tmp/nono-pypack-sentinel1.txt", "w").write("overwritten")
    print("OVERWRITE_SUCCEEDED")
except (PermissionError, OSError):
    print("OVERWRITE_BLOCKED")

# --- 3. Delete a file ---
try:
    pathlib.Path("/var/tmp/nono-pypack-sentinel2.txt").unlink()
    print("DELETE_SUCCEEDED")
except (PermissionError, OSError):
    print("DELETE_BLOCKED")

# --- 4. shutil.copy to /var/tmp ---
try:
    shutil.copy({copy_source!r}, "/var/tmp/nono-pypack-stolen-script.py")
    print("COPY_SUCCEEDED")
except (PermissionError, OSError):
    print("COPY_BLOCKED")

print("ALL_ATTEMPTS_DONE")
""",
            extra_allow=[cwd],
        )

    # --- Verify all four attack vectors were blocked ---
    assert "WRITE_BLOCKED" in result.stdout, (
        "Sandbox did NOT block new-file write to /var/tmp.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "OVERWRITE_BLOCKED" in result.stdout, (
        "Sandbox did NOT block overwrite of existing file in /var/tmp.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "DELETE_BLOCKED" in result.stdout, (
        "Sandbox did NOT block unlink in /var/tmp.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "COPY_BLOCKED" in result.stdout, (
        "Sandbox did NOT block shutil.copy to /var/tmp.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )

    # None of the "SUCCEEDED" markers should appear.
    assert "WRITE_SUCCEEDED" not in result.stdout, (
        "Write to /var/tmp was not blocked!\n"
        f"stdout: {result.stdout!r}"
    )
    assert "OVERWRITE_SUCCEEDED" not in result.stdout, (
        "Overwrite in /var/tmp was not blocked!\n"
        f"stdout: {result.stdout!r}"
    )
    assert "DELETE_SUCCEEDED" not in result.stdout, (
        "Delete in /var/tmp was not blocked!\n"
        f"stdout: {result.stdout!r}"
    )
    assert "COPY_SUCCEEDED" not in result.stdout, (
        "shutil.copy to /var/tmp was not blocked!\n"
        f"stdout: {result.stdout!r}"
    )

    # --- Sentinel files must be intact ---
    assert sentinel1.exists(), (
        f"Sentinel file {sentinel1} was deleted by the sandbox!"
    )
    assert sentinel1.read_text() == "sentinel\n", (
        f"Sentinel file {sentinel1} was modified by the sandbox! "
        f"Content: {sentinel1.read_text()!r}"
    )
    assert sentinel2.exists(), (
        f"Sentinel file {sentinel2} was deleted by the sandbox!"
    )
    assert sentinel2.read_text() == "sentinel2\n", (
        f"Sentinel file {sentinel2} was modified by the sandbox! "
        f"Content: {sentinel2.read_text()!r}"
    )

    # --- New-file and stolen-script targets must not exist ---
    assert not new_file.exists(), (
        f"New file {new_file} was created — sandbox did NOT block the write!"
    )
    assert not stolen.exists(), (
        f"Stolen script {stolen} was created — sandbox did NOT block shutil.copy!"
    )

    # Clean up sentinels.
    sentinel1.unlink(missing_ok=True)
    sentinel2.unlink(missing_ok=True)
