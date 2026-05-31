# nono npm pack

Supply chain attacks against the npm registry are well-documented and ongoing. The JavaScript ecosystem's dependency trees are famously deep, meaning a single `npm install` can pull in hundreds of transitive packages — each a potential vector. Between typosquatting, dependency confusion, compromised maintainer accounts, and malicious install scripts, the threat surface is large enough that it's time to treat `node_modules` the way we treat the rest of the untrusted web: sandboxed by default, with no implicit execution trust.

This pack tries to carefully separate two contexts:

- **Inside the sandbox**: npm can fetch and install packages normally, but with its own isolated cache and packages written to `sandbox_modules` rather than `node_modules`.
- **Outside the sandbox**: npm can optionally be restricted from downloading anything at all, and any code running on the host will not see the packages downloaded during sandbox sessions, since `node_modules` is empty.

The goal is that npm activity stays contained — what happens in the sandbox stays in the sandbox.

---

## Disabling npm outside the sandbox

To prevent npm from running at all on your host, this pack ships a `disabled.npmrc` that points npm at `localhost:0` — a port that does not exist — so every network operation fails immediately.

A symlink to this file is placed at `~/nono-disabled.npmrc` when you install the pack.

To enable it:

```sh
mv ~/nono-disabled.npmrc ~/.npmrc
```

To undo it (restore normal host npm access):

```sh
rm ~/.npmrc
```

With `disabled.npmrc` active, any npm command that touches the registry will fail:

```
npm error code ECONNREFUSED
npm error errno ECONNREFUSED
npm error network request to http://localhost:0/... failed
```

This is intentional. npm on your host is disabled. Run npm inside the sandbox instead.

---

## Running npm inside the sandbox

Launch the sandbox with the npm pack:

```sh
nono run --pack npm -- npm install
```

Inside the sandbox, npm is configured via `~/.config/nono_sandbox/.npmrc`. To customize registry, proxy, auth tokens, or any other npm settings, edit that file directly:

```sh
$EDITOR ~/.config/nono_sandbox/.npmrc
```

The sandbox policy (`policy.json`) allows:

- Read/write access to your working directory
- Read/write access to the npm cache at `~/.cache/nono_sandbox/npm_cache`
- Read access to the sandbox npmrc at `$XDG_CONFIG_HOME/nono_sandbox/.npmrc`
- The `deny_credentials` group is included, which blocks access to credential stores and secrets on the host

---

## How package isolation works

Before the sandbox session starts, the before-hook:

1. Sets `NPM_CONFIG_USERCONFIG` to the sandbox-specific `.npmrc`, overriding any host npmrc
2. If a real `node_modules/` directory exists in your working directory, it is moved to `node_modules.bak`
3. A `sandbox_modules/` directory is created (if it does not already exist)
4. `node_modules` is symlinked to `sandbox_modules`

After the session ends, the after-hook:

1. Removes the `node_modules` symlink
2. Restores the original `node_modules.bak` as `node_modules` (if one existed)
3. `sandbox_modules/` is left in place

This means:

- During the sandbox, `npm install` populates `sandbox_modules/` as if it were `node_modules/`
- After the sandbox exits, `node_modules/` is empty or restored to its pre-session state
- Code running outside the sandbox (including postinstall scripts triggered on a later bare `npm install`) will **not** automatically execute anything from `sandbox_modules/`

`sandbox_modules/` is yours to inspect or delete. Nothing in it runs unless you explicitly tell it to.
