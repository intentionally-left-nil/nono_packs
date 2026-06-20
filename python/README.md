# python-sandbox nono pack

Provides a nono sandbox profile for Python environments managed by conda,
micromamba, or pixi. Once installed, every `python` invocation in the
environment runs under OS-level kernel restrictions (Landlock on Linux,
Seatbelt on macOS) — enforced by nono and irreversible for the lifetime of
the process.

This pack is the **install-enabled variant**: `pip install` works normally
inside the sandbox. Package managers that run outside the Python process
(`conda`, `uv`, `pixi`) are expected to run outside the sandbox.

---

## How it works

The python-sandbox feedstock produces a Python binary that is a fork of the
nono CLI. When invoked, it:

1. Walks its ancestor process chain to detect whether it is already running
   inside a nono-supervised sandbox.
2. If **not** sandboxed: resolves the profile, builds an `ExecConfig`, and
   calls `execute_supervised()` — re-execing itself as the sandboxed child.
3. If **sandboxed**: calls `Py_BytesMain()` directly, handing off to CPython.

The sandbox is applied at the kernel level. It cannot be bypassed from
userspace by environment variables, `sys` module manipulation, or any other
Python technique.

---

## Profile: `python-sandbox`

The profile (`policy.json`) defines what the sandboxed Python process is
permitted to do.

### Filesystem

| Path | Access | Reason |
|------|--------|--------|
| `$PREFIX` | read+write | Entire conda env root — stdlib, site-packages, shared libs, CA bundle |
| `$HOME/.CFUserTextEncoding` | read | macOS: CPython text-encoding init |
| `$HOME/.terminfo` | read | Terminal capability database (IPython, rich, Jupyter) |
| `/usr/share/zoneinfo` | read | Timezone data fallback |
| `/var/db/timezone` | read (macOS) | macOS alternate timezone location |
| `/tmp` | read | Unix socket discovery, X11, lock files. Write access comes from `TMPDIR=$PREFIX/tmp` |
| CWD | read+write | Working directory |

Everything else — home directory files, credential stores, shell history,
browser data, cloud credentials — is denied by the groups inherited from
`default`.

`$PREFIX` is a build-var supplied at runtime by the feedstock launcher. When
testing via `nono-sideload`, substitute it manually (see
`docs/TESTING.md`).

### Environment variables

`allow_vars` is an explicit allowlist. Variables not in the list are stripped
before the sandboxed process starts. This prevents accidental credential
leakage from the parent shell.

`set_vars` injects fixed values after the allowlist filter. These values
override any inherited host value for the same key and cannot be spoofed from
the parent environment.

Key `set_vars` redirects:

| Variable | Value | Reason |
|----------|-------|--------|
| `TMPDIR` / `TMP` / `TEMP` | `$PREFIX/tmp` | Per-environment temp isolation; prevents cross-sandbox `/tmp` pollution |
| `PYTHONPYCACHEPREFIX` | `$PREFIX/__pycache__` | Keeps `.pyc` files out of source trees |
| `PIP_CACHE_DIR` | `$PREFIX/tmp/pip` | Isolates downloaded wheels per environment |
| `JUPYTER_RUNTIME_DIR` | `$PREFIX/tmp/jupyter/runtime` | Prevents sandboxed kernels registering with unsandboxed Jupyter sessions |
| `JUPYTER_DATA_DIR` | `$PREFIX/share/jupyter` | Kernel discovery scoped to this environment |
| `JUPYTER_CONFIG_DIR` | `$PREFIX/tmp/jupyter/config` | Ephemeral per-session Jupyter config |
| `MPLCONFIGDIR` | `$PREFIX/tmp/matplotlib` | Matplotlib font cache isolated per environment |
| `NUMBA_CACHE_DIR` | `$PREFIX/tmp/numba` | Numba JIT cache — native code, must be isolated |
| `TRITON_CACHE_DIR` | `$PREFIX/tmp/triton` | Triton GPU kernel cache — native code, must be isolated |
| `TORCHINDUCTOR_CACHE_DIR` | `$PREFIX/tmp/torch_inductor` | torch.compile kernel cache — native code, must be isolated |

**Model weight caches** (`HF_HOME`, `TORCH_HOME`, `HF_HUB_CACHE`,
`TRANSFORMERS_CACHE`) are passed through from the host environment but are
**not** forced to `$PREFIX/tmp` — model caches can be tens to hundreds of GB
and should not be relocated without explicit user intent. The sandboxed
process can only access these paths if an additional filesystem grant is
provided (e.g. `nono run --allow $HF_HOME ...`).

### Security

`ipc_mode: full` is required for Python's `multiprocessing` module. Without
it, fork-based workers (Pool, Queue, shared memory) hang because abstract
UNIX socket communication is restricted.

### Network

Outbound network is unrestricted by default. This allows pip to reach PyPI
and allows Python scripts to make arbitrary HTTP/HTTPS requests. Use a
custom profile extending this one with `network.block: true` or a
`network_profile` to restrict outbound access.

### What is NOT protected

- **`$PREFIX` write access is intentional.** pip installs packages into
  `$PREFIX/lib/.../site-packages/` and creates console scripts in
  `$PREFIX/bin/`. This means a malicious package's post-install hook could
  in principle write to `$PREFIX/bin/python`. The feedstock's nono fork adds
  an explicit deny for `$PREFIX/bin/python*` in the `ExecConfig` to prevent
  this; that rule is not in this profile file because it requires knowing the
  exact binary names and is enforced at the launcher level.

- **Rollback** snapshots `$PREFIX` if the user requests `--rollback`,
  since it has write grants. For large environments this is expensive. nono
  has no profile-level rollback disable; users who want rollback should be
  aware it covers `$PREFIX` as well as `$WORKDIR`.

---

## Customising the profile

The easiest way to customise is to create a user profile that extends this
one:

```jsonc
// ~/.config/nono/profiles/my-python.json
{
  "extends": "python-sandbox",
  "meta": { "name": "my-python" },
  "network": { "block": true },
  "filesystem": {
    "allow": ["$HOME/datasets"]
  }
}
```

To override the profile used by the feedstock launcher, set
`CONDA_PYTHON_PROFILE` before invoking Python:

```sh
# One-off override
CONDA_PYTHON_PROFILE=my-python python script.py

# Per-environment persistent override
conda env config vars set CONDA_PYTHON_PROFILE=my-python
```

The precedence order is:
1. `CONDA_PYTHON_PROFILE` environment variable
2. `$PREFIX/conda-meta/state` → `env_vars.CONDA_PYTHON_PROFILE`
3. Compile-time default (`python-sandbox`)

---

## Testing

See `docs/TESTING.md` for the full testing workflow using `nono-sideload`.
See `python/specs/test_scenarios.md` for the test scenario catalogue.
