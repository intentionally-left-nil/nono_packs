# Pack Authoring

This document covers the basics of authoring a nono pack. It is an orientation
guide; for the definitive reference on any topic, follow the links to the
official nono documentation.

---

## What is a pack?

A pack is a signed, versioned bundle of artifacts — profiles, hooks, scripts,
and supporting files — distributed via the nono registry. Installing a pack
with `nono pull` places its artifacts into the local pack store
(`~/.config/nono/packages/<namespace>/<name>/`) and applies any wiring
directives declared in `package.json`.

**Definitive reference:**
[Managing Packs](https://nono.sh/docs/cli/features/managing-packs)
| [Publishing Packs](https://nono.sh/docs/cli/features/package-publishing)

---

## Repository layout

A pack lives in its own subdirectory. At minimum it contains:

```
<pack>/
├── package.json        # manifest: name, version, artifacts, wiring
├── policy.json         # the nono profile (sandbox policy)
└── README.md           # optional but recommended
```

Additional artifacts — hook scripts, config files, skill documents — are
declared in `package.json` and placed alongside it. See the `npm/` pack in
this repository for a concrete example.

---

## `package.json`

The manifest describes everything the registry and the CLI need to know about
the pack. Required fields:

| Field | Purpose |
|---|---|
| `schema_version` | Always `1` |
| `name` | Pack name; must match the registry entry |
| `version` | Semver (e.g. `0.1.0`). Must be bumped before every release. |
| `description` | One-line description |
| `license` | SPDX identifier (e.g. `MIT`, `Apache-2.0`) |
| `platforms` | `["macos", "linux"]` or a subset |
| `min_nono_version` | Oldest CLI version that supports every feature the pack uses |
| `artifacts` | List of files to sign and install (see below) |

### Artifacts

Each entry in `artifacts` has a `type` and a `path` (relative to the pack
directory). The supported types are:

- **`profile`** — a nono sandbox profile JSON. Requires `install_as` (the
  name users type after `--profile`).
- **`plugin`** — any other file. Installed at its relative path inside the
  pack store. Without `install_dir` it stays in the pack store and is exposed
  to the sandbox via `$PACK_DIR`; with `install_dir` it is also fan-out copied
  into the user's home directory.
- **`instruction`** — a markdown context file (e.g. `CLAUDE.md`) optionally
  copied into the working directory on `nono pull --init`.
- **`script`** — a helper script installed under the pack's script directory.
- **`groups`** — additional capability groups (requires a `prefix` to avoid
  collisions with built-in group names).

### Wiring

`wiring` directives run at install time (`nono pull` / `nono-sideload sideload`).
Two types are supported:

- **`symlink`** — create a symlink in the user's home pointing into the pack
  store.
- **`write_file`** — copy a file from the pack into a path under the user's
  home.

Both support `"when": "macos"` / `"when": "linux"` predicates and the
`$PACK_DIR` / `$HOME` / `$NONO_PACKAGES` variables.

**Definitive reference:**
[Publishing Packs — Step 2: Write package.json](https://nono.sh/docs/cli/features/package-publishing#step-2-write-packagejson)

---

## `policy.json` — the profile

The profile is a JSONC file (JSON with `//` comments and trailing commas) that
defines the sandbox policy. Key sections:

### `extends`
Inherit from a base profile. Almost all packs extend `"default"`, which
provides the standard deny groups (credentials, browser data, shell history,
etc.) and system-library read access.

```jsonc
{ "extends": "default" }
```

### `workdir`
Controls whether the current working directory is shared with the sandboxed
process.

```jsonc
{ "workdir": { "access": "readwrite" } }
// access: "none" | "read" | "write" | "readwrite"
```

### `filesystem`
Additive path grants and deny overrides on top of what `extends` and `groups`
already provide.

```jsonc
{
  "filesystem": {
    "allow":  ["$HOME/.my-tool"],        // read + write
    "read":   ["/usr/share/zoneinfo"],   // read-only
    "write":  ["$HOME/.cache/my-tool"],  // write-only
    "deny":   ["$HOME/.ssh"],            // explicit block
    "bypass_protection": ["$HOME/.docker"] // punch hole in a deny group
                                            // (must also appear in allow/read/write)
  }
}
```

### `groups`
Include or exclude named capability groups. Groups are composable collections
of allow/deny rules for common toolchains and paths (e.g. `python_runtime`,
`node_runtime`, `deny_credentials`).

```jsonc
{
  "groups": {
    "include": ["python_runtime", "unlink_protection"],
    "exclude": ["dangerous_commands"]
  }
}
```

Run `nono profile groups` for the full list of built-in groups.

### `network`
```jsonc
{
  "network": {
    "block": false,                             // true to block all outbound
    "allow_domain": ["api.example.com"],        // extra domains through proxy
    "credentials": ["openai"],                  // credential injection via proxy
    "network_profile": "developer"              // named host-filter preset
  }
}
```

### `environment`
Filter and inject environment variables.

```jsonc
{
  "environment": {
    "allow_vars": ["HOME", "PATH", "AWS_*"],   // allowlist (empty = pass all)
    "deny_vars":  ["GH_TOKEN"],                // strip these even if in allow_vars
    "set_vars":   { "TOOL_MODE": "sandbox" }   // static injection; supports
                                                // $HOME, $TMPDIR, $WORKDIR, etc.
  }
}
```

`set_vars` values are injected after allow/deny filtering and cannot be
overridden by the host environment. `PATH` and `NONO_*` keys are reserved
and rejected.

### `env_credentials`
Inject secrets from the system keystore (macOS Keychain / Linux Secret Service)
as environment variables in the sandboxed child.

```jsonc
{
  "env_credentials": {
    "my_api_key": "MY_API_KEY"   // keystore account → env var name
  }
}
```

### `session_hooks`
Scripts that run **outside** the sandbox with host privileges, before or after
the sandboxed process. The `before` hook receives `NONO_SESSION_ID`,
`NONO_WORKDIR`, and `NONO_ENV_FILE` (write `KEY=VALUE` lines to inject env
vars into the sandbox). The `after` hook receives `NONO_SESSION_ID`,
`NONO_WORKDIR`, and `NONO_EXIT_CODE`.

```jsonc
{
  "session_hooks": {
    "before": { "script": "$PACK_DIR/hooks/before.sh", "timeout_secs": 30 },
    "after":  { "script": "$PACK_DIR/hooks/after.sh",  "timeout_secs": 10 }
  }
}
```

`$PACK_DIR` expands to the pack's installed directory in the pack store at
runtime. Use it to reference hook scripts and config files bundled with the
pack.

### `security`
Process isolation knobs.

```jsonc
{
  "security": {
    "ipc_mode": "full"   // "full" required for Python multiprocessing, etc.
                          // default is "shared_memory_only"
  }
}
```

**Definitive reference:**
[Profile Authoring](https://nono.sh/docs/cli/features/profile-authoring)
| [Profiles & Groups](https://nono.sh/docs/cli/features/profiles-groups)

---

## Variable expansion in profiles

The following variables are expanded in filesystem path fields and in
`environment.set_vars` values:

| Variable | Expands to |
|---|---|
| `$HOME` | User's home directory |
| `$WORKDIR` | Current working directory |
| `$TMPDIR` | System temporary directory |
| `$XDG_CACHE_HOME` | `~/.cache` (if unset) |
| `$XDG_CONFIG_HOME` | `~/.config` (if unset) |
| `$XDG_DATA_HOME` | `~/.local/share` (if unset) |
| `$XDG_STATE_HOME` | `~/.local/state` (if unset) |
| `$XDG_RUNTIME_DIR` | XDG runtime dir (left unexpanded if unset) |
| `$NONO_CONFIG` | `~/.config/nono` |
| `$NONO_PACKAGES` | `~/.config/nono/packages` |
| `$UID` | Current user ID |

`$PACK_DIR` is expanded in `session_hooks` paths only (not in profile
filesystem fields). Wiring directives have their own separate expansion context
that also includes `$PACK_DIR`.

---

## Authoring workflow

1. **Scaffold** a skeleton profile:
   ```sh
   nono profile init <name> --extends default --full --output ./<pack>/policy.json
   ```

2. **Edit** `policy.json` and `package.json` in your editor. Export the JSON
   Schema for autocomplete:
   ```sh
   nono profile schema --output nono-profile.schema.json
   ```

3. **Validate** the profile:
   ```sh
   nono profile validate ./<pack>/policy.json
   ```

4. **Inspect** the resolved profile (after inheritance and group expansion):
   ```sh
   nono profile show ./<pack>/policy.json
   ```

5. **Sideload and test** — see `docs/TESTING.md`.

6. **Publish** — see the [Publishing Packs](https://nono.sh/docs/cli/features/package-publishing)
   guide for registry setup, trusted publisher configuration, and the GitHub
   Actions workflow.

---

## LLM authoring guide

nono ships an embedded authoring guide optimised for use as LLM context:

```sh
nono profile guide
```

Pipe or paste the output into your conversation when asking an LLM to help
write or review a profile.
