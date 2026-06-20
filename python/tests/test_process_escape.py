"""
Scenario 14: Process-tree sandbox — spawning a different interpreter does not escape.

Goal: Confirm that spawning /usr/bin/python3 (or any other interpreter) from
inside the sandbox does not give that child an unsandboxed environment.  The
kernel policy covers the entire process tree; exec'ing a different binary does
not break out.

Tests:

1. ``test_os_system_escape_blocked``      — os.system() spawning another python3
2. ``test_subprocess_run_escape_blocked`` — subprocess.run() spawning python3
3. ``test_bash_shell_escape_blocked``     — subprocess.run(..., shell=True) via bash
4. ``test_execv_escape_blocked``          — os.execv() replacing the process image

Note on macOS /tmp enforcement gap: granting --allow /tmp/nono-pypack-test
implicitly promotes /tmp to writable, so /var/tmp is used as the blocked
target directory instead of /tmp.
"""

from __future__ import annotations

import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PYTHON3 = shutil.which("python3") or "/usr/bin/python3"
BASH = shutil.which("bash") or "/bin/bash"


# ---------------------------------------------------------------------------
# 1. os.system() escape blocked
# ---------------------------------------------------------------------------


def test_os_system_escape_blocked(sandbox):
    """
    A child interpreter launched via os.system() must remain inside the
    sandbox and must not be able to write to /var/tmp.

    os.system() forks a shell which exec's the command; the entire child
    process tree inherits the kernel sandbox policy.

    Expected: /var/tmp/escape1.txt does NOT exist after the call.
    """
    escape_file = Path("/var/tmp/escape1.txt")

    # Clean up any leftover from a prior run.
    escape_file.unlink(missing_ok=True)

    result = sandbox(
        f"""
import os
ret = os.system({PYTHON3!r} + " -c 'open(\\"/var/tmp/escape1.txt\\", \\"w\\").write(\\"x\\")'")
if ret == 0:
    print("OS_SYSTEM_WRITE_SUCCEEDED")
else:
    print(f"OS_SYSTEM_BLOCKED: ret={{ret}}")
""",
        timeout=30,
    )

    assert not escape_file.exists(), (
        f"Escape file {escape_file} was created — the sandbox did NOT block "
        "the write from a child interpreter spawned via os.system()!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "OS_SYSTEM_WRITE_SUCCEEDED" not in result.stdout, (
        "os.system() child claimed to write successfully — sandbox escape!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. subprocess.run() escape blocked
# ---------------------------------------------------------------------------


def test_subprocess_run_escape_blocked(sandbox):
    """
    A child interpreter launched via subprocess.run() must remain inside the
    sandbox and must not be able to write to /var/tmp.

    subprocess.run() forks and exec's the target binary directly; the new
    process still inherits the kernel sandbox policy.

    Expected: /var/tmp/escape2.txt does NOT exist after the call.
    """
    escape_file = Path("/var/tmp/escape2.txt")

    # Clean up any leftover from a prior run.
    escape_file.unlink(missing_ok=True)

    result = sandbox(
        f"""
import subprocess
r = subprocess.run(
    [{PYTHON3!r}, "-c", "open('/var/tmp/escape2.txt', 'w').write('x')"],
    capture_output=True, text=True, timeout=10
)
if r.returncode == 0:
    print("SUBPROCESS_WRITE_SUCCEEDED")
else:
    print(f"SUBPROCESS_BLOCKED: rc={{r.returncode}}")
""",
        timeout=30,
    )

    assert not escape_file.exists(), (
        f"Escape file {escape_file} was created — the sandbox did NOT block "
        "the write from a child interpreter spawned via subprocess.run()!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "SUBPROCESS_WRITE_SUCCEEDED" not in result.stdout, (
        "subprocess.run() child claimed to write successfully — sandbox escape!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. bash shell escape blocked
# ---------------------------------------------------------------------------


def test_bash_shell_escape_blocked(sandbox):
    """
    A child interpreter launched via bash (subprocess.run(..., shell=True))
    must remain inside the sandbox and must not be able to write to /var/tmp.

    shell=True routes through the system shell (bash/sh), which then exec's
    python3.  The entire chain stays under the kernel sandbox policy.

    Expected: /var/tmp/escape3.txt does NOT exist after the call.
    """
    escape_file = Path("/var/tmp/escape3.txt")

    # Clean up any leftover from a prior run.
    escape_file.unlink(missing_ok=True)

    result = sandbox(
        f"""
import subprocess
cmd = {PYTHON3!r} + " -c \\"open('/var/tmp/escape3.txt', 'w').write('x')\\""
r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    print("BASH_WRITE_SUCCEEDED")
else:
    print(f"BASH_BLOCKED: rc={{r.returncode}}")
""",
        timeout=30,
    )

    assert not escape_file.exists(), (
        f"Escape file {escape_file} was created — the sandbox did NOT block "
        "the write from a child interpreter spawned via bash shell!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "BASH_WRITE_SUCCEEDED" not in result.stdout, (
        "bash shell child claimed to write successfully — sandbox escape!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 4. os.execv() escape blocked
# ---------------------------------------------------------------------------


def test_execv_escape_blocked(sandbox):
    """
    A child interpreter launched via os.execv() (replacing the process image)
    must remain inside the sandbox and must not be able to write to /var/tmp.

    We run os.execv() in a subprocess so our test process survives the exec
    call.  The exec'd binary still executes under the original process's kernel
    sandbox policy.

    Expected: /var/tmp/escape4.txt does NOT exist after the call.
    """
    escape_file = Path("/var/tmp/escape4.txt")

    # Clean up any leftover from a prior run.
    escape_file.unlink(missing_ok=True)

    result = sandbox(
        f"""
import subprocess, sys
r = subprocess.run(
    [sys.executable, "-c",
     "import os; os.execv({PYTHON3!r}, "
     "[{PYTHON3!r}, '-c', \\"open('/var/tmp/escape4.txt','w').write('x')\\"])"],
    capture_output=True, text=True, timeout=10
)
if r.returncode == 0:
    print("EXECV_WRITE_SUCCEEDED")
else:
    print(f"EXECV_BLOCKED: rc={{r.returncode}}")
""",
        timeout=30,
    )

    assert not escape_file.exists(), (
        f"Escape file {escape_file} was created — the sandbox did NOT block "
        "the write from a child interpreter spawned via os.execv()!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "EXECV_WRITE_SUCCEEDED" not in result.stdout, (
        "os.execv() child claimed to write successfully — sandbox escape!\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
