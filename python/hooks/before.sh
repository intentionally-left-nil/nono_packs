#!/bin/sh
# before.sh — session hook for the python-sandbox nono pack
#
# Runs OUTSIDE the sandbox with host privileges before the sandboxed process
# starts. Receives: NONO_SESSION_ID, NONO_WORKDIR, NONO_ENV_FILE, PREFIX.
#
# The profile's set_vars redirect several cache and runtime directories to
# paths under $PREFIX/tmp. Those directories must exist before the sandboxed
# process starts, because some libraries (notably Jupyter) probe for them
# rather than creating them lazily.

set -e

if [ -z "$PREFIX" ]; then
    exit 0
fi

# Pre-create directories that set_vars points at.
# exist_ok equivalent: mkdir -p is idempotent.
mkdir -p \
    "$PREFIX/tmp" \
    "$PREFIX/tmp/pip" \
    "$PREFIX/tmp/jupyter/runtime" \
    "$PREFIX/tmp/jupyter/config" \
    "$PREFIX/tmp/ipython" \
    "$PREFIX/tmp/matplotlib" \
    "$PREFIX/tmp/numba" \
    "$PREFIX/tmp/triton" \
    "$PREFIX/tmp/torch_inductor" \
    "$PREFIX/__pycache__" \
    "$PREFIX/share/jupyter"
