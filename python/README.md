# python-sandbox nono pack

Sandboxes Python in a conda-managed environment (conda, micromamba, or pixi).

Once installed, every `python` invocation in the environment runs under OS-level kernel restrictions — enforced by nono and irreversible for the lifetime of the process.

## What this pack allows

- **Read + write access to `$PREFIX`** — the full conda environment root (stdlib, site-packages, shared libs, etc.), so `pip install` works normally inside the sandbox.
- Everything else (home directory, working directory, credential stores, shell history, cloud credentials, etc.) is denied by default.

## Variants

This is the **full-access** variant: the sandboxed process has unrestricted write access to `$PREFIX`. A future pack will provide a more restricted variant that limits writes within `$PREFIX` (e.g. blocking writes to `$PREFIX/bin`).

## Customising

Extend this profile to grant access to additional paths (e.g. the working directory, a model weight cache), add network restrictions, or override other defaults:

```jsonc
// ~/.config/nono/profiles/my-python.json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "my-python", "version": "1.0.0" },
  "filesystem": {
    "allow": ["$HOME/datasets"],
    "allow_file": ["$HOME/output.csv"]
  },
  "workdir": { "access": "readwrite" }
}
```

Point the conda environment at your custom profile:

```bash
conda env config vars set -p /path/to/env CONDA_PYTHON_PROFILE=my-python
```

Then restart Python to pick up the new profile.

## OpenCode skill

When this pack is installed, an OpenCode skill (`python-sandbox`) is automatically wired into `~/.config/opencode/skills/`. The skill teaches an AI agent how to diagnose sandbox permission errors and author profile extensions — including the restart requirement.

