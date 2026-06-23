---
name: python-sandbox
description: Resolves sandbox permission errors in this Python environment. Use when a file, I/O, network, or subprocess operation fails with "Operation not permitted", "Permission denied", EACCES, EPERM, or a network connection is blocked. Also use when the user asks how to grant a path, change the sandbox profile, or configure what their Python code can access.
version: 1.0.0
platforms: [macos, linux]
---

# Skill: python-sandbox

The Python interpreter in this environment is a sandboxed build powered by [nono](https://docs.nono.sh). It enforces filesystem and network limits at the OS level (Seatbelt on macOS, Landlock on Linux) — kernel-enforced boundaries that cannot be bypassed from inside Python.

**You do not run nono yourself.** Run Python the normal way (`python script.py`, `pytest`, `jupyter lab`). The launcher applies the active sandbox profile automatically. **Never prefix with `nono run`** — that double-wraps and breaks the active profile.

The `nono` profile CLI is available in this environment for validating and inspecting profiles.

## Identifying a sandbox denial

```
PermissionError: [Errno 1] Operation not permitted
PermissionError: [Errno 13] Permission denied
OSError: [Errno 1] Operation not permitted
```

When you see any of these, it is a sandbox boundary. Do NOT suggest:

- `sudo`, `chmod`, `chown`
- System Settings / Privacy & Security / Full Disk Access
- Retrying the same operation
- A different path that resolves to the same denied location

The fix is always: **extend the profile → validate → wire → restart Python.**

Network connection errors (`[Errno 1] Operation not permitted` on a socket call, or a blocked outbound connection) may indicate a network sandbox denial. If the user is trying to reach an API that needs a credential, use the `env-secrets` skill instead of this one.

## Workflow

```
Checklist:
- [ ] Step 1: Read the live cap file to see what is actually granted
- [ ] Step 2: Create or extend the profile with the missing path
- [ ] Step 3: Validate the profile
- [ ] Step 4: Wire the conda environment to the profile
- [ ] Step 5: Tell the user to restart Python
```

## Step 1: Read the live cap file

**Always do this before editing anything.** The cap file shows every grant in effect for the running session — do not guess from the profile name.

```python
import os, json

cap_file = os.environ.get("NONO_CAP_FILE")
if cap_file:
    with open(cap_file) as f:
        print(f.read())
else:
    print("NONO_CAP_FILE not set — not running inside a sandbox session")
```

Confirm the denied path is absent from the grants (or covered by a deny rule) before proceeding.

## Step 2: Create or extend the profile

Profiles are JSON files at `~/.config/nono/profiles/<name>.json`.

**If `CONDA_PYTHON_PROFILE` is set to something other than `intentionally-left-nil/python`**, extend that profile instead of the base. Check with:

```bash
python -c "import os; print(os.environ.get('CONDA_PYTHON_PROFILE', 'not set'))"
```

**Grant a directory** (read+write):
```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "my-profile", "version": "1.0.0" },
  "filesystem": {
    "allow": ["$HOME/data"]
  }
}
```

**Grant a single file:**
```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "my-profile", "version": "1.0.0" },
  "filesystem": {
    "allow_file": ["$HOME/output.csv"]
  }
}
```

Filesystem field reference:

| Field | Access |
|---|---|
| `allow` | read+write on a directory |
| `read` | read-only on a directory |
| `write` | write-only on a directory |
| `allow_file` | read+write on a single file |
| `read_file` | read-only on a single file |
| `write_file` | write-only on a single file |

Use `$HOME`, `$WORKDIR`, `$TMPDIR` in paths — do not hardcode absolute paths. For network access, credential injection, or environment variable configuration, see the `env-secrets` skill.

## Step 3: Validate the profile

After every edit, validate before wiring. A profile that fails validation will prevent Python from starting.

```bash
nono profile validate ~/.config/nono/profiles/<name>.json
```

To inspect the fully resolved profile after inheritance:

```bash
nono profile show <name>
```

Fix any reported errors and re-run validation before proceeding.

## Step 4: Wire the conda environment

The active profile is controlled by `CONDA_PYTHON_PROFILE` in the conda environment's `conda-meta/state`. Write it with:

```bash
conda env config vars set -p /path/to/env CONDA_PYTHON_PROFILE=<name>
```

Where `/path/to/env` is `$CONDA_PREFIX` (the conda environment root).

**If `conda env config vars` is not available**, write the state file directly:

```bash
python -c "
import json, os, pathlib
prefix = os.environ.get('CONDA_PREFIX')
if not prefix:
    print('CONDA_PREFIX not set — activate the environment first')
else:
    state = pathlib.Path(prefix) / 'conda-meta' / 'state'
    data = json.loads(state.read_text()) if state.exists() else {}
    data.setdefault('env_vars', {})['CONDA_PYTHON_PROFILE'] = '<name>'
    state.write_text(json.dumps(data, indent=2))
    print('Written:', state)
"
```

## Step 5: Restart Python

Profile changes take effect at next interpreter startup — not in the running process.

```
Restart Python now to apply the new sandbox profile.
```

## What you must NOT do

- **Do not prefix Python invocations with `nono run`** — the interpreter is already wrapped. Run `python script.py` as normal.
- **Do not suggest `sudo`, `chmod`, `chown`** — the sandbox is kernel-enforced; these have no effect on it.
- **Do not edit files under `~/.config/nono/packages/`** — pack artifacts are cryptographically signed; editing them causes Python to fail to start.
- **Do not tell the user the change takes effect immediately** — it requires a Python restart.
- **Do not retry the failing operation** — sandbox denials are deterministic; the retry will fail identically.
