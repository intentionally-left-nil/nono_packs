# Testing Packs

This document describes how to test packs in this repository locally before
publishing them to the registry.

Because the nono registry requires Sigstore attestation on every pack, the
normal `nono pull` path is not available during development. The `nono-sideload`
binary provides a development-only escape hatch that installs a pack directly
from a local directory, bypassing attestation checks entirely.

---

## Prerequisites

Build a copy of nono with the `sideload` feature enabled:

```sh
cargo build --features sideload
```

Name the resulting binary `nono-sideload` and place it somewhere on your
`PATH`. The binary is intentionally distinct from production `nono` — every
invocation prints a warning confirming that integrity protections are disabled.
Do not use it on production systems.

---

## Installing a pack with sideload

From the repository root, pass the path to the pack directory (the directory
that contains `package.json`):

```sh
nono-sideload sideload ./npm
```

The command:

- Reads `package.json` and validates the artifact list.
- Copies artifacts into the local pack store (`~/.config/nono/packages/<namespace>/<name>/`).
- Applies any `wiring` directives declared in `package.json` (symlinks,
  `write_file` entries, etc.).
- Expands `$PACK_DIR` references in `session_hooks` to the installed pack
  directory.
- Records a lockfile entry marking the pack as `[sideload]`.

Sideloading is idempotent. After editing `policy.json` or any other pack
artifact, re-run the same command to pick up the changes.

---

## Verifying the installed pack

Confirm the pack appears in the installed list:

```sh
nono-sideload list --installed
```

Sideloaded packs are shown with a `[sideload]` annotation next to the version.

To inspect the resolved profile — after inheritance and group expansion — and
confirm the effective capability set before running anything:

```sh
nono-sideload profile show <profile-name>
```

To see exactly which filesystem paths and network rules will be applied, and
why each rule is present:

```sh
nono-sideload run --profile <namespace>/<name> --dry-run -- <command>
```

The dry-run output shows the full capability summary (allowed paths, network
mode, credential routes) without actually executing the command or applying the
sandbox.

To investigate why a specific path would be allowed or denied:

```sh
nono-sideload why --path <path> --op <read|write|readwrite> --profile <namespace>/<name>
```

---

## Running the sandbox

Once sideloaded, exercise the pack using `nono-sideload run` in place of
`nono run`:

```sh
nono-sideload run --profile <namespace>/<name> -- <command>
```

All standard `nono run` flags work as usual (`--allow`, `--read`, `--block-net`,
`--allow-cwd`, etc.).

---

## Iterating

The typical edit-test loop is:

1. Edit `policy.json` (or hooks, wiring, etc.) in the pack directory.
2. Re-sideload: `nono-sideload sideload ./<pack>`.
3. Verify with `--dry-run` or a targeted `nono-sideload run`.
4. Repeat.

There is no need to remove and reinstall between iterations — sideload
overwrites the previous installation in place.

---

## Removing a sideloaded pack

```sh
nono-sideload remove <namespace>/<name>
```

This reverses wiring directives (removes symlinks, etc.) and cleans up the
pack store entry and lockfile.

---

## Production nono refuses sideloaded packs

The production `nono` binary verifies the Sigstore attestation bundle for every
installed pack before running it. Sideloaded packs have no bundle, so production
`nono` will refuse to use them:

```
nono: Package verification failed for <namespace>/<name>: pack '<namespace>/<name>' is
missing .nono-trust.bundle - reinstall with: nono pull <namespace>/<name> --force
```

Use `nono-sideload` throughout local development. Switch to the published pack
via `nono pull` once it has been released.
