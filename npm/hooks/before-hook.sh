#!/bin/sh
set -e

# Wire up NPM config to sandbox-specific npmrc
echo "NPM_CONFIG_USERCONFIG=${XDG_CONFIG_HOME:-$HOME/.config}/nono_sandbox/.npmrc" >> "$NONO_ENV_FILE"

# If node_modules is a real directory (not a symlink or file), back it up
if [ -d "$NONO_WORKDIR/node_modules" ] && [ ! -L "$NONO_WORKDIR/node_modules" ]; then
    mv "$NONO_WORKDIR/node_modules" "$NONO_WORKDIR/node_modules.bak"
fi

# Create sandbox_modules if it doesn't exist
if [ ! -e "$NONO_WORKDIR/sandbox_modules" ]; then
    mkdir "$NONO_WORKDIR/sandbox_modules"
fi

# Symlink node_modules -> sandbox_modules
ln -s "$NONO_WORKDIR/sandbox_modules" "$NONO_WORKDIR/node_modules"
