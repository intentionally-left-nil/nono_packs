#!/bin/sh
set -e

# Remove the node_modules symlink if present
if [ -L "$NONO_WORKDIR/node_modules" ]; then
    rm "$NONO_WORKDIR/node_modules"
fi

# Restore node_modules from backup if one exists
if [ -d "$NONO_WORKDIR/node_modules.bak" ]; then
    mv "$NONO_WORKDIR/node_modules.bak" "$NONO_WORKDIR/node_modules"
fi

# sandbox_modules is left in place intentionally
