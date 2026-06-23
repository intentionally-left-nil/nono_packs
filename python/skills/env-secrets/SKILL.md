---
name: env-secrets
description: Configure outbound credentials for code running inside this sandboxed Python environment, so secrets stay outside the sandbox and are injected into requests in transit. Use when the user wants to set OPENAI_API_KEY or any other API token, mentions "store my API key", "my code needs a credential", "I have an environment variable for an API", or is starting a new integration with an HTTP service (remote HTTPS API or a localhost server) and does not yet know how to wire the credential. Do not use for general environment variables that are not secrets.
version: 1.0.0
platforms: [macos, linux]
---

# Skill: env-secrets

The Python interpreter in this environment is a sandboxed build that supports **credential injection**: secrets live in the system keychain, outside the sandbox; the sandbox's outbound proxy injects them into HTTP requests in transit; the Python process only ever sees a phantom token. The underlying technology is [nono](https://docs.nono.sh) — you do not run nono yourself. Run Python the normal way (`python script.py`, `pytest`, `jupyter lab`); the launcher applies the active profile automatically. **Never prefix with `nono run`** — that double-wraps and breaks the configuration you just edited.

The `nono profile` CLI is available for validating and inspecting profile files.

## When to use this skill

Trigger this skill when the user wants their sandboxed Python code to reach a service that needs a credential, AND any of:

- They have a key as an env var and want it available to their code without exposing it
- They are starting a new integration and have nothing stored yet
- A request is failing with 401/403 and the user mentions an API key
- They mention `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or any `*_API_KEY`/`*_TOKEN` env var

Do **not** use this skill for general env vars that are not secrets (`PYTHONPATH`, `LOG_LEVEL`, etc.) — those go in `environment.set_vars` in the profile, which is out of scope here.

## Workflow

```
Workflow checklist:
- [ ] Step 1: Discover what is already in the keychain
- [ ] Step 2: If the secret is missing, ask the user to store it (do not read its value)
- [ ] Step 3: Pick the route shape (remote HTTPS or localhost)
- [ ] Step 4: Edit the active nono profile to add the route
- [ ] Step 5: Validate the profile with `nono profile validate`
- [ ] Step 6: Wire client code if (and only if) the route is localhost
- [ ] Step 7: Tell the user to restart Python; verify the phantom token shape
```

## Step 1: Discover what is already stored

Secrets used by this sandbox live under the keychain service name `nono`. List the accounts already present — this never reveals values:

**macOS:**
```bash
security dump-keychain | awk -F'"' '/"svce"<blob>="nono"/{found=1} found && /"acct"/{print $4; found=0}'
```

**Linux:**
```bash
secret-tool search --all service nono
```

**Hard rule — never read the secret value.** Do not run `security find-generic-password ... -w`. Do not run `secret-tool lookup`. Do not echo, copy, or otherwise surface the secret. Existence and account name are sufficient for everything this skill does.

## Step 2: Store a new secret (if needed)

If the user is starting fresh, ask them to store the secret themselves so the value never enters the conversation. Choose an alphanumeric+underscore account name (the `credential_key` field is validated against this).

**macOS — interactive prompt, value never on the command line:**
```bash
security add-generic-password -s nono -a <account_name> -w
```

**Linux:**
```bash
secret-tool store --label="nono: <account_name>" service nono username <account_name> target default
```

**Other backends.** The user can also reference 1Password (`op://...`), Bitwarden (`bw://...`), Apple Passwords (`apple-password://...`), file-backed secrets (`file://...`), or a custom keyring service (`keyring://service/account`). If they want one of these, fetch <https://docs.nono.sh/llms.txt> for the authoritative `credential_key` URI schemes before composing the profile — the syntax requirements differ per backend (e.g. `op://` requires the `op` CLI authenticated, `bw://` requires `env_var` to be explicit).

## Step 3: Pick the route shape

There are two shapes. Pick based on where the upstream lives.

| Upstream | Shape | Why |
|---|---|---|
| Remote HTTPS (`https://api.example.com`) | **MITM via HTTPS_PROXY** | The sandbox sets `HTTPS_PROXY` and a CA bundle; outbound HTTPS is intercepted, the credential is injected as a header, and forwarded. **Client code requires no auth changes.** If the SDK refuses to send without an API key, pass any non-empty dummy string — the proxy strips and replaces the header before forwarding. |
| Localhost (`http://127.0.0.1:<port>`) | **Reverse proxy** | The sandbox's child env hardcodes `NO_PROXY=localhost,127.0.0.1`, so HTTPS_PROXY does not catch loopback traffic. The client must point its base URL at the proxy's reverse route and present the phantom token as its own auth value. |

Both shapes use the same profile fields. The difference is whether client code changes are needed.

## Step 4: Edit the active nono profile

Profiles are JSON files at `~/.config/nono/profiles/<name>.json`. The active profile is selected by `CONDA_PYTHON_PROFILE` — see the `python-sandbox` skill for setting that. If the user does not yet have a profile, create one extending the base Python sandbox profile.

**Two-field activation model:**

- `network.custom_credentials.<name>` = route definition (template)
- `network.credentials = ["<name>", ...]` = activation list

**A route is inert until its name appears in `credentials`.** Always write both fields together.

### Example A — Remote HTTPS (MITM)

User has an internal API at `https://api.acme.example.com`. Key stored as `acme_api`. Their code does `requests.get("https://api.acme.example.com/data")`.

```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "acme-client", "version": "1.0.0" },
  "filesystem": { "allow": ["$WORKDIR"] },
  "network": {
    "credentials": ["acme"],
    "custom_credentials": {
      "acme": {
        "upstream": "https://api.acme.example.com",
        "credential_key": "acme_api",
        "inject_header": "Authorization",
        "credential_format": "Bearer {}"
      }
    }
  }
}
```

Client code is unchanged. Outbound HTTPS to `api.acme.example.com` is intercepted; `Authorization: Bearer <real_key>` is injected; forwarded to upstream.

### Example B — Localhost (reverse proxy)

User runs a local LLM at `http://127.0.0.1:8080/v1`. Key stored as `local_llm`. The OpenAI SDK is the client.

```json
{
  "extends": "intentionally-left-nil/python",
  "meta": { "name": "inference-client", "version": "1.0.0" },
  "filesystem": { "allow": ["$WORKDIR"] },
  "network": {
    "credentials": ["openai_local"],
    "custom_credentials": {
      "openai_local": {
        "upstream": "http://127.0.0.1:8080/v1",
        "credential_key": "local_llm",
        "env_var": "OPENAI_API_KEY",
        "inject_header": "Authorization",
        "credential_format": "Bearer {}"
      }
    }
  }
}
```

The credential name `openai_local` produces two child env vars:

- `OPENAI_LOCAL_BASE_URL` → the reverse proxy route the client must call
- `OPENAI_API_KEY` → the phantom token (because `env_var` is set explicitly)

Without `env_var`, the phantom token would land in `OPENAI_LOCAL` (uppercase service name), which most SDKs do not read. Set `env_var` whenever the SDK expects a specific variable name.

### Field reference (the minimum)

| Field | Required | Notes |
|---|---|---|
| `upstream` | yes | HTTPS for remote, or `http://127.0.0.1:<port>...` / `http://localhost:<port>...` for loopback. No other HTTP allowed. |
| `credential_key` | yes | Bare account name under keychain service `nono` (alphanumeric+underscore), or a `op://`/`bw://`/`apple-password://`/`keyring://`/`file://`/`env://` URI. |
| `inject_header` | no | Defaults to `Authorization`. Use the upstream's expected header (e.g. `x-api-key` for Anthropic-style services). |
| `credential_format` | no | Defaults to `Bearer {}`. Use `{}` for a bare token. |
| `env_var` | conditional | Required when `credential_key` uses `op://`, `bw://`, `apple-password://`, `file://`, or `cmd://`. Recommended whenever the client SDK reads a specific env var name. |

For everything else (`inject_mode`, `path_pattern`, `query_param_name`, `basic_auth`, `endpoint_rules`, `tls_ca`, mTLS, `cmd://` capture), fetch <https://docs.nono.sh/llms.txt> and read the credential-injection schema. Do not guess these fields.

## Step 5: Validate the profile

After every edit, run:

```bash
nono profile validate ~/.config/nono/profiles/<name>.json
```

If it reports errors, fix them and re-run. Common errors:

- `must contain only alphanumeric characters and underscores` — `credential_key` is a bare name but contains hyphens or a URI prefix that is not recognized in this position.
- `Upstream URL must be HTTPS` — remote upstreams must be `https://`. Only `localhost`, `127.0.0.1`, and `::1` may use `http://`.
- `Credential not found for route 'X'` (warning at runtime) — the keychain entry referenced by `credential_key` does not exist. Go back to Step 1/2.

To inspect what the profile resolves to after inheritance:

```bash
nono profile show <name>
```

## Step 6: Wire client code (only for localhost)

Remote HTTPS routes need no client changes. Localhost routes do — the client must call the reverse proxy URL with the phantom token.

**Pattern:** read `<NAME_UPPERCASE>_BASE_URL` for the URL, and read `env_var` (or `NONO_PROXY_TOKEN` if `env_var` was not set) for the auth value.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["OPENAI_LOCAL_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],   # phantom token, swapped by the proxy
)
```

The phantom token (`os.environ["OPENAI_API_KEY"]`) is a long random hex string, **not the real key**. The proxy validates the phantom token, swaps it for the real credential from the keychain, and forwards upstream.

## Step 7: Restart and verify

Tell the user to restart Python — profile changes take effect at next interpreter startup, not in a running process.

After restart, sanity-check inside Python:

```python
import os
val = os.environ.get("OPENAI_API_KEY", "")
# Phantom tokens are 64 hex chars; real OpenAI keys start with "sk-"
assert val and not val.startswith("sk-"), "Real key leaked into the sandbox!"
```

A 401 from the upstream after this point means the **stored credential is wrong** — not a profile problem. The user must re-store the secret (Step 2).

## Last resort: env_credentials passthrough

If proxy injection genuinely cannot work — non-HTTP protocols, an SDK that bypasses HTTPS_PROXY and has no base-URL override, or a tool that needs the raw value at process startup — fall back to environment passthrough:

```json
{
  "env_credentials": {
    "acme_api": "ACME_API_KEY"
  }
}
```

This loads `acme_api` from the keychain and sets `ACME_API_KEY` in the sandboxed process. **The real secret enters the sandbox** in this mode. Document the reason in `meta.description` of the profile so a future reader knows why the weaker mode was chosen. Do not use this as a default.

## What you must NOT do

- **Do not prefix Python invocations with `nono run`, `nono shell`, or any other sandbox launcher.** The interpreter is already wrapped. Run `python script.py` exactly as the user would.
- **Do not read secret values.** No `security find-generic-password ... -w`. No `secret-tool lookup`. No printing values from any backend.
- **Do not paste, echo, or commit a real secret** — into the profile, into a script, into chat output, into a comment, into a test fixture, anywhere.
- **Do not hardcode the key in the script** after the user has stored it in the keychain.
- **Do not reach for `env_credentials`** unless proxy injection cannot work for a documented reason.
- **Do not add `network.credentials: []`** thinking it activates everything in `custom_credentials` — empty list means no routes are active.
