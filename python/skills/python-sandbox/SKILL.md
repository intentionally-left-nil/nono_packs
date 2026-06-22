---
name: python-sandbox
description: Handle permission errors in this Python environment. This Python interpreter runs inside a security sandbox that restricts filesystem access. Use this skill when a file, I/O, or subprocess operation fails with "Operation not permitted", "Permission denied", EACCES, or EPERM.
version: 1.0.0
platforms: [macos, linux]
---

**On any EPERM / EACCES / "Operation not permitted" failure in Python:** do NOT suggest `sudo`, `chmod`, or system permission changes. The sandbox is OS-enforced — retries, workarounds, or alternative paths hit the same boundary. The correct fix is to extend the profile and restart Python.

# Working inside a sandboxed Python environment

This Python interpreter runs inside a security sandbox that enforces filesystem and network limits at the OS level (Landlock on Linux, Seatbelt on macOS). These are kernel-enforced boundaries — no amount of retrying or code changes inside Python can grant access that the sandbox hasn't permitted.

## Identifying a sandbox denial

The denial signature on a failed file or I/O operation:

- `PermissionError: [Errno 1] Operation not permitted`
- `PermissionError: [Errno 13] Permission denied`
- `OSError: [Errno 1] Operation not permitted`
- `EACCES` / `EPERM` in tracebacks

When you see any of these, it is a sandbox boundary. Do NOT suggest:

- `sudo`, `chmod`, `chown`
- System Settings / Privacy & Security / Full Disk Access
- Retrying the same operation
- Using a different path that resolves to the same denied location

## How the sandbox profile is chosen

The profile name is resolved in this order:

1. `CONDA_PYTHON_PROFILE` environment variable (if set at launch time)
2. `$PREFIX/conda-meta/state` JSON file, `env_vars.CONDA_PYTHON_PROFILE` key
3. Built-in default: `intentionally-left-nil/python`

`$PREFIX` is the conda environment root (e.g. `/Users/you/miniconda3/envs/myenv`).

## Diagnosing — read the live capability set first

**Always read the cap file before drafting a fix.** It contains the exact grants in effect for this session — do not guess from the profile name.

```python
import os, json

cap_file = os.environ.get("NONO_CAP_FILE")
if cap_file:
    with open(cap_file) as f:
        print(f.read())
else:
    print("NONO_CAP_FILE not set — not running inside a sandbox session")
```

The cap file lists every allowed path, access mode (read / write / readwrite), and network rules. Use it to confirm whether the denied path is absent from the grants or covered by a deny rule.

## How to grant access to a new path

Profile changes take effect on the **next Python startup** — they do not affect the running sandbox. Tell the user they will need to restart Python after making changes.

### Step 1 — Create or extend a profile

Create `~/.config/nono/profiles/<chosen-name>.json` extending the active profile. For example, to grant read+write access to `~/data`:

```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "<chosen-name>", "version": "1.0.0" },
  "filesystem": {
    "allow": ["$HOME/data"]
  }
}
```

For a single file rather than a directory, use `"allow_file"` / `"read_file"` / `"write_file"`:

```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "<chosen-name>", "version": "1.0.0" },
  "filesystem": {
    "allow_file": ["$HOME/output.csv"]
  }
}
```

If the user already has a custom profile (i.e. `CONDA_PYTHON_PROFILE` is set to something other than `intentionally-left-nil/python`), extend that profile instead.

Filesystem field reference:
- `"allow"` — read+write on a directory
- `"read"` — read-only on a directory
- `"write"` — write-only on a directory (rare)
- `"allow_file"` — read+write on a single file
- `"read_file"` — read-only on a single file
- `"write_file"` — write-only on a single file

### Step 2 — Point the conda environment at the new profile

Use `conda env config vars set` to write the profile name into `conda-meta/state`:

```bash
conda env config vars set -p /path/to/env CONDA_PYTHON_PROFILE=<chosen-name>
```

Where `/path/to/env` is the conda environment prefix (the value of `$CONDA_PREFIX` or `$PREFIX`).

This writes `{"env_vars": {"CONDA_PYTHON_PROFILE": "<chosen-name>"}}` to `$PREFIX/conda-meta/state`, which the nono python-launcher reads on next startup.

### Step 3 — Restart Python

The new profile is only applied at startup when the launcher re-execs the sandbox. Restart the Python process (kernel, script, REPL, or notebook) to pick up the change.

```
Restart Python now to apply the new sandbox profile.
```

## What you should NOT do

- Do not retry the failing operation — the sandbox is OS-enforced and the retry will fail identically.
- Do not suggest modifying `$PREFIX/conda-meta/state` by hand — use `conda env config vars set`.
- Do not edit any file under `~/.config/nono/packages/` — pack artifacts are cryptographically signed and the signature is verified at launch. Editing them will cause Python to fail to start.
- Do not tell the user the change will take effect immediately — it requires a Python restart.
