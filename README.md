# nono_packs

A collection of [nono.sh](https://nono.sh) packs — sandboxed execution environments for common developer toolchains.

Each pack configures a nono sandbox with the policies, hooks, and configuration needed to safely run a specific tool or ecosystem.

## Packs

| Pack | Directory | Purpose |
|------|-----------|---------|
| npm  | [`npm/`](./npm/) | Run npm commands in an isolated sandbox, preventing untrusted package code from executing on your host machine. Packages are installed into `sandbox_modules` and do not persist in `node_modules` after the session ends. |
