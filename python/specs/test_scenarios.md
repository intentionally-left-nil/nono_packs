# Python Pack — Test Scenarios

This document describes the test scenarios for the `python` nono pack profile.
Tests are run against the sideloaded pack using the standard `nono-sideload`
binary — no feedstock installation is required.

---

## Setup

### Create a test prefix

Tests require a Python prefix to stand in for the conda environment. The
preferred approach is a real conda environment created at an explicit path with
`-p`, which is easy to isolate and clean up. A plain venv is an acceptable
fallback when conda is not available.

**Preferred — conda environment:**
```sh
conda create -p /tmp/pybox-test python=3.12 --yes
export PREFIX=/tmp/pybox-test
```

**Fallback — plain venv:**
```sh
python3 -m venv /tmp/pybox-test
export PREFIX=/tmp/pybox-test
```

Throughout this document `$PREFIX` refers to whichever prefix was chosen.
Cleanup is the same in both cases: `rm -rf /tmp/pybox-test`.

### Install test packages

Some scenarios require third-party packages. Install them into the test prefix
before running those scenarios.

**Preferred — conda:**
```sh
conda install -p $PREFIX requests fastapi uvicorn jupyter ipykernel pandas matplotlib --yes
```

**Fallback — pip into the prefix:**
```sh
$PREFIX/bin/pip install requests fastapi uvicorn jupyter ipykernel pandas matplotlib
```

### Prepare the profile for testing

The pack profile uses `$PREFIX` as a build-var (see `docs/pack_authoring.md`
and `docs/sandbox-adr.md` ADR-8). Because we are sideloading rather than going
through the feedstock launcher, `$PREFIX` is not expanded automatically. Before
running tests, substitute the actual prefix path into a working copy of the
profile:

```sh
cp python/policy.json /tmp/pybox-test-policy.json
sed -i "s|\$PREFIX|$PREFIX|g" /tmp/pybox-test-policy.json
```

### Sideload the pack

```sh
nono-sideload sideload ./python
```

### Invocation pattern

All tests use `nono-sideload run` with the modified profile and an explicit
`--allow` for the prefix:

```sh
nono-sideload run --profile /tmp/pybox-test-policy.json \
    --allow $PREFIX \
    -- $PREFIX/bin/python -c "<code>"
```

For venv tests that need `argv[0]` to be a symlink path rather than the real
binary, invoke the unversioned `python` symlink (`$PREFIX/bin/python`) rather
than the real binary directly — this mirrors how the feedstock launcher
preserves `argv[0]` for `pyvenv.cfg` detection.

---

## Test categories

### 1. Standard library imports

**Goal:** Confirm the sandbox grants sufficient read access for CPython to
import the full standard library.

**Tests:**

- Import a representative spread of stdlib modules:
  ```python
  import json, csv, pathlib, hashlib, urllib.parse, datetime, re, os, sys
  print("STDLIB_OK")
  ```
  Expected: exits 0, prints `STDLIB_OK`.

- Import a C-extension stdlib module (exercises shared-library access):
  ```python
  import _json, _csv, _hashlib
  print("CEXT_OK")
  ```
  Expected: exits 0, prints `CEXT_OK`.

---

### 2. Working-directory read and write

**Goal:** Confirm `workdir: readwrite` grants the sandboxed process access to
the current working directory.

**Tests:**

- Write a file in CWD, read it back:
  ```python
  import os
  p = os.path.join(os.getcwd(), "sandbox_write_test.txt")
  open(p, "w").write("hello")
  assert open(p).read() == "hello"
  os.unlink(p)
  print("WRITE_CWD_OK")
  ```
  Expected: exits 0, prints `WRITE_CWD_OK`.

- Read an existing file in CWD:
  Create a file in the test working directory before invoking the sandbox, then
  confirm it is readable from inside.
  Expected: exits 0.

---

### 3. `$PREFIX` access

**Goal:** Confirm that `--allow $PREFIX` (manually expanded in the test profile)
grants the Python process access to the venv's stdlib, site-packages, and shared
libraries. This is a structural test of the profile's `filesystem.allow` section.

**Tests:**

- Confirm `sys.prefix` resolves under the test prefix:
  ```python
  import sys, os
  expected = os.path.realpath(os.environ["CONDA_PREFIX"])
  actual = os.path.realpath(sys.prefix)
  assert actual == expected, f"got {actual!r}"
  print("PREFIX_OK")
  ```
  The test harness must set `CONDA_PREFIX=$PREFIX` before invoking
  `nono-sideload run`. Expected: exits 0, prints `PREFIX_OK`.

- Write to `$PREFIX/tmp` (the redirected TMPDIR):
  ```python
  import tempfile, os
  assert os.environ["TMPDIR"].startswith(os.environ["CONDA_PREFIX"])
  with tempfile.NamedTemporaryFile(delete=False) as f:
      f.write(b"x")
  print("TMPDIR_OK")
  ```
  Expected: exits 0, prints `TMPDIR_OK`.
  Note: the test harness must pre-create `$PREFIX/tmp/` and set
  `TMPDIR=$PREFIX/tmp` in the environment before invoking `nono-sideload run`,
  since this is normally the launcher's job.

---

### 4. Environment variable filtering — vars that should be stripped

**Goal:** Confirm that env vars not in `allow_vars` are stripped before the
sandboxed process sees them.

**Tests:**

- A secret set in the parent shell is absent inside the sandbox:
  Set `SECRET_KEY=hunter2` in the invoking shell, then:
  ```python
  import os
  assert "SECRET_KEY" not in os.environ, f"leaked: {os.environ['SECRET_KEY']!r}"
  print("SECRET_STRIPPED_OK")
  ```
  Expected: exits 0, prints `SECRET_STRIPPED_OK`.

- A generic `MY_CUSTOM_VAR` not in `allow_vars` is absent:
  Same pattern as above with `MY_CUSTOM_VAR=canary`.
  Expected: stripped, prints confirmation.

---

### 5. Environment variable filtering — vars that should pass through

**Goal:** Confirm that vars in `allow_vars` survive the exec boundary.

**Tests:**

- `CONDA_PREFIX` is visible inside the sandbox (set it explicitly in the parent
  environment):
  ```python
  import os
  assert os.environ.get("CONDA_PREFIX") == "/tmp/pybox-test-venv", \
      os.environ.get("CONDA_PREFIX")
  print("CONDA_PREFIX_OK")
  ```
  Expected: exits 0, prints `CONDA_PREFIX_OK`.

- `VIRTUAL_ENV` passes through:
  Same pattern; set `VIRTUAL_ENV=/tmp/pybox-test-venv` in parent.
  Expected: visible inside sandbox.

- `TMPDIR` passes through (set to `$PREFIX/tmp` by the test harness):
  ```python
  import os
  assert "TMPDIR" in os.environ
  print("TMPDIR_PASSED_OK")
  ```
  Expected: exits 0, prints `TMPDIR_PASSED_OK`.

- `PYTHONPYCACHEPREFIX` passes through:
  Set `PYTHONPYCACHEPREFIX=/tmp/pybox-test-venv/__pycache__` in parent.
  Expected: visible inside sandbox.

- A wildcard-matched var passes through: set `MAMBA_ROOT_PREFIX=/opt/mamba`
  in parent (matched by `MAMBA_*`):
  Expected: visible inside sandbox.

---

### 6. Network access

**Goal:** Confirm outbound network is permitted by the profile.

**Tests:**

- Make an HTTPS request to a well-known public endpoint:
  ```python
  import urllib.request
  with urllib.request.urlopen("https://example.com", timeout=10) as r:
      assert r.status == 200
  print("NETWORK_OK")
  ```
  Expected: exits 0, prints `NETWORK_OK`.

---

### 7. Multiprocessing (`ipc_mode: full`)

**Goal:** Confirm that `security.ipc_mode: full` is set correctly and that
Python's `multiprocessing` module works inside the sandbox. This is a known
failure mode when `ipc_mode` is missing or set to `shared_memory_only`.

**Tests:**

- `multiprocessing.Pool` with `fork` start method:
  ```python
  import multiprocessing, time
  def sq(x): return x * x
  start = time.monotonic()
  with multiprocessing.get_context("fork").Pool(4) as p:
      result = p.map(sq, range(8))
  assert result == [0, 1, 4, 9, 16, 25, 36, 49], result
  assert time.monotonic() - start < 5.0, "pool took too long"
  print("MULTIPROCESSING_OK")
  ```
  Expected: exits 0, prints `MULTIPROCESSING_OK`, completes in under 5 seconds.

- `multiprocessing.Queue` round-trip (exercises shared-memory and IPC
  primitives beyond just fork):
  ```python
  import multiprocessing
  def producer(q): q.put("ping")
  ctx = multiprocessing.get_context("fork")
  q = ctx.Queue()
  p = ctx.Process(target=producer, args=(q,))
  p.start(); p.join()
  assert q.get() == "ping"
  print("QUEUE_OK")
  ```
  Expected: exits 0, prints `QUEUE_OK`.

---

### 8. Subprocess sandbox propagation

**Goal:** Confirm that a child Python process spawned by `subprocess` inherits
the sandbox and that internal env vars are cleaned up correctly.

**Tests:**

- Child process can import stdlib and run normally:
  ```python
  import subprocess, sys
  result = subprocess.run(
      [sys.executable, "-c", "import json; print('CHILD_OK')"],
      capture_output=True, text=True, timeout=15
  )
  assert result.returncode == 0, result.stderr
  assert "CHILD_OK" in result.stdout
  print("SUBPROCESS_OK")
  ```
  Expected: exits 0, prints `SUBPROCESS_OK`.

- `PYBOX_ORIGINAL_ARGV0` is not visible in the child's environment (the
  launcher is responsible for stripping it, but we verify it is absent in case
  it leaked):
  ```python
  import subprocess, sys, os
  result = subprocess.run(
      [sys.executable, "-c",
       "import os; print(os.environ.get('PYBOX_ORIGINAL_ARGV0', '__ABSENT__'))"],
      capture_output=True, text=True, timeout=10
  )
  assert "__ABSENT__" in result.stdout, f"leaked: {result.stdout.strip()!r}"
  print("ARGV0_ABSENT_OK")
  ```
  Expected: exits 0, prints `ARGV0_ABSENT_OK`.

---

### 9. Virtual environment compatibility

**Goal:** Confirm that a venv built on top of the test prefix is detected
correctly by CPython — i.e. `sys.prefix` points at the inner venv, not the
base prefix. This exercises the `PYBOX_ORIGINAL_ARGV0` carry mechanism
end-to-end once the feedstock launcher is in place; for now it validates that
the profile does not interfere with standard venv behaviour.

Create a nested venv before running these tests:

```sh
$PREFIX/bin/python -m venv /tmp/pybox-nested-venv
```

For each test below, invoke `/tmp/pybox-nested-venv/bin/python` directly (it
symlinks back into the test prefix). The `--allow` flag must cover both:

```sh
nono-sideload run --profile /tmp/pybox-test-policy.json \
    --allow $PREFIX \
    --allow /tmp/pybox-nested-venv \
    -- /tmp/pybox-nested-venv/bin/python -c "<code>"
```

**Tests:**

- `sys.prefix` is the nested venv, not the base prefix:
  ```python
  import sys, os
  expected = os.path.realpath("/tmp/pybox-nested-venv")
  actual = os.path.realpath(sys.prefix)
  assert actual == expected, f"got {actual!r}"
  print("NESTED_PREFIX_OK")
  ```
  Expected: exits 0, prints `NESTED_PREFIX_OK`.

- `sys.base_prefix` is the base prefix (the Python installation):
  ```python
  import sys, os
  expected = os.path.realpath(os.environ["CONDA_PREFIX"])
  actual = os.path.realpath(sys.base_prefix)
  assert actual == expected, f"got {actual!r}"
  print("BASE_PREFIX_OK")
  ```
  The test harness must set `CONDA_PREFIX=$PREFIX`. Expected: exits 0,
  prints `BASE_PREFIX_OK`.

- Nested venv's `site-packages` is on `sys.path`; base prefix's is not:
  ```python
  import sys, os
  nested_lib = os.path.realpath("/tmp/pybox-nested-venv/lib")
  base_lib   = os.path.realpath(os.environ["CONDA_PREFIX"] + "/lib")
  paths = [os.path.realpath(p) for p in sys.path]
  assert any(p.startswith(nested_lib) and "site-packages" in p for p in paths), \
      f"nested site-packages missing: {paths}"
  assert not any(p.startswith(base_lib) and "site-packages" in p for p in paths), \
      f"base site-packages leaked: {paths}"
  print("SITE_PACKAGES_OK")
  ```
  Expected: exits 0, prints `SITE_PACKAGES_OK`.

---

## Real-world application scenarios

The following scenarios are drawn from the `pybox` prototype's example suite.
They test the profile against realistic workloads rather than synthetic
one-liners, and exercise the sandbox boundary in ways that matter for production
use. Each scenario is run with the same invocation pattern as the core tests
above (sideloaded profile, `--allow $PREFIX`, modified policy with `$PREFIX`
expanded).

Where a scenario requires third-party packages, install them using conda where
possible. Fall back to pip only if the package is unavailable in the conda
channel being used.

---

### 10. Web server survives a blocked write (FastAPI / uvicorn)

**Goal:** Confirm that a long-running server process is not killed by a
`PermissionError` from the sandbox — the error propagates normally to
application code and the server keeps running.

**Setup:**
```sh
# Preferred
conda install -p $PREFIX fastapi uvicorn httpx --yes
# Fallback
$PREFIX/bin/pip install fastapi uvicorn httpx
```

**Tests:**

- Start `uvicorn` inside the sandbox, pointing at a minimal FastAPI app. The
  app exposes two endpoints:
  - `GET /` — health check; reads nothing, writes nothing.
  - `POST /log` — appends a line to `logs/requests.log` inside CWD (allowed).
  - `POST /escape` — attempts `open("/tmp/escaped.txt", "w")` (blocked).

- `GET /` returns HTTP 200. Expected: success.

- `POST /log` returns HTTP 200 and the log file is created in CWD.
  Expected: success.

- `POST /escape` returns HTTP 500 with a `PermissionError` in the response
  body. The server process is still alive and continues serving subsequent
  requests.
  Expected: HTTP 500, server still up, no crash.

- After the `/escape` failure, send another `GET /` to confirm the server
  did not crash or stall.
  Expected: HTTP 200.

---

### 11. Jupyter kernel starts and executes cells

**Goal:** Confirm that Jupyter and ipykernel start normally under the sandbox
and that cells can perform allowed I/O. This exercises the `JUPYTER_*` env var
redirects (`JUPYTER_RUNTIME_DIR`, `JUPYTER_DATA_DIR`, `JUPYTER_CONFIG_DIR`)
that the profile injects via `set_vars`.

**Setup:**
```sh
# Preferred
conda install -p $PREFIX jupyter ipykernel pandas matplotlib --yes
# Fallback
$PREFIX/bin/pip install jupyter ipykernel pandas matplotlib
```

**Tests:**

- Execute a notebook headlessly (`jupyter nbconvert --to notebook --execute`)
  with cells that:
  - Import `pandas` and `matplotlib` — exercises C-extension and shared-library
    access.
  - Read a CSV from the working directory and compute a summary — exercises CWD
    read.
  - Write a summary CSV to `output/summary.csv` inside CWD — exercises CWD
    write.
  Expected: notebook executes to completion, output file is created.

- A cell that attempts `open("/tmp/escaped.txt", "w")` raises `PermissionError`
  and the traceback is captured in the cell output — the kernel does not crash.
  Expected: `PermissionError` in cell output, subsequent cells still execute.

- Jupyter runtime files (connection sockets, kernel pid file) are created under
  `$PREFIX/tmp/jupyter/runtime/`, not under `~/.local/share/jupyter/` or
  `~/Library/Jupyter/`. Verify by checking `JUPYTER_RUNTIME_DIR` from inside a
  cell:
  ```python
  import os
  assert os.environ["JUPYTER_RUNTIME_DIR"].startswith(os.environ["CONDA_PREFIX"]), \
      os.environ["JUPYTER_RUNTIME_DIR"]
  ```
  Expected: assertion passes.

---

### 12. Filesystem write/overwrite/delete/copy outside CWD all blocked

**Goal:** Confirm the four fundamental filesystem attack vectors are each
independently blocked. These correspond to distinct syscalls; one being blocked
does not imply the others are.

**Setup:** Before invoking the sandbox, create sentinel files outside CWD:
```sh
echo "sentinel" > /tmp/pybox-sentinel.txt
echo "sentinel2" > /tmp/pybox-sentinel2.txt
```

**Tests (all run inside one sandboxed invocation, CWD set to a temp dir):**

- Write a new file to `/tmp`: `open("/tmp/pybox-new-file.txt", "w")`
  Expected: `PermissionError`.

- Overwrite an existing file in `/tmp`: `open("/tmp/pybox-sentinel.txt", "w")`
  Expected: `PermissionError`.

- Delete a file in `/tmp`: `pathlib.Path("/tmp/pybox-sentinel2.txt").unlink()`
  Expected: `PermissionError`.

- `shutil.copy(__file__, "/tmp/pybox-stolen-script.py")`
  Expected: `PermissionError`.

- After all four attempts, verify the sentinel files still exist and are
  unchanged (checked from outside the sandbox).
  Expected: both sentinel files intact.

---

### 13. PYTHONPATH injection has no effect

**Goal:** `PYTHONPATH` is unconditionally stripped by nono regardless of
`allow_vars`. Confirm it is not visible inside the sandbox even when set in the
parent shell.

**Test:** Set `PYTHONPATH=/tmp/evil-modules` in the invoking environment, then:
```python
import os
assert "PYTHONPATH" not in os.environ, \
    f"PYTHONPATH leaked: {os.environ['PYTHONPATH']!r}"
print("PYTHONPATH_STRIPPED_OK")
```
Expected: exits 0, prints `PYTHONPATH_STRIPPED_OK`.

---

### 14. Process-tree sandbox: spawning a different interpreter does not escape

**Goal:** Confirm that spawning `/usr/bin/python3` (or any other interpreter)
from inside the sandbox does not give that child process an unsandboxed
environment. The kernel policy covers the entire process tree; exec'ing a
different binary does not break out.

**Tests:**

- `os.system("/usr/bin/python3 -c 'open(\"/tmp/escape1.txt\", \"w\").write(\"x\")'")`:
  Check that `/tmp/escape1.txt` does not exist after the call.
  Expected: write blocked, file not created.

- `subprocess.run(["/usr/bin/python3", "-c", "open('/tmp/escape2.txt','w').write('x')"])`:
  Check that `/tmp/escape2.txt` does not exist.
  Expected: write blocked, file not created.

- `subprocess.run("bash -c 'python3 -c ...'", shell=True)`:
  Same check.
  Expected: write blocked.

- `os.execv` replacement — run in a child subprocess so our process survives:
  ```python
  import subprocess, sys
  r = subprocess.run(
      [sys.executable, "-c",
       "import os; os.execv('/usr/bin/python3', "
       "['/usr/bin/python3', '-c', \"open('/tmp/escape4.txt','w').write('x')\"])"],
      capture_output=True, text=True, timeout=10
  )
  ```
  Check that `/tmp/escape4.txt` does not exist.
  Expected: write blocked even after `execv` replaces the process image.

---

### 15. `$PREFIX` is effectively read-only — tampering attempts blocked

**Goal:** Confirm that the sandboxed process can read from the prefix (import
packages) but cannot modify it. This matters because the profile grants
`--allow $PREFIX` which is read-write, but the intent is that write access is
limited to `$PREFIX/tmp` and `$PREFIX/__pycache__`. The profile's `filesystem`
section should deny writes to critical paths even within `$PREFIX`.

**Setup:**
```sh
# Preferred — install requests via conda so site-packages is under $PREFIX
conda install -p $PREFIX requests --yes
# Fallback
$PREFIX/bin/pip install requests
```

**Tests:**

- Inject a `.pth` file into `site-packages`:
  ```python
  import site, pathlib
  sp = pathlib.Path(site.getsitepackages()[0])
  (sp / "evil.pth").write_text("import os; os.system('echo PWNED')\n")
  ```
  Expected: `PermissionError`.

- Delete a package file:
  ```python
  (sp / "requests" / "__init__.py").unlink()
  ```
  Expected: `PermissionError`.

- Overwrite a package file:
  ```python
  (sp / "requests" / "__init__.py").write_text("# backdoored\n")
  ```
  Expected: `PermissionError`.

- Write an arbitrary file to the prefix root:
  ```python
  import os
  (pathlib.Path(os.environ["CONDA_PREFIX"]) / "injected.txt").write_text("x\n")
  ```
  Expected: `PermissionError`.

- After all attempts, `import requests` succeeds (prefix is undamaged).
  Expected: import succeeds.

**Note:** This test defines a requirement on the profile's `filesystem` section
that goes beyond a plain `--allow $PREFIX`. The profile must explicitly deny
writes to `$PREFIX/lib` (and `$PREFIX/site-packages`) while still permitting
writes to `$PREFIX/tmp` and `$PREFIX/__pycache__`. This is a key profile
authoring constraint to validate.

---

### 16. Package installation inside the sandbox cannot corrupt the prefix

**Goal:** A malicious package's post-install hook (running under the package
manager, which itself runs inside the sandbox) cannot overwrite the Python
binary or other critical prefix paths. This is tested for both conda and pip,
since both are common installation vectors.

**Setup:** Create a minimal local package with a post-install script that
attempts to overwrite `$PREFIX/bin/python` and inject a `.pth` file into
`site-packages`.

#### 16a. conda install of a malicious local package

Build a local conda package whose `post-link.sh` attempts:
1. `cp /dev/urandom $PREFIX/bin/python` — overwrite the Python binary.
2. `echo "import os; os.system('echo PWNED')" > $PREFIX/lib/pythonX.Y/site-packages/evil.pth`

```sh
conda install -n pybox-test --use-local ./malicious-conda-pkg --yes
```

Run this inside the sandbox:
```sh
nono-sideload run --profile /tmp/pybox-test-policy.json \
    --allow $PREFIX \
    -- conda install -p $PREFIX --use-local ./malicious-conda-pkg --yes
```

Expected: both write attempts in `post-link.sh` raise `Permission denied`;
conda reports the post-link hook as failed. `$PREFIX/bin/python` is unchanged
(verify checksum from outside the sandbox).

#### 16b. pip install of a malicious local package

Create a local Python package whose `pyproject.toml` includes a post-install
hook that attempts to overwrite `$PREFIX/bin/python` and write
`site-packages/evil.pth`.

```sh
nono-sideload run --profile /tmp/pybox-test-policy.json \
    --allow $PREFIX \
    -- $PREFIX/bin/pip install ./malicious_pkg
```

Expected: the hook's write attempts raise `PermissionError`; pip reports the
install as failed or partial. `$PREFIX/bin/python` is unchanged.

#### Both variants — post-attack verification

After either attack, confirm from outside the sandbox:
- `$PREFIX/bin/python` hash is unchanged.
- `site-packages/evil.pth` does not exist.
- A normal sandboxed Python invocation still works and still blocks writes to
  `/tmp` (sandbox is still functional).
