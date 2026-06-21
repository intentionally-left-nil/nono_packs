# python-sandbox nono pack

Sandboxes Python in a conda-managed environment (conda, micromamba, or pixi).

Once installed, every `python` invocation in the environment runs under OS-level kernel restrictions — enforced by nono and irreversible for the lifetime of the process.

## What this pack allows

- **Read + write access to `$PREFIX`** — the full conda environment root (stdlib, site-packages, shared libs, etc.), so `pip install` works normally inside the sandbox.
- **Read + write access to the working directory** — so scripts can read and write files where they are run.
- Everything else (home directory, credential stores, shell history, cloud credentials, etc.) is denied.

## Variants

This is the **full-access** variant: the sandboxed process has unrestricted write access to `$PREFIX`. A future pack will provide a more restricted variant that limits writes within `$PREFIX` (e.g. blocking writes to `$PREFIX/bin`).

## Customising

Extend this profile to add network restrictions, grant access to additional paths (e.g. a model weight cache), or override other defaults:

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

Set `CONDA_PYTHON_PROFILE=my-python` to use your custom profile.
